import sys
from typing import TYPE_CHECKING, Any, List

from howler_client.common.utils import api_path

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

if TYPE_CHECKING:
    from howler_client import Connection


class Comment(object):
    """Help related endpoints"""

    def __init__(self: Self, connection: "Connection"):
        self._connection = connection

    def add(self: Self, hit_id: str, comment: str) -> dict[str, Any]:
        """Add a comment to a hit and return it

        Args:
            hit_id (str): ID of the hit
            comment: content of the comment

        Returns:
            dict[str, Any]: The corresponding hit data
        """
        return self._connection.post(api_path("hit", hit_id, "comments"), json={"value": comment})

    def edit(self: Self, hit_id: str, comment: str, comment_id: str) -> dict[str, Any]:
        """Update a comment on a hit and return it

        Args:
            hit_id (str): ID of the hit
            comment_id (str): ID of the comment that need to be updated
            comment: content of the comment

        Returns:
            dict[str, Any]: The corresponding hit data
        """
        return self._connection.put(
            api_path("hit", hit_id, "comments", comment_id),
            json={"value": comment},
        )

    def delete(self: Self, hit_id: str, comment_ids: List[str]) -> dict[str, Any]:
        """Delete a comment on a hit and return it

        Args:
            hit_id (str): ID of the hit
            comment_ids (List[str]): list of all comment ids that need to be removed

        Returns:
            dict[str, Any]: The corresponding hit data
        """
        return self._connection.delete(api_path("hit", hit_id, "comments"), json=comment_ids)
