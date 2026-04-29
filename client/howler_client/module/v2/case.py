"""Client module for the v2 Case API."""

import sys
from typing import TYPE_CHECKING, Any, Literal

from howler_client.common.utils import api_path_v2

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

if TYPE_CHECKING:
    from howler_client import Connection


class Case(object):
    """Operations for managing cases via the v2 API."""

    def __init__(self: Self, connection: "Connection"):
        self._connection = connection

    def __call__(self: Self, case_id: str) -> dict[str, Any]:
        """Return a case by ID.

        Args:
            case_id: Unique identifier of the case.

        Returns:
            The case data.
        """
        return self._connection.get(api_path_v2("case", case_id))

    def create(self: Self, case_data: dict[str, Any]) -> dict[str, Any]:
        """Create a new case.

        Args:
            case_data: Dictionary with at least ``title`` and ``summary``.

        Returns:
            The created case data.
        """
        return self._connection.post(api_path_v2("case/"), json=case_data)

    def update(self: Self, case_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        """Update fields on an existing case.

        Args:
            case_id: ID of the case to update.
            updates: Dictionary of fields to update.

        Returns:
            The updated case data.
        """
        return self._connection.put(api_path_v2("case", case_id), json=updates)

    def delete(self: Self, case_ids: list[str]) -> None:
        """Delete one or more cases.

        Args:
            case_ids: List of case IDs to delete.
        """
        return self._connection.delete(api_path_v2("case/"), json=case_ids)

    def hide(self: Self, case_ids: list[str]) -> dict[Literal["success"], bool]:
        """Hide one or more cases.

        Args:
            case_ids: List of case IDs to hide.

        Returns:
            Whether the operation succeeded.
        """
        return self._connection.post(api_path_v2("case/hide"), json=case_ids)

    def append_item(
        self: Self,
        case_id: str,
        item_type: str,
        value: str,
        path: str,
    ) -> dict[str, Any]:
        """Append an item to a case.

        Args:
            case_id: ID of the case.
            item_type: Type of item (``hit``, ``observable``, ``case``, ``table``, ``lead``, or ``reference``).
            value: The ID or reference value for the item.
            path: Display path for the item in the case tree.

        Returns:
            The updated case data.
        """
        return self._connection.post(
            api_path_v2("case", case_id, "items"),
            json={"type": item_type, "value": value, "path": path},
        )

    def delete_items(self: Self, case_id: str, item_values: list[str]) -> dict[str, Any]:
        """Remove items from a case.

        Args:
            case_id: ID of the case.
            item_values: List of item values to remove.

        Returns:
            The updated case data.
        """
        return self._connection.delete(api_path_v2("case", case_id, "items"), json={"values": item_values})

    def rename_item(self: Self, case_id: str, item_value: str, new_path: str) -> dict[str, Any]:
        """Rename (re-path) an item within a case.

        Args:
            case_id: ID of the case.
            item_value: Value identifying the item to rename.
            new_path: New path for the item.

        Returns:
            The updated case data.
        """
        return self._connection.put(
            api_path_v2("case", case_id, "items"),
            json={"value": item_value, "new_path": new_path},
        )

    def add_rule(self: Self, case_id: str, rule_data: dict[str, Any]) -> dict[str, Any]:
        """Add a correlation rule to a case.

        Args:
            case_id: ID of the case.
            rule_data: Rule definition (must include ``query``, ``destination``, ``author``).

        Returns:
            The updated case data.
        """
        return self._connection.post(api_path_v2("case", case_id, "rules"), json=rule_data)

    def delete_rule(self: Self, case_id: str, rule_id: str) -> dict[str, Any]:
        """Delete a correlation rule from a case.

        Args:
            case_id: ID of the case.
            rule_id: ID of the rule to delete.

        Returns:
            The updated case data.
        """
        return self._connection.delete(api_path_v2("case", case_id, "rules", rule_id))

    def update_rule(self: Self, case_id: str, rule_id: str, rule_data: dict[str, Any]) -> dict[str, Any]:
        """Update a correlation rule on a case.

        Args:
            case_id: ID of the case.
            rule_id: ID of the rule to update.
            rule_data: Updated rule fields.

        Returns:
            The updated case data.
        """
        return self._connection.put(api_path_v2("case", case_id, "rules", rule_id), json=rule_data)
