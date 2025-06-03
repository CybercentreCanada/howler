import sys
from typing import Any, Literal

from howler_client.common.utils import api_path

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


class User(object):
    """Methods related to Howler users"""

    def __init__(self, connection):
        self._connection = connection

    def __call__(self: Self, username: str) -> dict[str, Any]:
        """Return the profile for the given username

        Args:
            username (str): User key. (string).

        Returns:
            dict[str, Any]: The user account corresponding to the given username
        """
        return self._connection.get(api_path("user", username))

    def add(self: Self, username: str, user_data: dict[str, Any]) -> dict[Literal["success"], bool]:
        """Add a user to the system

        Args:
            username (str): Name of the user to add to the system
            user_data (dict[str, Any]): Profile data of the user to add

        Returns:
            dict[Literal["success"], bool]: Whether creating the user succeeded
        """
        return self._connection.post(api_path("user", username), json=user_data)

    def delete(self: Self, username: str) -> dict[Literal["success"], bool]:
        """Remove the account specified by the username.

        Args:
            str: Name of the user to remove from the system

        Returns:
            dict[Literal["success"], bool]: Whether the delete succeeded
        """
        return self._connection.delete(api_path("user", username))

    def list(
        self: Self,
        query: str = "*:*",
        rows: int = 10,
        offset: int = 0,
        sort: str = "uname asc",
        **kwargs,
    ) -> dict[str, Any]:
        """List users of the system

        Args:
            query (_type_, optional): Filter to apply to the user list. Defaults to "*:*".
            rows (int, optional): Total number of users returned. Defaults to 10.
            offset (int, optional): Offset in the user index. Defaults to 0.
            sort (str, optional): Sort order. Defaults to "uname asc".

        Returns:
            dict[str, Any]: Result of listing the users
        """
        return self._connection.get(
            api_path(
                "search",
                "user",
                query=query,
                rows=rows,
                offset=offset,
                sort=sort,
                **kwargs,
            )
        )

    def update(self: Self, username: str, user_data: dict[str, Any]) -> dict[Literal["success"], bool]:
        """Update a user profile in the system.

        Args:
            username (str): Name of the user to update in the system
            user_data (dict[str, Any]): Profile data of the user to update

        Returns:
            dict[Literal["success"], bool]: Whether the update succeeded
        """
        return self._connection.put(api_path("user", username), json=user_data)

    def whoami(self: Self) -> dict[str, Any]:
        "Return the currently logged in user"
        return self._connection.get(api_path("user", "whoami"))
