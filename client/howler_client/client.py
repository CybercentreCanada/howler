import sys

from howler_client.common.utils import walk_api_path
from howler_client.connection import Connection
from howler_client.module.bundle import Bundle
from howler_client.module.help import Help
from howler_client.module.hit import Hit
from howler_client.module.search import Search
from howler_client.module.user import User

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


class Client(object):
    "Main howler client object, wrapping API calls"

    def __init__(self: Self, connection: Connection):
        self._connection: Connection = connection

        self.help = Help(self._connection)
        self.search = Search(self._connection)
        self.hit = Hit(self._connection, self.search)
        self.bundle = Bundle(self._connection, self.hit)
        self.user = User(self._connection)

        paths: list[str] = []
        walk_api_path(self, [""], paths)

        self.__doc__ = "Client provides the following methods:\n\n" + "\n".join(["\n".join(p + "\n") for p in paths])
