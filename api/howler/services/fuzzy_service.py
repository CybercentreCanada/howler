from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

import elasticsearch
from elasticsearch import Elasticsearch

from howler import odm
from howler.common.loader import APP_NAME, datastore
from howler.datastore.exceptions import SearchException, SearchRetryException
from howler.datastore.types import SearchResult
from howler.odm.base import (
    DOMAIN_ONLY_REGEX,
    EMAIL_REGEX,
    IP,
    IP_ONLY_REGEX,
    MD5_REGEX,
    SHA1_REGEX,
    SHA256_REGEX,
    List,
    Optional,
    Text,
    _Field,
)
from howler.services.search_service import _normalize_indexes
from howler.utils.str_utils import sanitize_lucene_query

DEFAULT_OFFSET = 0
DEFAULT_ROW_SIZE = 100
VALID_INDEXES = {"hit", "event", "case"}


def _escape_query_string(query: str) -> str:
    """Escape special Lucene characters from a raw query string."""
    return sanitize_lucene_query(query)


# Compiled regexes from ODM base for token type detection
_IP_RE = re.compile(IP_ONLY_REGEX)
_MD5_RE = re.compile(MD5_REGEX, re.IGNORECASE)
_SHA1_RE = re.compile(SHA1_REGEX, re.IGNORECASE)
_SHA256_RE = re.compile(SHA256_REGEX, re.IGNORECASE)
_EMAIL_RE = re.compile(EMAIL_REGEX)
_DOMAIN_RE = re.compile(DOMAIN_ONLY_REGEX)
# FULL_URI is too permissive for token detection (matches bare domains).
# Use a scheme-prefix check to identify URLs specifically.
_URL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+\-.]*://", re.IGNORECASE)

# Field boosts by index
FIELD_BOOSTS: dict[str, dict[str, int]] = {
    "hit": {
        "howler.id": 5,
        "howler.outline.threat": 4,
        "howler.outline.target": 3,
        "related.ip": 4,
        "related.user": 3,
        "related.uri": 3,
        "related.hosts": 3,
        "related.hash": 3,
        "related.signature": 2,
        "message": 1,
    },
    "event": {
        "howler.id": 5,
        "source.ip": 4,
        "destination.ip": 4,
        "dns.domain": 3,
        "url.domain": 3,
        "http.host": 3,
        "related.ip": 2,
        "related.user": 2,
        "related.uri": 2,
        "related.hosts": 2,
        "related.hash": 2,
        "message": 1,
    },
    "case": {
        "case_id": 5,
        "indicators": 4,
        "targets": 4,
        "items.value": 3,
        "items.path": 2,
    },
}


def _detect_token_type(token: str) -> str:
    """Detect the type of a search token using ODM-defined patterns.

    Returns one of: 'ip', 'md5', 'sha1', 'sha256', 'email', 'url', 'domain', 'text'
    """
    if _IP_RE.match(token):
        return "ip"
    if _MD5_RE.match(token):
        return "md5"
    if _SHA1_RE.match(token):
        return "sha1"
    if _SHA256_RE.match(token):
        return "sha256"
    if _EMAIL_RE.match(token):
        return "email"
    if _URL_RE.match(token):
        return "url"
    if _DOMAIN_RE.match(token):
        return "domain"
    return "text"


def _get_fields_for_index(index: str) -> list[str]:
    """Get boosted field strings for a given index."""
    boosts = FIELD_BOOSTS.get(index, {})
    return [f"{field}^{boost}" for field, boost in boosts.items()]


def _resolve_field_type(field: _Field) -> type:
    """Unwrap Optional/List wrappers to get the leaf field type."""
    if isinstance(field, Optional):
        return _resolve_field_type(field.child_type)
    if isinstance(field, List):
        return _resolve_field_type(field.child_type)
    return type(field)


@lru_cache(maxsize=1)
def _classify_boosted_fields() -> dict[str, str]:
    """Classify each field in FIELD_BOOSTS by its Elasticsearch type using ODM model introspection.

    Inspects the flat_fields() of each model to determine the ES mapping type.
    Fields declared as odm.IP() map to ES 'ip' type.
    Fields declared as odm.Text() map to ES 'text' type.
    All others (Keyword and subtypes) map to ES 'keyword' type.

    Returns:
        A dict mapping field name to one of 'ip', 'text', or 'keyword'.
    """
    from howler.odm.models.case import Case
    from howler.odm.models.event import Event
    from howler.odm.models.hit import Hit

    model_map: dict[str, type[odm.Model]] = {
        "hit": Hit,
        "event": Event,
        "case": Case,
    }

    field_types: dict[str, str] = {}
    for index, fields in FIELD_BOOSTS.items():
        model_class = model_map.get(index, None)
        if not model_class:
            continue

        flat = model_class.flat_fields()
        for field_name in fields:
            if field_name in field_types:
                continue
            field_def = flat.get(field_name)
            if not field_def:
                field_types[field_name] = "keyword"
                continue
            leaf_type = _resolve_field_type(field_def)
            if issubclass(leaf_type, IP):
                field_types[field_name] = "ip"
            elif issubclass(leaf_type, Text):
                field_types[field_name] = "text"
            else:
                field_types[field_name] = "keyword"

    return field_types


def _get_ip_typed_fields() -> set[str]:
    """Return the set of fields classified as IP type."""
    return {f for f, t in _classify_boosted_fields().items() if t == "ip"}


def build_fuzzy_query(  # noqa: C901
    query: str,
    indexes: list[str],
    filters: list[str] | None = None,
    access_control: str | None = None,
) -> dict[str, Any]:
    """Build an Elasticsearch query body for fuzzy/plain-text search.

    Args:
        q: The search string (plain text, IP, hash, domain, etc.)
        indexes: List of index names to search across.
        filters: Additional filter queries.
        access_control: Access control filter string.

    Returns:
        An Elasticsearch query body dict.
    """
    query = query.strip()
    token_type = _detect_token_type(query)

    # Collect all boosted fields across requested indexes
    all_fields: list[str] = []
    for index in indexes:
        all_fields.extend(_get_fields_for_index(index))

    # De-duplicate fields (keep highest boost if duplicate base field)
    field_boost_map: dict[str, int] = {}
    for field_str in all_fields:
        if "^" in field_str:
            field, boost_str = field_str.rsplit("^", 1)
            boost = int(boost_str)
        else:
            field = field_str
            boost = 1
        if field not in field_boost_map or field_boost_map[field] < boost:
            field_boost_map[field] = boost

    # Partition fields by ES type using ODM model introspection.
    # - ip: must use term queries (no fuzzy/phrase support)
    # - text: supports all query types including phrase_prefix
    # - keyword: supports best_fields and phrase, but NOT phrase_prefix
    field_classes = _classify_boosted_fields()
    ip_fields: dict[str, int] = {}
    text_fields: dict[str, int] = {}
    keyword_fields: dict[str, int] = {}
    for f, b in field_boost_map.items():
        es_type = field_classes.get(f, "keyword")
        if es_type == "ip":
            ip_fields[f] = b
        elif es_type == "text":
            text_fields[f] = b
        else:
            keyword_fields[f] = b

    # Fields safe for multi_match best_fields / phrase (text + keyword)
    searchable_field_list = [f"{f}^{b}" for f, b in {**text_fields, **keyword_fields}.items()]
    # Fields safe for phrase_prefix (text only)
    text_field_list = [f"{f}^{b}" for f, b in text_fields.items()]

    should_clauses: list[dict[str, Any]] = []

    # Broad catch-all: query_string across all indexed fields at low boost.
    # This ensures every field in the schema is searched (e.g. agent.type),
    # while the boosted multi_match clauses below rank high-value fields higher.
    escaped_q = sanitize_lucene_query(query)

    if token_type == "ip":  # noqa: S105
        # For IP tokens, use term queries on IP fields and best_fields on boosted text/keyword fields
        for field, boost in ip_fields.items():
            should_clauses.append({"term": {field: {"value": query, "boost": boost}}})
        if searchable_field_list:
            should_clauses.append(
                {"multi_match": {"query": query, "fields": searchable_field_list, "type": "best_fields"}}
            )
        should_clauses.append({"query_string": {"query": escaped_q, "default_field": "*", "boost": 0.5}})
    elif token_type in ("md5", "sha1", "sha256"):
        # Exact match for hashes — boosted fields + catch-all
        if searchable_field_list:
            should_clauses.append(
                {"multi_match": {"query": query, "fields": searchable_field_list, "type": "best_fields"}}
            )
        should_clauses.append({"query_string": {"query": escaped_q, "default_field": "*", "boost": 0.5}})
    elif token_type in ("email", "url", "domain"):
        # Use phrase matching on boosted fields + catch-all
        if searchable_field_list:
            should_clauses.append({"multi_match": {"query": query, "fields": searchable_field_list, "type": "phrase"}})
            should_clauses.append(
                {"multi_match": {"query": query, "fields": searchable_field_list, "type": "best_fields"}}
            )
        should_clauses.append({"query_string": {"query": escaped_q, "default_field": "*", "boost": 0.5}})
    else:
        # General text - boosted fuzzy match + catch-all across all fields
        if searchable_field_list:
            should_clauses.append(
                {
                    "multi_match": {
                        "query": query,
                        "fields": searchable_field_list,
                        "type": "best_fields",
                        "fuzziness": "AUTO",
                    }
                }
            )
            # phrase_prefix only works on text fields, not keyword
            if len(query) >= 3 and text_field_list:
                should_clauses.append(
                    {"multi_match": {"query": query, "fields": text_field_list, "type": "phrase_prefix"}}
                )
        should_clauses.append(
            {"query_string": {"query": f"*{escaped_q}*", "default_field": "*", "boost": 0.5, "analyze_wildcard": True}}
        )

    # Build filter clauses
    filter_clauses: list[dict[str, Any]] = []
    if filters:
        for f in filters:
            filter_clauses.append({"query_string": {"query": f}})
    if access_control:
        filter_clauses.append({"query_string": {"query": access_control}})

    query_body: dict[str, Any] = {
        "query": {
            "bool": {
                "should": should_clauses,
                "minimum_should_match": 1,
            }
        }
    }

    if filter_clauses:
        query_body["query"]["bool"]["filter"] = filter_clauses

    return query_body


def fuzzy_search(
    indexes: list[str],
    query: str,
    filters: list[str] | None = None,
    offset: int = DEFAULT_OFFSET,
    rows: int = DEFAULT_ROW_SIZE,
    track_total_hits: bool = False,
    access_control: str | None = None,
) -> SearchResult[dict[str, Any]]:
    """Perform a fuzzy/plain-text search across multiple indexes.

    Args:
        indexes: List of index names (hit, event, case).
        q: Plain text search query.
        filters: Additional filter queries.
        offset: Offset into results.
        rows: Number of results to return.
        track_total_hits: Whether to track total hits beyond 10000.
        access_control: Access control filter string.

    Returns:
        A SearchResult containing matched items with __index and _score.
    """
    # Validate indexes
    for idx in indexes:
        if idx not in VALID_INDEXES:
            raise SearchException(f"Invalid index for fuzzy search: {idx}")

    client: Elasticsearch = datastore().ds.client
    parsed_indexes = _normalize_indexes(indexes)

    query_body = build_fuzzy_query(query, indexes, filters, access_control)

    params: dict[str, Any] = {}
    if track_total_hits:
        params["track_total_hits"] = True

    try:
        result = client.search(
            index=parsed_indexes,
            sort=[{"_score": "desc"}],
            from_=offset,
            size=rows,
            **params,
            **query_body,
        )
    except (elasticsearch.exceptions.ConnectionError, elasticsearch.exceptions.ConnectionTimeout) as error:
        raise SearchRetryException(f"indexes: {parsed_indexes}, query: {query}, error: {str(error)}") from error
    except (elasticsearch.exceptions.TransportError, elasticsearch.exceptions.RequestError) as error:
        raise SearchException(str(error)) from error
    except Exception as error:
        raise SearchException(f"indexes: {parsed_indexes}, query: {query}, error: {str(error)}") from error

    total = result.get("hits", {}).get("total", {}).get("value", 0)
    hits = result.get("hits", {}).get("hits", [])

    items = _format_items_with_score(hits)

    response: SearchResult[dict[str, Any]] = {
        "offset": int(offset),
        "rows": len(items),
        "total": int(total),
        "items": items,
    }

    return response


def _format_items_with_score(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Format Elasticsearch hits including _score in the output."""
    items: list[dict[str, Any]] = []
    for hit in hits:
        source = hit.get("_source")
        if source:
            raw_index = hit.get("_index", None)
            if raw_index:
                source["__index"] = raw_index.replace(f"{APP_NAME}-", "").replace("_hot", "")
            source["_score"] = hit.get("_score", 0)
            items.append(source)
    return items
