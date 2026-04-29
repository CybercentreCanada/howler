"""Unit tests for the v2 SearchV2 client module."""

import json
from unittest.mock import MagicMock

from howler_client.module.search_v2 import SearchV2


def _make_search_module() -> tuple[SearchV2, MagicMock]:
    conn = MagicMock()
    return SearchV2(conn), conn


class TestSearchCall:
    def test_basic_search(self):
        search, conn = _make_search_module()
        conn.post.return_value = {"total": 1, "items": [{"howler": {"id": "h1"}}], "offset": 0, "rows": 1}

        result = search("hit", "howler.id:*")

        assert result["total"] == 1
        conn.post.assert_called_once()
        path = conn.post.call_args[0][0]
        assert "v2" in path
        assert "search/hit" in path

        sent = json.loads(conn.post.call_args[1]["data"])
        assert sent["query"] == "howler.id:*"
        assert sent["offset"] == 0
        assert sent["rows"] == 25

    def test_multi_index_search(self):
        search, conn = _make_search_module()
        conn.post.return_value = {"total": 0, "items": [], "offset": 0, "rows": 0}

        search("hit,observable", "howler.id:*")

        path = conn.post.call_args[0][0]
        assert "search/hit,observable" in path

    def test_search_with_filters(self):
        search, conn = _make_search_module()
        conn.post.return_value = {"total": 0, "items": [], "offset": 0, "rows": 0}

        search("hit", "howler.id:*", filters=["howler.status:open"])

        sent = json.loads(conn.post.call_args[1]["data"])
        assert sent["filters"] == ["howler.status:open"]

    def test_search_with_fl(self):
        search, conn = _make_search_module()
        conn.post.return_value = {"total": 0, "items": [], "offset": 0, "rows": 0}

        search("hit", "howler.id:*", fl="howler.id,event.kind")

        sent = json.loads(conn.post.call_args[1]["data"])
        assert sent["fl"] == "howler.id,event.kind"

    def test_search_with_sort(self):
        search, conn = _make_search_module()
        conn.post.return_value = {"total": 0, "items": [], "offset": 0, "rows": 0}

        search("hit", "howler.id:*", sort="event.created desc")

        sent = json.loads(conn.post.call_args[1]["data"])
        assert sent["sort"] == "event.created desc"

    def test_search_with_timeout(self):
        search, conn = _make_search_module()
        conn.post.return_value = {"total": 0, "items": [], "offset": 0, "rows": 0}

        search("hit", "howler.id:*", timeout=5000)

        sent = json.loads(conn.post.call_args[1]["data"])
        assert sent["timeout"] == 5000

    def test_search_with_metadata(self):
        search, conn = _make_search_module()
        conn.post.return_value = {"total": 0, "items": [], "offset": 0, "rows": 0}

        search("hit", "howler.id:*", metadata=["dossiers"])

        sent = json.loads(conn.post.call_args[1]["data"])
        assert sent["metadata"] == ["dossiers"]

    def test_search_with_offset_and_rows(self):
        search, conn = _make_search_module()
        conn.post.return_value = {"total": 0, "items": [], "offset": 50, "rows": 10}

        search("hit", "howler.id:*", offset=50, rows=10)

        sent = json.loads(conn.post.call_args[1]["data"])
        assert sent["offset"] == 50
        assert sent["rows"] == 10

    def test_search_omits_optional_fields_when_not_set(self):
        search, conn = _make_search_module()
        conn.post.return_value = {"total": 0, "items": [], "offset": 0, "rows": 0}

        search("hit", "howler.id:*")

        sent = json.loads(conn.post.call_args[1]["data"])
        assert "filters" not in sent
        assert "fl" not in sent
        assert "sort" not in sent
        assert "timeout" not in sent
        assert "metadata" not in sent
        assert "use_archive" not in sent
        assert "track_total_hits" not in sent

    def test_search_with_archive_and_track_total(self):
        search, conn = _make_search_module()
        conn.post.return_value = {"total": 0, "items": [], "offset": 0, "rows": 0}

        search("hit", "howler.id:*", use_archive=True, track_total_hits=True)

        sent = json.loads(conn.post.call_args[1]["data"])
        assert sent["use_archive"] is True
        assert sent["track_total_hits"] is True


class TestSearchExplain:
    def test_explain_posts_query(self):
        search, conn = _make_search_module()
        conn.post.return_value = {"valid": True, "explanations": []}

        result = search.explain("hit", "howler.id:*")

        assert result["valid"] is True
        conn.post.assert_called_once()
        path = conn.post.call_args[0][0]
        assert "search/hit/explain" in path
        assert conn.post.call_args[1]["json"] == {"query": "howler.id:*"}


class TestSearchCount:
    def test_count_returns_integer(self):
        search, conn = _make_search_module()
        conn.post.return_value = 42

        result = search.count("hit", "howler.id:*")

        assert result == 42
        path = conn.post.call_args[0][0]
        assert "search/count/hit" in path
        assert conn.post.call_args[1]["json"]["query"] == "howler.id:*"

    def test_count_with_filters(self):
        search, conn = _make_search_module()
        conn.post.return_value = 10

        search.count("hit", "howler.id:*", filters=["howler.status:open"])

        body = conn.post.call_args[1]["json"]
        assert body["filters"] == ["howler.status:open"]

    def test_count_with_timeout(self):
        search, conn = _make_search_module()
        conn.post.return_value = 0

        search.count("hit", "howler.id:*", timeout=1000)

        body = conn.post.call_args[1]["json"]
        assert body["timeout"] == 1000

    def test_count_with_archive(self):
        search, conn = _make_search_module()
        conn.post.return_value = 0

        search.count("hit", "howler.id:*", use_archive=True)

        body = conn.post.call_args[1]["json"]
        assert body["use_archive"] is True

    def test_count_omits_optional_when_not_set(self):
        search, conn = _make_search_module()
        conn.post.return_value = 0

        search.count("hit", "howler.id:*")

        body = conn.post.call_args[1]["json"]
        assert "filters" not in body
        assert "timeout" not in body
        assert "use_archive" not in body


class TestSearchFacet:
    def test_facet_posts_fields_and_query(self):
        search, conn = _make_search_module()
        conn.post.return_value = {"howler.analytic": {"A": 5, "B": 3}}

        result = search.facet("hit", ["howler.analytic"])

        assert result["howler.analytic"]["A"] == 5
        conn.post.assert_called_once()
        path = conn.post.call_args[0][0]
        assert "search/facet/hit" in path
        body = conn.post.call_args[1]["json"]
        assert body["fields"] == ["howler.analytic"]
        assert body["query"] == "*:*"

    def test_facet_multi_index(self):
        search, conn = _make_search_module()
        conn.post.return_value = {}

        search.facet("hit,observable", ["howler.analytic"])

        path = conn.post.call_args[0][0]
        assert "search/facet/hit,observable" in path

    def test_facet_with_optional_params(self):
        search, conn = _make_search_module()
        conn.post.return_value = {}

        search.facet(
            "hit",
            ["howler.analytic"],
            query="howler.status:open",
            mincount=5,
            rows=10,
            filters=["event.kind:alert"],
        )

        body = conn.post.call_args[1]["json"]
        assert body["query"] == "howler.status:open"
        assert body["mincount"] == 5
        assert body["rows"] == 10
        assert body["filters"] == ["event.kind:alert"]

    def test_facet_omits_optional_when_not_set(self):
        search, conn = _make_search_module()
        conn.post.return_value = {}

        search.facet("hit", ["howler.analytic"])

        body = conn.post.call_args[1]["json"]
        assert "mincount" not in body
        assert "rows" not in body
        assert "filters" not in body
