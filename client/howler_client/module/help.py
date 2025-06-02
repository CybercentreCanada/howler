from typing import TYPE_CHECKING
from howler_client.common.utils import api_path_by_module

if TYPE_CHECKING:
    from howler_client import Connection


class Help(object):
    """Help related endpoints"""

    def __init__(self, connection: "Connection"):
        self._connection = connection

    def classification_definition(self):
        """
        Return the current system classification definition
        """
        return self._connection.get(api_path_by_module(self))
