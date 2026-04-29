"""Client module for the v2 Ingest API."""

import json
import sys
from typing import TYPE_CHECKING, Any, Literal, Union

from howler_client.common.utils import ClientError, api_path_v2

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

if TYPE_CHECKING:
    from howler_client import Connection

UPDATE_OPERATIONS = [
    "SET",
    "INC",
    "DEC",
    "MAX",
    "MIN",
    "APPEND",
    "APPEND_IF_MISSING",
    "REMOVE",
    "DELETE",
]


class Ingest(object):
    """Operations for ingesting records via the v2 API.

    Unlike the v1 ``hit`` module, v2 ingest supports multiple indexes
    (``hit`` and ``observable``) and enqueues new records for correlation
    processing.
    """

    def __init__(self: Self, connection: "Connection"):
        self._connection = connection

    def create(
        self: Self,
        index: str,
        data: Union[dict[str, Any], list[dict[str, Any]]],
    ) -> list[str]:
        """Create one or more records in the given index.

        Args:
            index: Target index (``hit`` or ``observable``).
            data: A single record dict or a list of record dicts.

        Returns:
            List of created record IDs.
        """
        if not isinstance(data, list):
            data = [data]

        return self._connection.post(
            api_path_v2("ingest", index),
            data=json.dumps(data),
            headers={"Content-Type": "application/json"},
        )

    def delete(self: Self, indexes: str, ids: list[str]) -> dict[str, Any]:
        """Delete records across one or more indexes.

        Args:
            indexes: Comma-separated index names (e.g. ``"hit"`` or ``"hit,observable"``).
            ids: List of record IDs to delete.

        Returns:
            Dictionary with deletion results.
        """
        return self._connection.delete(api_path_v2("ingest", indexes), json=ids)

    def validate(
        self: Self,
        index: str,
        data: Union[dict[str, Any], list[dict[str, Any]]],
    ) -> dict[str, list[dict[str, Any]]]:
        """Validate records against an index schema without persisting.

        Args:
            index: Target index (``hit`` or ``observable``).
            data: A single record dict or a list of record dicts.

        Returns:
            Dictionary with ``valid`` and ``invalid`` lists.
        """
        if not isinstance(data, list):
            data = [data]

        return self._connection.post(
            api_path_v2("ingest", index, "validate"),
            data=json.dumps(data),
            headers={"Content-Type": "application/json"},
        )

    def overwrite(
        self: Self,
        index: str,
        record_id: str,
        new_data: dict[str, Any],
        replace: bool = False,
    ) -> dict[str, Any]:
        """Overwrite (patch) a single record.

        Args:
            index: Index of the record (e.g. ``"hit"``).
            record_id: ID of the record to overwrite.
            new_data: Partial record data to merge.
            replace: If ``True``, lists are replaced instead of merged.

        Returns:
            The updated record data.
        """
        if not isinstance(new_data, dict):
            raise TypeError("new_data must be a dict.")

        return self._connection.request(
            self._connection.session.patch,
            api_path_v2("ingest", index, record_id, "overwrite", replace=replace if replace else None),
            lambda resp: resp.json()["api_response"],
            json=new_data,
        )

    def update_by_query(
        self: Self,
        indexes: str,
        query: str,
        operations: list[tuple[str, str, Any]],
    ) -> dict[Literal["success"], bool]:
        """Bulk update records matching a query.

        Args:
            indexes: Comma-separated index names.
            query: Lucene query selecting records to update.
            operations: List of ``(operation, key, value)`` tuples.
                Valid operations: SET, INC, DEC, MAX, MIN, APPEND,
                APPEND_IF_MISSING, REMOVE, DELETE.

        Returns:
            Whether the operation succeeded.
        """
        if not isinstance(operations, list):
            raise TypeError("operations must be a list.")

        for op in operations:
            if not isinstance(op, tuple):
                raise TypeError("Each operation must be a tuple.")
            if op[0] not in UPDATE_OPERATIONS:
                raise ClientError(
                    f"Invalid operation '{op[0]}' — must be one of {', '.join(UPDATE_OPERATIONS)}",
                    400,
                )

        return self._connection.put(
            api_path_v2("ingest", indexes, "update"),
            json={"query": query, "operations": operations},
        )
