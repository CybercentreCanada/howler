"""Client module for Howler automation actions."""

import sys
from typing import TYPE_CHECKING, Any, List, Literal

from howler_client.common.utils import api_path

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

if TYPE_CHECKING:
    from howler_client import Connection


class Action(object):
    """Operations for managing and executing Howler automation actions."""

    def __init__(self: Self, connection: "Connection"):
        self._connection = connection

    def __call__(self: Self, action_id: str) -> dict[str, Any]:
        """Return an action by ID.

        Args:
            action_id: Unique identifier of the action.

        Returns:
            The action data.
        """
        return self._connection.get(api_path("action", action_id))

    def list(self: Self) -> list[dict[str, Any]]:
        """Return every action visible to the current user."""
        return self._connection.get(api_path("action/"))

    def create(
        self: Self,
        action_data: dict[str, Any],
        refresh: bool | Literal["true", "false", "wait_for"] = False,
    ) -> dict[str, Any]:
        """Create an action.

        Args:
            action_data: Action definition, including ``name``, ``query``, and ``operations``.
            refresh: Whether to refresh the index before returning.

        Returns:
            The created action data.
        """
        return self._connection.post(api_path("action/", refresh=refresh), json=action_data)

    def execute(
        self: Self,
        action_id: str,
        request_id: str,
        query: str | None = None,
    ) -> dict[str, List[dict[str, Any]]]:
        """Execute an action, optionally overriding its configured query.

        Args:
            action_id: Unique identifier of the action to execute.
            request_id: Identifier used to correlate websocket execution updates.
            query: Optional query to run instead of the action's configured query.

        Returns:
            The execution reports grouped by operation ID.
        """
        payload: dict[str, str] = {"request_id": request_id}
        if query is not None:
            payload["query"] = query

        return self._connection.post(api_path("action", action_id, "execute"), json=payload)
