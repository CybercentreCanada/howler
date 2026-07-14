from __future__ import annotations

from typing import Any

import elasticsearch
from elasticsearch import Elasticsearch

from howler.common.loader import APP_NAME, datastore
from howler.common.logging import get_logger
from howler.datastore.collection import parse_sort
from howler.datastore.exceptions import SearchException, SearchRetryException
from howler.datastore.types import SearchResult
from howler.helper.search import get_collection, has_access_control
from howler.odm.models.user import User
from howler.services import case_service

DEFAULT_OFFSET = 0
DEFAULT_ROW_SIZE = 25
DEFAULT_SORT: list[dict[str, str]] = [{"_id": "asc"}]
DEFAULT_SEARCH_FIELD = "__text__"
SCROLL_TIMEOUT = "5m"

logger = get_logger(__file__)


def _normalize_indexes(indexes: str | list[str]) -> str:
    """Normalizes Elasticsearch index names into a comma-separated string.

    Parses the input indexes and applies naming conventions. Special patterns like
    wildcards, exclusions, and explicitly formatted indexes are preserved as-is.
    Regular indexes are formatted with the APP_NAME prefix and '_hot' suffix.

    Args:
        indexes: A comma-separated string or list of index names to normalize.

    Returns:
        A comma-separated string of normalized index names ready for Elasticsearch queries.

    Raises:
        SearchException: If no valid indexes are provided after parsing and stripping whitespace.

    Examples:
        >>> _normalize_indexes("logs,metrics")
        "howler-logs_hot,howler-metrics_hot"

        >>> _normalize_indexes(["*", "custom-index"])
        "*,custom-index"

        >>> _normalize_indexes("alerts, events")
        "howler-alerts_hot,howler-events_hot"
    """
    if isinstance(indexes, str):
        parsed_indexes = [item.strip() for item in indexes.split(",") if item.strip()]
    else:
        parsed_indexes = [item.strip() for item in indexes if item.strip()]

    if not parsed_indexes:
        raise SearchException("No indexes were provided.")

    normalized_indexes: list[str] = []
    for index in parsed_indexes:
        if index in {"*", "_all"} or "-" in index or "*" in index:
            normalized_indexes.append(index)
        else:
            normalized_indexes.append(f"{APP_NAME}-{index}")

    return ",".join(normalized_indexes)


def _format_items(hits: list[dict[str, Any]], user_classification: str | None) -> list[dict[str, Any]]:
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

        if source:
            raw_index = hit.get("_index", None)

            if raw_index:
                source["__index"] = raw_index.replace(f"{APP_NAME}-", "").replace("_hot", "")

            if source.get("__index") == "case" and user_classification:
                case_service.filter_case_items_by_classification(source, user_classification)

            items.append(source)

    return items


def search(  # noqa: C901
    indexes: str | list[str],
    query: str | None = None,
    deep_paging_id: str | None = None,
    filters: list[str] | str | None = None,
    offset: int = DEFAULT_OFFSET,
    rows: int = DEFAULT_ROW_SIZE,
    sort: str | dict[str, str] | list[dict[str, str]] | None = None,
    fl: str | list[str] | None = None,
    timeout: int | None = None,
    track_total_hits: bool = False,
    metadata: list[str] | None = None,
    user: User | None = None,
) -> SearchResult[dict[str, Any]]:
    """Search through specified index for a given query. Uses lucene search syntax for query.

    Variables:
    indexes  =>   Comma-separated list of indexes to search in (hit, event,...)

    Arguments:
    query: Query to search for
    deep_paging_id   : ID of the next page or * to start deep paging
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

    client: Elasticsearch = datastore().ds.client
    parsed_indexes = _normalize_indexes(indexes)

    if filters is None:
        parsed_filters: list[str] = []
    elif isinstance(filters, str):
        parsed_filters = [filters]
    else:
        parsed_filters = filters

    # NOTE: This means index searches must be either ALL access controlled or none of them have access control.
    # Otherwise, the access control requirements on one index will cause the other index to return no items.
    # This is pretty reasonable constraint, as all the relevant, searchable items support classifications.
    if user and user.access_control and has_access_control(indexes):
        parsed_filters.append(user.access_control)

    if query is None:
        query = "id:*"

    if sort is None:
        sort = DEFAULT_SORT

    source_fields: list[str] | None
    if fl is None:
        source_fields = None
    elif isinstance(fl, str):
        source_fields = [field.strip() for field in fl.split(",") if field.strip()]
    else:
        source_fields = [field.strip() for field in fl if field.strip()]

    params: dict[str, Any] = {}
    if deep_paging_id is not None:
        params["scroll"] = SCROLL_TIMEOUT
    elif track_total_hits:
        params["track_total_hits"] = True

    if timeout is not None:
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
        "items": _format_items(hits, user.classification if user else None),
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
