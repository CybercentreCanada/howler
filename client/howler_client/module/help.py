import sys
from typing import TYPE_CHECKING

from howler_client.common.utils import api_path

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

if TYPE_CHECKING:
    from howler_client import Connection


class Help(object):
    """Help related endpoints"""

    def __init__(self: Self, connection: "Connection"):
        self._connection = connection

    def classification_definition(self):
        """Return the current system classification definition"""
        return self._connection.get(api_path("help", "classification_definition"))
