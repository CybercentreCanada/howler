"""Unit tests for the V2 client container and api_path_v2."""

from unittest.mock import MagicMock

from howler_client.common.utils import api_path_v2
from howler_client.module.case import Case
from howler_client.module.ingest import Ingest
from howler_client.module.search_v2 import SearchV2
from howler_client.module.v2 import V2


class TestApiPathV2:
    def test_basic_path(self):
        assert api_path_v2("case") == "api/v2/case"

    def test_path_with_args(self):
        assert api_path_v2("case", "abc", "items") == "api/v2/case/abc/items"

    def test_path_with_kwargs(self):
        result = api_path_v2("ingest", "hit", replace="true")
        assert result == "api/v2/ingest/hit?replace=true"

    def test_path_with_none_kwarg_omitted(self):
        result = api_path_v2("ingest", "hit", replace=None)
        assert result == "api/v2/ingest/hit"


class TestV2Container:
    def test_exposes_case_module(self):
        conn = MagicMock()
        v2 = V2(conn)
        assert isinstance(v2.case, Case)

    def test_exposes_ingest_module(self):
        conn = MagicMock()
        v2 = V2(conn)
        assert isinstance(v2.ingest, Ingest)

    def test_exposes_search_module(self):
        conn = MagicMock()
        v2 = V2(conn)
        assert isinstance(v2.search, SearchV2)
