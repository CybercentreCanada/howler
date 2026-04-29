"""Client module for the v2 Search API."""

import json
import sys
from typing import TYPE_CHECKING, Any, Optional

from howler_client.common.utils import api_path_v2

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

if TYPE_CHECKING:
    from howler_client import Connection


class SearchV2(object):
    """Search operations via the v2 API.

    Unlike the v1 search module, v2 supports searching across multiple
    comma-separated indexes in a single request.
    """

    def __init__(self: Self, connection: "Connection"):
        self._connection = connection

    def __call__(
        self: Self,
        indexes: str,
        query: str,
        filters: Optional[list[str]] = None,
        fl: Optional[str] = None,
        offset: int = 0,
        rows: int = 25,
        sort: Optional[str] = None,
        timeout: Optional[int] = None,
        use_archive: bool = False,
        track_total_hits: bool = False,
        metadata: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Search across one or more indexes.

        Args:
            indexes: Comma-separated index names (e.g. ``"hit"`` or ``"hit,observable"``).
            query: Lucene query string.
            filters: Additional filter queries.
            fl: Comma-separated list of fields to return.
            offset: Result offset.
            rows: Number of results per page.
            sort: Sort specification (e.g. ``"event.created desc"``).
            timeout: Maximum execution time in milliseconds.
            use_archive: Include archived data.
            track_total_hits: Track exact total hit count.
            metadata: Additional features to include (e.g. ``["dossiers"]``).

        Returns:
            Search result with ``total``, ``offset``, ``rows``, ``items``.
        """
        body: dict[str, Any] = {"query": query, "offset": offset, "rows": rows}

        if filters:
            body["filters"] = filters
        if fl:
            body["fl"] = fl
        if sort:
            body["sort"] = sort
        if timeout is not None:
            body["timeout"] = timeout
        if use_archive:
            body["use_archive"] = True
        if track_total_hits:
            body["track_total_hits"] = True
        if metadata:
            body["metadata"] = metadata

        return self._connection.post(api_path_v2("search", indexes), data=json.dumps(body))

    def explain(self: Self, index: str, query: str) -> dict[str, Any]:
        """Explain a Lucene query against an index.

        Args:
            index: Single index name (e.g. ``"hit"``).
            query: Lucene query to explain.

        Returns:
            Explanation with ``valid`` and ``explanations`` fields.
        """
        return self._connection.post(api_path_v2("search", index, "explain"), json={"query": query})

    def count(
        self: Self,
        index: str,
        query: str,
        filters: Optional[list[str]] = None,
        timeout: Optional[int] = None,
        use_archive: bool = False,
    ) -> int:
        """Count documents matching a query.

        Args:
            index: Single index name (e.g. ``"hit"``).
            query: Lucene query string.
            filters: Additional filter queries.
            timeout: Maximum execution time in milliseconds.
            use_archive: Include archived data.

        Returns:
            Number of matching documents.
        """
        body: dict[str, Any] = {"query": query}

        if filters:
            body["filters"] = filters
        if timeout is not None:
            body["timeout"] = timeout
        if use_archive:
            body["use_archive"] = True

        return self._connection.post(api_path_v2("search", "count", index), json=body)

    def facet(
        self: Self,
        indexes: str,
        fields: list[str],
        query: str = "*:*",
        mincount: Optional[int] = None,
        rows: Optional[int] = None,
        filters: Optional[list[str]] = None,
    ) -> dict[str, dict[str, int]]:
        """Perform field faceting across one or more indexes.

        Args:
            indexes: Comma-separated index names.
            fields: List of fields to facet on.
            query: Lucene query to filter documents.
            mincount: Minimum count for a value to be returned.
            rows: Maximum number of facet values per field.
            filters: Additional filter queries.

        Returns:
            Dictionary mapping each field to its value counts.
        """
        body: dict[str, Any] = {"query": query, "fields": fields}

        if mincount is not None:
            body["mincount"] = mincount
        if rows is not None:
            body["rows"] = rows
        if filters:
            body["filters"] = filters

        return self._connection.post(api_path_v2("search", "facet", indexes), json=body)
