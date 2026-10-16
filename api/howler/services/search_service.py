from __future__ import annotations

from collections.abc import Callable
from typing import Any

import elasticsearch
from elasticsearch import Elasticsearch

from howler.api.search_utils import (
    issue_scroll_token,
    read_scroll_token,
    resolve_deep_paging_id,
    validate_scroll_keep_alive,
)
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
from howler.datastore.utils import (
    field_paths_with_parents,
    normalize_field_list,
    project_stored_fields,
    select_stored_fields,
    stored_field_paths,
)
from howler.helper.search import INDEX_MAP, get_collection, get_default_sort, has_access_control
from howler.odm.models.user import User
from howler.services import case_service
from howler.utils.indexes import get_logical_index_name, normalize_indexes

DEFAULT_OFFSET = 0
DEFAULT_ROW_SIZE = 25
DEFAULT_SORT: list[dict[str, str]] = [{"_id": "asc"}]
DEFAULT_SEARCH_FIELD = "__text__"
SCROLL_TIMEOUT = "5m"

USER_STORED_FIELDS: frozenset[str] = frozenset(stored_field_paths(User.flat_fields()))
_USER_ALLOWED_FIELD_PATHS = frozenset(field_paths_with_parents(USER_STORED_FIELDS))

logger = get_logger(__file__)


def _resolve_search_collections(index_list: list[str], user: User | None) -> dict[str, ESCollection]:
    """Accept only the logical index names the caller may search.

    Physical names, aliases, and wildcards would bypass the per-index field rules and access-control filters.
    """
    if not index_list:
        raise SearchException("No indexes were provided.")

    collection_factories: dict[str, Callable[[], ESCollection]] = {}
    for index in index_list:
        collection_factory = get_collection(index, user) if user else INDEX_MAP.get(index)
        if collection_factory is None:
            raise SearchException(f"Not a valid index to search in: {index}")
        collection_factories[index] = collection_factory

    return {index: factory() for index, factory in collection_factories.items()}


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
            source.pop("__index", None)

            if raw_index:
                source["__index"] = get_logical_index_name(raw_index)

            if source.get("__index") == "case" and user_classification:
                case_service.filter_case_items_by_classification(source, user_classification)

            if include_id and hit.get("_id") is not None:
                source["id"] = hit["_id"]

            if source or include_id:
                items.append(source)

    return items


def user_fields_allowed(
    indexes: str | list[str],
    fl: str | list[str] | None,
    user: User | None = None,
) -> bool:
    """Guard legacy v1 source searches and aggregations that do not use stored-field projection."""
    if "user" not in _parse_index_list(indexes):
        return True
    try:
        names = normalize_field_list(fl)
    except SearchException:
        return False
    return all(name in _USER_ALLOWED_FIELD_PATHS or name == "id" for name in names)


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
    search_collections = _resolve_search_collections(index_list, user)
    source_fields, allowed_fields_by_index, selected_id = select_stored_fields(search_collections, fl)
    include_id = include_id or selected_id

    if user and user.classification and "case" in allowed_fields_by_index:
        selected_case_fields = allowed_fields_by_index["case"]
        if any(field == "items" or field.startswith("items.") for field in selected_case_fields):
            if "items.classification" not in source_fields:
                source_fields.append("items.classification")

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
        "_source": source_fields,
    }

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

    items = _format_items(hits, user.classification if user else None, include_id=include_id)
    items = project_stored_fields(items, allowed_fields_by_index, include_id, fields=fl)

    response: SearchResult[dict[str, Any]] = {
        "offset": int(offset),
        "rows": len(hits),
        "total": int(total),
        "items": items,
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
        logger.exception("Failed to clear Elasticsearch scroll")
        raise SearchRetryException("The scroll context could not be cleared. Please retry.") from error
    except (elasticsearch.exceptions.TransportError, elasticsearch.exceptions.RequestError) as error:
        logger.exception("Failed to clear Elasticsearch scroll")
        raise SearchException("The scroll context could not be cleared.") from error
    except Exception as error:
        logger.exception("Failed to clear Elasticsearch scroll")
        raise SearchException("The scroll context could not be cleared.") from error


def clear_owned_scroll(user: User, scroll_token: Any) -> dict[str, Any]:
    """Clear the Elasticsearch scroll behind a token, but only for the user who opened it."""
    claims = read_scroll_token(scroll_token)
    if claims["u"] != user["uname"]:
        raise InvalidScrollTokenException("Scroll token belongs to another user.")

    return clear_scroll(claims["s"])


def scroll_search(
    indexes: str, query: str, user: User, params: dict[str, Any], scroll: str | None
) -> SearchResult[dict[str, Any]]:
    """Open or continue a deep-paging scroll with user-bound tokens and stored-field projection."""
    if not isinstance(query, str):
        raise SearchException("Search query must be a string.")

    keep_alive = validate_scroll_keep_alive(scroll)
    search_params = params.copy()
    search_params["deep_paging_id"] = resolve_deep_paging_id(user, indexes, params["deep_paging_id"], query)
    requested_fields = normalize_field_list(params.get("fl"))
    result = search(
        indexes,
        query,
        user=user,
        scroll=keep_alive,
        include_id=not requested_fields or "*" in requested_fields,
        **search_params,
    )
    next_scroll_id = result.get("next_deep_paging_id")
    if next_scroll_id is not None:
        result["next_deep_paging_id"] = issue_scroll_token(user, indexes, next_scroll_id, query)

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

    if not user_fields_allowed(index_list, fields, user):
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
