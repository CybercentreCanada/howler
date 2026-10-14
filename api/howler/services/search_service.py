from __future__ import annotations

from typing import Any

import elasticsearch
from elasticsearch import Elasticsearch

from howler.api.search_utils import read_scroll_token
from howler.common.loader import datastore
from howler.common.logging import get_logger
from howler.datastore.collection import ESCollection, parse_sort
from howler.datastore.exceptions import (
    InvalidScrollTokenException,
    SearchException,
    SearchRetryException,
    SensitiveUserFieldsException,
)
from howler.datastore.types import SearchResult
from howler.helper.search import INDEX_MAP, get_collection, get_default_sort, has_access_control
from howler.odm.base import BANNED_FIELDS
from howler.odm.models.user import User
from howler.services import case_service
from howler.utils.indexes import get_logical_index_name, normalize_indexes

DEFAULT_OFFSET = 0
DEFAULT_ROW_SIZE = 25
DEFAULT_SORT: list[dict[str, str]] = [{"_id": "asc"}]
DEFAULT_SEARCH_FIELD = "__text__"
SCROLL_TIMEOUT = "5m"

_USER_FLAT_FIELDS = User.flat_fields()
USER_STORED_FIELDS: frozenset[str] = frozenset(
    name for name, field in _USER_FLAT_FIELDS.items() if field.store and name not in BANNED_FIELDS
)
_USER_DENIED_ROOTS: frozenset[str] = frozenset(
    {name.split(".")[0] for name in _USER_FLAT_FIELDS if name not in USER_STORED_FIELDS} | BANNED_FIELDS
)

logger = get_logger(__file__)


def _validate_search_indexes(index_list: list[str], user: User | None) -> None:
    """Accept only the logical index names the caller may search.

    Physical names, aliases, and wildcards would bypass the per-index field rules and access-control filters.
    """
    if not index_list:
        raise SearchException("No indexes were provided.")

    for index in index_list:
        collection = get_collection(index, user) if user else INDEX_MAP.get(index)
        if collection is None:
            raise SearchException(f"Not a valid index to search in: {index}")


def _requested_field_names(fl: Any) -> list[str] | None:
    """Split a field request into names, or return None when the request has an unsupported shape."""
    if fl is None:
        return []

    entries = [fl] if isinstance(fl, str) else fl if isinstance(fl, list) else None
    if entries is None or not all(isinstance(entry, str) for entry in entries):
        return None

    return [name.strip() for entry in entries for name in entry.split(",") if name.strip()]


def _format_items(
    hits: list[dict[str, Any]], user_classification: str | None, include_id: bool = False
) -> list[dict[str, Any]]:
    """Formats Elasticsearch search hits into a standardized item format.

    Extracts the _source content from each hit.

    Args:
        hits: A list of Elasticsearch hit dictionaries containing _source and metadata.

    Returns:
        A list of formatted item dictionaries.
    """
    items: list[dict[str, Any]] = []
    for hit in hits:
        source = hit.get("_source")

        if source is not None:
            raw_index = hit.get("_index", None)

            if raw_index:
                source["__index"] = get_logical_index_name(raw_index)

            if source.get("__index") == "case" and user_classification:
                case_service.filter_case_items_by_classification(source, user_classification)

            if include_id and hit.get("_id") is not None:
                source["id"] = hit["_id"]

            if source or include_id:
                items.append(source)

    return items


def user_fields_allowed(indexes: str | list[str], fl: Any) -> bool:
    """Return False when a request for the user index names non-stored, banned, or wildcard fields.

    Only stored user fields are safe to return. Anything else, including the credential fields and
    wildcards that could expand to them, is refused. Requests for other indexes are not affected.
    """
    if "user" not in _parse_index_list(indexes):
        return True

    names = _requested_field_names(fl)
    return names is not None and all("*" not in name and name.split(".")[0] not in _USER_DENIED_ROOTS for name in names)


def search(  # noqa: C901
    indexes: str | list[str],
    query: str | None = None,
    deep_paging_id: str | None = None,
    filters: list[str] | str | None = None,
    offset: int | None = None,
    rows: int | None = None,
    sort: str | dict[str, str] | list[dict[str, str]] | None = None,
    fl: str | list[str] | None = None,
    timeout: int | None = None,
    track_total_hits: bool = False,
    metadata: list[str] | None = None,
    user: User | None = None,
    scroll: str | None = None,
    include_id: bool = False,
) -> SearchResult[dict[str, Any]]:
    """Search through specified index for a given query. Uses lucene search syntax for query.

    Variables:
    indexes  =>   Comma-separated list of indexes to search in (hit, event,...)

    Arguments:
    query: Query to search for
    deep_paging_id   : ID of the next page or * to start deep paging
    scroll           : Scroll keep-alive duration (defaults to 5m for deep paging)
    include_id       : Include Elasticsearch's document ID in each formatted item
    filters          : List of additional filter queries limit the data
    offset           : Offset in the results
    rows             : Number of results per page
    sort             : How to sort the results (not available in deep paging)
    fl               : List of fields to return
    timeout          : Maximum execution time (ms)
    track_total_hits : Track the total number of query matches, instead of stopping at 10000 (Default: False)
    metadata         : A list of additional features to be added to the result alongside the raw results

    Result Example:
    {"total": 201,                          # Total results found
     "offset": 0,                           # Offset in the result list
     "rows": 100,                           # Number of results returned
     "next_deep_paging_id": "asX3f...342",  # ID to pass back for the next page during deep paging
     "items": []}                           # List of results
    """
    del metadata

    index_list = _parse_index_list(indexes)
    _validate_search_indexes(index_list, user)
    if "user" in index_list:
        if not user_fields_allowed(index_list, fl):
            raise SensitiveUserFieldsException("Invalid fields to retrieve.")
        if not _requested_field_names(fl):
            if len(index_list) > 1:
                raise SensitiveUserFieldsException("Specify fl when searching the user index with other indexes.")
            fl = sorted(USER_STORED_FIELDS)

    client: Elasticsearch = datastore().ds.client
    parsed_indexes = normalize_indexes(indexes)

    if filters is None:
        parsed_filters: list[str] = []
    elif isinstance(filters, str):
        parsed_filters = [filters]
    else:
        parsed_filters = filters

    # NOTE: This means index searches must be either ALL access controlled or none of them have access control.
    # Otherwise, the access control requirements on one index will cause the other index to return no items.
    # This is pretty reasonable constraint, as all the relevant, searchable items support classifications.
    if user and user.access_control and has_access_control(index_list):
        parsed_filters.append(user.access_control)

    if query is None:
        query = "id:*"

    if sort is None:
        default_sorts = [get_default_sort(index, user) for index in _parse_index_list(indexes)] if user else []
        default_sort = default_sorts[0] if default_sorts else None
        if default_sort is not None and all(index_sort == default_sort for index_sort in default_sorts):
            sort = default_sort
        else:
            sort = DEFAULT_SORT

    if rows is None:
        rows = DEFAULT_ROW_SIZE
    else:
        rows = int(rows)

    if offset is None:
        offset = DEFAULT_OFFSET
    else:
        offset = int(offset)

    source_fields: list[str] | None
    if fl is None:
        source_fields = None
    elif isinstance(fl, str):
        source_fields = [field.strip() for field in fl.split(",") if field.strip()]
    else:
        source_fields = [field.strip() for field in fl if field.strip()]

    params: dict[str, Any] = {}
    if deep_paging_id is not None:
        params["scroll"] = scroll if scroll is not None else SCROLL_TIMEOUT
    elif track_total_hits:
        params["track_total_hits"] = True

    if timeout is not None and deep_paging_id in (None, "*"):
        params["timeout"] = f"{timeout}ms"

    query_body: dict[str, Any] = {
        "query": {
            "bool": {
                "must": {"query_string": {"query": query, "default_field": DEFAULT_SEARCH_FIELD}},
                "filter": [{"query_string": {"query": filter_query}} for filter_query in parsed_filters],
            }
        },
        "from_": offset,
        "size": rows,
        "sort": parse_sort(sort),
    }

    if source_fields is not None:
        query_body["_source"] = source_fields

    try:
        if deep_paging_id is not None and deep_paging_id != "*":
            result = client.scroll(scroll_id=deep_paging_id, **params)
        else:
            result = client.search(index=parsed_indexes, **params, **query_body)
    except (elasticsearch.exceptions.ConnectionError, elasticsearch.exceptions.ConnectionTimeout) as error:
        raise SearchRetryException(f"indexes: {parsed_indexes}, query: {query}, error: {str(error)}") from error
    except (elasticsearch.exceptions.TransportError, elasticsearch.exceptions.RequestError) as error:
        raise SearchException(str(error)) from error
    except Exception as error:
        raise SearchException(f"indexes: {parsed_indexes}, query: {query}, error: {str(error)}") from error

    total = result.get("hits", {}).get("total", {}).get("value", 0)
    hits = result.get("hits", {}).get("hits", [])

    response: SearchResult[dict[str, Any]] = {
        "offset": int(offset),
        "rows": len(hits),
        "total": int(total),
        "items": _format_items(hits, user.classification if user else None, include_id=include_id),
    }

    next_deep_paging_id = result.get("_scroll_id")

    if deep_paging_id is not None and next_deep_paging_id is None:
        try:
            client.clear_scroll(scroll_id=deep_paging_id)
        except elasticsearch.exceptions.NotFoundError:
            pass

    if next_deep_paging_id is not None and len(response["items"]) < rows:
        try:
            client.clear_scroll(scroll_id=next_deep_paging_id)
        except elasticsearch.exceptions.NotFoundError:  # pragma: no cover
            pass
        next_deep_paging_id = None

    if next_deep_paging_id is not None:
        response["next_deep_paging_id"] = next_deep_paging_id

    return response


def clear_scroll(scroll_id: str) -> dict[str, Any]:
    """Clear an Elasticsearch scroll context and return Elasticsearch's response."""
    client: Elasticsearch = datastore().ds.client

    try:
        return dict(client.clear_scroll(scroll_id=scroll_id).body)
    except (elasticsearch.exceptions.ConnectionError, elasticsearch.exceptions.ConnectionTimeout) as error:
        raise SearchRetryException(f"scroll_id: {scroll_id}, error: {str(error)}") from error
    except (elasticsearch.exceptions.TransportError, elasticsearch.exceptions.RequestError) as error:
        raise SearchException(str(error)) from error
    except Exception as error:
        raise SearchException(f"scroll_id: {scroll_id}, error: {str(error)}") from error


def clear_owned_scroll(user: User, scroll_token: Any) -> dict[str, Any]:
    """Clear the Elasticsearch scroll behind a token, but only for the user who opened it."""
    claims = read_scroll_token(scroll_token)
    if claims["u"] != user["uname"]:
        raise InvalidScrollTokenException("Scroll token belongs to another user.")

    return clear_scroll(claims["s"])


def scroll_search(
    indexes: str, query: str, user: User, params: dict[str, Any], scroll: Any
) -> SearchResult[dict[str, Any]]:
    """Open or continue a deep-paging scroll with user-bound tokens, access control, and field projection."""
    from howler.api.search_utils import (
        issue_scroll_token,
        prune_scroll_items,
        resolve_deep_paging_id,
        select_safe_scroll_fields,
        validate_scroll_keep_alive,
    )

    if not isinstance(query, str):
        raise SearchException("Search query must be a string.")

    index_list = _parse_index_list(indexes)
    requested_fl = params.get("fl")
    if not user_fields_allowed(index_list, requested_fl):
        raise SensitiveUserFieldsException("Invalid fields to retrieve.")

    scroll_collections: dict[str, ESCollection] = {}
    for index in index_list:
        collection = get_collection(index, user)
        if collection is None:
            raise SearchException(f"Not a valid index to search in: {index}")
        scroll_collections[index] = collection()

    keep_alive = validate_scroll_keep_alive(scroll)
    search_params = params.copy()
    search_params["deep_paging_id"] = resolve_deep_paging_id(user, indexes, params["deep_paging_id"], query)
    search_params["fl"], scroll_fields, include_id = select_safe_scroll_fields(scroll_collections, requested_fl)

    result = search(
        indexes,
        query,
        user=user,
        scroll=keep_alive,
        include_id=include_id,
        **search_params,
    )
    next_scroll_id = result.get("next_deep_paging_id")
    if next_scroll_id is not None:
        result["next_deep_paging_id"] = issue_scroll_token(user, indexes, next_scroll_id, query)

    result["items"] = prune_scroll_items(result["items"], scroll_fields, include_id)
    return result


def _parse_index_list(indexes: str | list[str]) -> list[str]:
    if isinstance(indexes, str):
        return [index.strip() for index in indexes.split(",") if index.strip()]
    return [index.strip() for index in indexes if index.strip()]


def _parse_filters(filters: list[str] | str | None) -> list[str]:
    if filters is None:
        return []
    if isinstance(filters, str):
        return [filters]
    return list(filters)


def _resolve_facet_context(index_list: list[str], user: User | None) -> tuple[list[str], list[set[str]]]:
    normalized_indexes: list[str] = []
    index_fields: list[set[str]] = []

    for index in index_list:
        collection = get_collection(index, user) if user else None
        if collection is None:
            raise SearchException(f"Not a valid index to search in: {index}")

        resolved_collection = collection()
        normalized_indexes.append(resolved_collection.index_name)
        index_fields.append(set(resolved_collection.fields().keys()))

    return normalized_indexes, index_fields


def _build_facet_aggregations(
    valid_fields: list[str], rows: int, mincount: int
) -> dict[str, dict[str, dict[str, Any]]]:
    return {
        field: {
            "terms": {
                "field": field,
                "size": rows,
                "min_doc_count": mincount,
            }
        }
        for field in valid_fields
    }


def _build_facet_query(query: str, parsed_filters: list[str]) -> dict[str, dict[str, Any]]:
    return {
        "bool": {
            "must": {
                "query_string": {
                    "query": query,
                    "default_field": DEFAULT_SEARCH_FIELD,
                }
            },
            "filter": [{"query_string": {"query": filter_query}} for filter_query in parsed_filters],
        }
    }


def _get_valid_facet_fields(fields: list[str], index_fields: list[set[str]]) -> list[str]:
    valid_fields: list[str] = []
    for field in fields:
        if any(field in available_fields for available_fields in index_fields):
            valid_fields.append(field)
        else:
            logger.warning("Invalid field %s requested for faceting, skipping", field)

    return valid_fields


def _format_facet_result(
    valid_fields: list[str],
    base_result: dict[str, dict[str, Any]],
    raw_result: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    for field in valid_fields:
        base_result[field] = {
            row.get("key_as_string", row["key"]): row["doc_count"]
            for row in raw_result.get("aggregations", {}).get(field, {}).get("buckets", [])
        }

    return base_result


def facet(
    indexes: str | list[str],
    fields: list[str],
    query: str | None = None,
    mincount: int = 1,
    rows: int = 10,
    filters: list[str] | str | None = None,
    user: User | None = None,
) -> dict[str, dict[str, Any]]:
    """Facet one or more fields across one or more indexes in a single Elasticsearch request."""
    if not fields:
        return {}

    index_list = _parse_index_list(indexes)

    if not index_list:
        raise SearchException("No indexes were provided.")

    if not user_fields_allowed(index_list, fields):
        raise SensitiveUserFieldsException("Invalid fields to facet on.")

    facet_result: dict[str, dict[str, Any]] = {field: {} for field in fields}

    normalized_indexes, index_fields = _resolve_facet_context(index_list, user)

    valid_fields = _get_valid_facet_fields(fields, index_fields)

    if not valid_fields:
        return facet_result

    parsed_filters = _parse_filters(filters)

    if user and user.access_control and has_access_control(index_list):
        parsed_filters.append(user.access_control)

    effective_query = query or "id:*"

    aggregations = _build_facet_aggregations(valid_fields, rows, mincount)
    facet_query = _build_facet_query(effective_query, parsed_filters)

    client: Elasticsearch = datastore().ds.client

    try:
        result: Any = client.search(index=",".join(normalized_indexes), query=facet_query, aggs=aggregations, size=0)
    except (elasticsearch.exceptions.ConnectionError, elasticsearch.exceptions.ConnectionTimeout) as error:
        raise SearchRetryException(
            f"indexes: {','.join(normalized_indexes)}, query: {effective_query}, error: {str(error)}"
        ) from error
    except (elasticsearch.exceptions.TransportError, elasticsearch.exceptions.RequestError) as error:
        raise SearchException(str(error)) from error
    except Exception as error:
        raise SearchException(
            f"indexes: {','.join(normalized_indexes)}, query: {effective_query}, error: {str(error)}"
        ) from error

    return _format_facet_result(valid_fields, facet_result, result)


if __name__ == "__main__":
    results = search("hit,event", "howler.id:*", sort="timestamp desc", rows=250)

    indexes = {result["_index"] for result in results["items"]}

    print(indexes)  # noqa: T201
