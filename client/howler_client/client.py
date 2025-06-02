from howler_client.connection import Connection
from howler_client.common.utils import walk_api_path
from howler_client.module.bundle import Bundle
from howler_client.module.help import Help
from howler_client.module.hit import Hit
from howler_client.module.search import Search
from howler_client.module.user import User


class Client(object):
    def __init__(self, connection):
        self._connection: Connection = connection

        self.help = Help(self._connection)
        self.search = Search(self._connection)
        self.hit = Hit(self._connection, self.search)
        self.bundle = Bundle(self._connection, self.hit)
        self.user = User(self._connection)

        paths = []
        walk_api_path(self, [""], paths)

        self.__doc__ = "Client provides the following methods:\n\n" + "\n".join(
            ["\n".join(p + [""]) for p in paths]
        )
