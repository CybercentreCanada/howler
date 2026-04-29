"""V2 API module container.

Provides access to v2-only endpoints: ``case``, ``ingest``, and ``search``.
"""

import sys
from typing import TYPE_CHECKING

from howler_client.module.v2.case import Case
from howler_client.module.v2.ingest import Ingest
from howler_client.module.v2.search import SearchV2

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

if TYPE_CHECKING:
    from howler_client import Connection


class V2(object):
    """Access v2 API endpoints."""

    def __init__(self: Self, connection: "Connection"):
        self._connection = connection

        self.case = Case(connection)
        self.ingest = Ingest(connection)
        self.search = SearchV2(connection)
