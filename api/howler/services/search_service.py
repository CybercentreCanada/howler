from __future__ import annotations

from typing import Any

import elasticsearch
from elasticsearch import Elasticsearch

from howler.common.loader import APP_NAME, datastore
from howler.datastore.collection import parse_sort
from howler.datastore.exceptions import SearchException, SearchRetryException
from howler.datastore.types import SearchResult

DEFAULT_OFFSET = 0
DEFAULT_ROW_SIZE = 25
DEFAULT_SORT: list[dict[str, str]] = [{"_id": "asc"}]
DEFAULT_SEARCH_FIELD = "__text__"
SCROLL_TIMEOUT = "5m"


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
            normalized_indexes.append(f"{APP_NAME}-{index}_hot")

    return ",".join(normalized_indexes)


def _format_items(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
) -> SearchResult[dict[str, Any]]:
    """Search through specified index for a given query. Uses lucene search syntax for query.

    Variables:
    indexes  =>   Comma-separated list of indexes to search in (hit, observable,...)

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
        "items": _format_items(hits),
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
        except elasticsearch.exceptions.NotFoundError:
            pass
        next_deep_paging_id = None

    if next_deep_paging_id is not None:
        response["next_deep_paging_id"] = next_deep_paging_id

    return response


if __name__ == "__main__":
    results = search("hit,observable", "howler.id:*", sort="timestamp desc", rows=250)

    indexes = {result["_index"] for result in results["items"]}

    print(indexes)  # noqa: T201
