from unittest.mock import MagicMock, patch

import elasticsearch
import pytest

from howler.common.loader import APP_NAME
from howler.datastore.exceptions import SearchException, SearchRetryException
from howler.odm.random_data import (
    create_hits,
    create_observables,
    create_users,
    wipe_hits,
    wipe_observables,
    wipe_users,
)
from howler.services import search_service

TEST_SIZE = 12


@pytest.fixture(scope="module")
def datastore(datastore_connection):
    ds = datastore_connection

    try:
        wipe_users(ds)
        create_users(ds)
        if ds.hit.search("howler.id:*")["total"] != 40:
            wipe_hits(ds)
            create_hits(ds, hit_count=40)

        if ds.observable.search("howler.id:*")["total"] != 40:
            wipe_observables(ds)
            create_observables(ds, observable_count=40)

        for index in range(TEST_SIZE - 5):
            user = ds.user.get("user")
            user.uname = f"svc_test_{index}"
            user.name = f"SVC_TEST_{index}"
            ds.user.save(user.uname, user)

        ds.user.commit()
        ds.hit.commit()
        ds.observable.commit()

        yield ds
    finally:
        wipe_users(ds)
        create_users(ds)


def test_normalize_indexes_string():
    assert search_service._normalize_indexes("user,hit") == f"{APP_NAME}-user_hot,{APP_NAME}-hit_hot"


def test_normalize_indexes_list_and_special_values():
    assert (
        search_service._normalize_indexes(["*", "_all", "custom-index", "observable*"])
        == "*,_all,custom-index,observable*"
    )


@pytest.mark.parametrize("indexes", ["", " , ", [], [" "]])
def test_normalize_indexes_fails_on_empty(indexes):
    with pytest.raises(SearchException, match="No indexes were provided"):
        search_service._normalize_indexes(indexes)


def test_format_items():
    items = search_service._format_items(
        [
            {
                "_id": "id-1",
                "_index": "idx-1",
                "_score": 1.23,
                "_source": {"uname": "admin", "name": "Administrator"},
            }
        ]
    )

    assert items[0]["uname"] == "admin"
    assert items[0]["name"] == "Administrator"


def test_search_defaults(datastore):
    result = search_service.search("hit", query="howler.id:*")

    assert result["total"] >= TEST_SIZE
    assert result["offset"] == search_service.DEFAULT_OFFSET
    assert result["rows"] == search_service.DEFAULT_ROW_SIZE
    assert len(result["items"]) > 0


def test_search_query_none_uses_wildcard(datastore):
    result = search_service.search("hit", query=None, rows=5)

    assert result["total"] >= TEST_SIZE
    assert len(result["items"]) <= 5


def test_search_with_filters_string(datastore):
    result = search_service.search("user", query="uname:*", filters="uname:admin", rows=25)

    assert result["total"] >= 1
    assert all(item.get("uname") == "admin" for item in result["items"])


def test_search_with_filters_list(datastore):
    result = search_service.search("user", query="uname:*", filters=["uname:admin", 'name:"Michael Scott"'], rows=25)

    assert result["total"] >= 1
    assert all(item.get("uname") == "admin" for item in result["items"])


def test_search_with_offset_and_rows(datastore):
    result = search_service.search("user", query="uname:*", offset=1, rows=3)

    assert result["offset"] == 1
    assert result["rows"] == 3
    assert len(result["items"]) <= 3


@pytest.mark.parametrize(
    "sort_value",
    [
        "uname asc",
        {"uname": "asc"},
        [{"uname": "asc"}],
    ],
)
def test_search_with_sort_variants(datastore, sort_value):
    result = search_service.search("user", query="uname:*", sort=sort_value, rows=5)

    assert result["total"] >= TEST_SIZE
    assert len(result["items"]) <= 5


def test_search_with_fl_string(datastore):
    result = search_service.search("user", query="uname:*", fl="uname,name", rows=5)

    assert len(result["items"]) > 0
    for item in result["items"]:
        assert "uname" in item
        assert "name" in item
        assert "__index" in item
        assert item["__index"] == "user"
        assert len(list(item.keys())) == 3


def test_search_with_fl_list(datastore):
    result = search_service.search("user", query="uname:*", fl=["uname", "name"], rows=5)

    assert len(result["items"]) > 0
    for item in result["items"]:
        assert "uname" in item
        assert "name" in item
        assert "__index" in item
        assert item["__index"] == "user"
        assert len(list(item.keys())) == 3


def test_search_with_empty_fl_string(datastore):
    result = search_service.search("user", query="uname:*", fl="", rows=5)

    assert len(result["items"]) > 0
    for item in result["items"]:
        assert item.get("uname") is not None


def test_search_with_timeout_and_track_total_hits(datastore):
    result = search_service.search("user", query="uname:*", timeout=2000, track_total_hits=True, rows=5)

    assert result["total"] >= TEST_SIZE
    assert len(result["items"]) <= 5


def test_search_with_metadata_argument_ignored(datastore):
    result = search_service.search("user", query="uname:*", metadata=["template", "overview"], rows=3)

    assert len(result["items"]) <= 3
    for item in result["items"]:
        assert "__template" not in item
        assert "__overview" not in item


def test_search_with_deep_paging(datastore):
    first_page = search_service.search("user", query="uname:*", rows=2, deep_paging_id="*")

    assert len(first_page["items"]) <= 2

    deep_paging_id = first_page.get("next_deep_paging_id")
    if deep_paging_id:
        second_page = search_service.search("user", query="uname:*", rows=2, deep_paging_id=deep_paging_id)
        assert len(second_page["items"]) <= 2


def test_search_raises_search_retry_exception_on_connection_error(datastore):
    client = search_service.datastore().ds.client

    with patch.object(client, "search", side_effect=elasticsearch.exceptions.ConnectionError("N/A", "down")):
        with pytest.raises(SearchRetryException):
            search_service.search("user", query="uname:*")


def test_search_raises_search_retry_exception_on_timeout(datastore):
    client = search_service.datastore().ds.client

    with patch.object(client, "search", side_effect=elasticsearch.exceptions.ConnectionTimeout("N/A", "slow")):
        with pytest.raises(SearchRetryException):
            search_service.search("user", query="uname:*")


def test_search_raises_search_exception_on_unexpected_error(datastore):
    client = search_service.datastore().ds.client

    with patch.object(client, "search", side_effect=RuntimeError("unexpected")):
        with pytest.raises(SearchException, match="unexpected"):
            search_service.search("user", query="uname:*")


def test_search_clears_scroll_on_deep_paging_end(datastore):
    client = search_service.datastore().ds.client

    with patch.object(client, "scroll", return_value={"hits": {"total": {"value": 0}, "hits": []}}):
        with patch.object(client, "clear_scroll") as clear_scroll:
            search_service.search("user", query="uname:*", deep_paging_id="scroll-token", rows=10)

            clear_scroll.assert_called_once_with(scroll_id="scroll-token")


def test_search_ignores_not_found_on_clear_scroll(datastore):
    client = search_service.datastore().ds.client

    with patch.object(client, "scroll", return_value={"hits": {"total": {"value": 0}, "hits": []}}):
        with patch.object(client, "clear_scroll", side_effect=elasticsearch.exceptions.NotFoundError("404", "", {})):
            result = search_service.search("user", query="uname:*", deep_paging_id="missing-scroll", rows=10)

    assert result["total"] == 0
    assert result["items"] == []


def test_search_clears_next_scroll_when_last_page(datastore):
    client = search_service.datastore().ds.client

    scroll_result = {
        "_scroll_id": "next-token",
        "hits": {
            "total": {"value": 1},
            "hits": [
                {
                    "_id": "admin",
                    "_index": f"{APP_NAME}-user_hot",
                    "_score": 1.0,
                    "_source": {"uname": "admin"},
                }
            ],
        },
    }

    with patch.object(client, "search", return_value=scroll_result):
        with patch.object(client, "clear_scroll") as clear_scroll:
            result = search_service.search("user", query="uname:*", deep_paging_id="*", rows=10)

    clear_scroll.assert_called_once_with(scroll_id="next-token")
    assert "next_deep_paging_id" not in result


def test_search_multiple(datastore):
    result = search_service.search(
        indexes="hit",
        query="howler.id:*",
        sort="timestamp desc",
        rows=80,
    )

    assert result["rows"] == 40
    assert len(result["items"]) > 0
    assert len(result["items"]) <= 40

    result = search_service.search(
        indexes="observable",
        query="howler.id:*",
        sort="timestamp desc",
        rows=80,
    )

    assert result["rows"] == 40
    assert len(result["items"]) > 0
    assert len(result["items"]) <= 40

    result = search_service.search(
        indexes="hit,observable",
        query="howler.id:*",
        sort="timestamp desc",
        rows=80,
    )

    assert result["rows"] == 80
    assert len(result["items"]) > 0
    assert len(result["items"]) <= 80


class TestNormalizeIndexes:
    """Tests for search_service._normalize_indexes."""

    def test_single_index_adds_prefix_and_suffix(self):
        """A plain index name gets the APP_NAME prefix and _hot suffix."""
        result = search_service._normalize_indexes("hit")

        assert result.endswith("-hit_hot")

    def test_multiple_indexes_comma_separated(self):
        """Comma-separated indexes are each normalized."""
        result = search_service._normalize_indexes("hit,observable")

        parts = result.split(",")
        assert len(parts) == 2
        assert parts[0].endswith("-hit_hot")
        assert parts[1].endswith("-observable_hot")

    def test_wildcard_preserved(self):
        """Wildcard '*' is kept as-is."""
        result = search_service._normalize_indexes("*")

        assert result == "*"

    def test_exclusion_pattern_preserved(self):
        """Indexes with a dash (exclusion pattern) are kept as-is."""
        result = search_service._normalize_indexes("custom-index")

        assert result == "custom-index"

    def test_list_input(self):
        """A list of indexes is handled correctly."""
        result = search_service._normalize_indexes(["hit", "observable"])

        parts = result.split(",")
        assert len(parts) == 2
        assert all(p.endswith("_hot") for p in parts)

    def test_empty_string_raises(self):
        """An empty string raises SearchException."""
        with pytest.raises(SearchException):
            search_service._normalize_indexes("")

    def test_empty_list_raises(self):
        """An empty list raises SearchException."""
        with pytest.raises(SearchException):
            search_service._normalize_indexes([])

    def test_whitespace_stripped(self):
        """Leading/trailing whitespace in index names is stripped."""
        result = search_service._normalize_indexes("  hit , observable  ")

        parts = result.split(",")
        assert len(parts) == 2
        assert all(p.endswith("_hot") for p in parts)

    def test_all_keyword_preserved(self):
        """The '_all' keyword is preserved as-is."""
        result = search_service._normalize_indexes("_all")

        assert result == "_all"

    def test_mixed_wildcard_and_plain(self):
        """Mix of wildcards and plain indexes normalizes correctly."""
        result = search_service._normalize_indexes("*,hit")

        parts = result.split(",")
        assert parts[0] == "*"
        assert parts[1].endswith("-hit_hot")


# ---------------------------------------------------------------------------
# _format_items
# ---------------------------------------------------------------------------


class TestFormatItems:
    """Tests for search_service._format_items."""

    def test_extracts_source(self):
        """Each hit's _source is returned as an item."""
        hits = [
            {"_source": {"howler": {"id": "hit-1"}}, "_index": "howler-hit_hot"},
        ]

        items = search_service._format_items(hits)

        assert len(items) == 1
        assert items[0]["howler"]["id"] == "hit-1"

    def test_sets_index_field(self):
        """The __index field is set to the cleaned-up index name."""
        hits = [
            {"_source": {"howler": {"id": "hit-1"}}, "_index": "howler-hit_hot"},
        ]

        items = search_service._format_items(hits)

        assert items[0]["__index"] == "hit"

    def test_skips_hits_without_source(self):
        """Hits without _source are not included in the result."""
        hits = [
            {"_index": "howler-hit_hot"},
            {"_source": {"howler": {"id": "hit-2"}}, "_index": "howler-hit_hot"},
        ]

        items = search_service._format_items(hits)

        assert len(items) == 1
        assert items[0]["howler"]["id"] == "hit-2"

    def test_no_index_field_omits_index(self):
        """When _index is missing from a hit, __index is not set."""
        hits = [{"_source": {"howler": {"id": "hit-1"}}}]

        items = search_service._format_items(hits)

        assert "__index" not in items[0]

    def test_empty_hits_returns_empty_list(self):
        """An empty hits list returns an empty items list."""
        assert search_service._format_items([]) == []


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


class TestSearch:
    """Tests for search_service.search."""

    @patch("howler.services.search_service.datastore")
    def test_basic_search_returns_result(self, mock_ds_fn):
        """A basic search returns formatted results with total, offset, rows, items."""
        mock_client = MagicMock()
        mock_ds = MagicMock()
        mock_ds.ds.client = mock_client
        mock_ds_fn.return_value = mock_ds

        mock_client.search.return_value = {
            "hits": {
                "total": {"value": 1},
                "hits": [
                    {"_source": {"howler": {"id": "hit-1"}}, "_index": "howler-hit_hot"},
                ],
            }
        }

        result = search_service.search("hit", query="howler.id:*")

        assert result["total"] == 1
        assert result["offset"] == 0
        assert result["rows"] == 1
        assert len(result["items"]) == 1
        assert result["items"][0]["howler"]["id"] == "hit-1"

    @patch("howler.services.search_service.datastore")
    def test_search_default_query(self, mock_ds_fn):
        """When query is None, the default 'id:*' query is used."""
        mock_client = MagicMock()
        mock_ds = MagicMock()
        mock_ds.ds.client = mock_client
        mock_ds_fn.return_value = mock_ds

        mock_client.search.return_value = {"hits": {"total": {"value": 0}, "hits": []}}

        search_service.search("hit", query=None)

        call_kwargs = mock_client.search.call_args
        query_string = call_kwargs.kwargs["query"]["bool"]["must"]["query_string"]["query"]
        assert query_string == "id:*"

    @patch("howler.services.search_service.datastore")
    def test_search_with_filters(self, mock_ds_fn):
        """Filters are included in the bool query's filter clause."""
        mock_client = MagicMock()
        mock_ds = MagicMock()
        mock_ds.ds.client = mock_client
        mock_ds_fn.return_value = mock_ds

        mock_client.search.return_value = {"hits": {"total": {"value": 0}, "hits": []}}

        search_service.search("hit", query="*:*", filters=["howler.status:open", "event.kind:alert"])

        call_kwargs = mock_client.search.call_args
        filter_clauses = call_kwargs.kwargs["query"]["bool"]["filter"]
        assert len(filter_clauses) == 2

    @patch("howler.services.search_service.datastore")
    def test_search_with_string_filter(self, mock_ds_fn):
        """A single string filter is converted to a list."""
        mock_client = MagicMock()
        mock_ds = MagicMock()
        mock_ds.ds.client = mock_client
        mock_ds_fn.return_value = mock_ds

        mock_client.search.return_value = {"hits": {"total": {"value": 0}, "hits": []}}

        search_service.search("hit", query="*:*", filters="howler.status:open")

        call_kwargs = mock_client.search.call_args
        filter_clauses = call_kwargs.kwargs["query"]["bool"]["filter"]
        assert len(filter_clauses) == 1

    @patch("howler.services.search_service.datastore")
    def test_search_with_fl_string(self, mock_ds_fn):
        """A comma-separated fl string is parsed into a source fields list."""
        mock_client = MagicMock()
        mock_ds = MagicMock()
        mock_ds.ds.client = mock_client
        mock_ds_fn.return_value = mock_ds

        mock_client.search.return_value = {"hits": {"total": {"value": 0}, "hits": []}}

        search_service.search("hit", query="*:*", fl="howler.id,event.kind")

        call_kwargs = mock_client.search.call_args
        assert call_kwargs.kwargs["_source"] == ["howler.id", "event.kind"]

    @patch("howler.services.search_service.datastore")
    def test_search_with_fl_list(self, mock_ds_fn):
        """A list fl is passed through as source fields."""
        mock_client = MagicMock()
        mock_ds = MagicMock()
        mock_ds.ds.client = mock_client
        mock_ds_fn.return_value = mock_ds

        mock_client.search.return_value = {"hits": {"total": {"value": 0}, "hits": []}}

        search_service.search("hit", query="*:*", fl=["howler.id"])

        call_kwargs = mock_client.search.call_args
        assert call_kwargs.kwargs["_source"] == ["howler.id"]

    @patch("howler.services.search_service.datastore")
    def test_search_no_fl_omits_source(self, mock_ds_fn):
        """When fl is None, _source is not constrained."""
        mock_client = MagicMock()
        mock_ds = MagicMock()
        mock_ds.ds.client = mock_client
        mock_ds_fn.return_value = mock_ds

        mock_client.search.return_value = {"hits": {"total": {"value": 0}, "hits": []}}

        search_service.search("hit", query="*:*", fl=None)

        call_kwargs = mock_client.search.call_args
        assert "_source" not in call_kwargs.kwargs

    @patch("howler.services.search_service.datastore")
    def test_search_with_timeout(self, mock_ds_fn):
        """A timeout value is formatted as milliseconds string."""
        mock_client = MagicMock()
        mock_ds = MagicMock()
        mock_ds.ds.client = mock_client
        mock_ds_fn.return_value = mock_ds

        mock_client.search.return_value = {"hits": {"total": {"value": 0}, "hits": []}}

        search_service.search("hit", query="*:*", timeout=5000)

        call_kwargs = mock_client.search.call_args
        assert call_kwargs.kwargs["timeout"] == "5000ms"

    @patch("howler.services.search_service.datastore")
    def test_search_connection_error_raises_retry(self, mock_ds_fn):
        """ConnectionError from ES is wrapped in SearchRetryException."""
        mock_client = MagicMock()
        mock_ds = MagicMock()
        mock_ds.ds.client = mock_client
        mock_ds_fn.return_value = mock_ds

        mock_client.search.side_effect = elasticsearch.exceptions.ConnectionError("conn refused")

        with pytest.raises(SearchRetryException):
            search_service.search("hit", query="*:*")

    @patch("howler.services.search_service.datastore")
    def test_search_transport_error_raises_search_exception(self, mock_ds_fn):
        """TransportError from ES is wrapped in SearchException."""
        mock_client = MagicMock()
        mock_ds = MagicMock()
        mock_ds.ds.client = mock_client
        mock_ds_fn.return_value = mock_ds

        mock_client.search.side_effect = elasticsearch.exceptions.TransportError("bad request")

        with pytest.raises(SearchException):
            search_service.search("hit", query="*:*")

    @patch("howler.services.search_service.datastore")
    def test_search_generic_error_raises_search_exception(self, mock_ds_fn):
        """A generic exception from ES is wrapped in SearchException."""
        mock_client = MagicMock()
        mock_ds = MagicMock()
        mock_ds.ds.client = mock_client
        mock_ds_fn.return_value = mock_ds

        mock_client.search.side_effect = RuntimeError("unexpected")

        with pytest.raises(SearchException):
            search_service.search("hit", query="*:*")

    @patch("howler.services.search_service.datastore")
    def test_search_with_offset_and_rows(self, mock_ds_fn):
        """Custom offset and rows are passed to the ES query."""
        mock_client = MagicMock()
        mock_ds = MagicMock()
        mock_ds.ds.client = mock_client
        mock_ds_fn.return_value = mock_ds

        mock_client.search.return_value = {"hits": {"total": {"value": 100}, "hits": []}}

        result = search_service.search("hit", query="*:*", offset=50, rows=10)

        call_kwargs = mock_client.search.call_args
        assert call_kwargs.kwargs["from_"] == 50
        assert call_kwargs.kwargs["size"] == 10
        assert result["offset"] == 50

    @patch("howler.services.search_service.datastore")
    def test_deep_paging_uses_scroll(self, mock_ds_fn):
        """When deep_paging_id='*', client.search is called with scroll param."""
        mock_client = MagicMock()
        mock_ds = MagicMock()
        mock_ds.ds.client = mock_client
        mock_ds_fn.return_value = mock_ds

        mock_client.search.return_value = {
            "hits": {
                "total": {"value": 5},
                "hits": [{"_source": {"howler": {"id": "h1"}}, "_index": "howler-hit_hot"}],
            },
            "_scroll_id": "scroll-abc",
        }

        result = search_service.search("hit", query="*:*", deep_paging_id="*", rows=1)

        call_kwargs = mock_client.search.call_args
        assert call_kwargs.kwargs["scroll"] == search_service.SCROLL_TIMEOUT
        assert result["next_deep_paging_id"] == "scroll-abc"

    @patch("howler.services.search_service.datastore")
    def test_deep_paging_continuation_uses_scroll_api(self, mock_ds_fn):
        """When deep_paging_id is an actual scroll ID, client.scroll is called."""
        mock_client = MagicMock()
        mock_ds = MagicMock()
        mock_ds.ds.client = mock_client
        mock_ds_fn.return_value = mock_ds

        mock_client.scroll.return_value = {
            "hits": {"total": {"value": 5}, "hits": []},
        }

        search_service.search("hit", query="*:*", deep_paging_id="scroll-abc", rows=100)

        mock_client.scroll.assert_called_once()
        mock_client.search.assert_not_called()

    @patch("howler.services.search_service.datastore")
    def test_deep_paging_clears_scroll_when_exhausted(self, mock_ds_fn):
        """When deep paging has no more results, the scroll is cleared."""
        mock_client = MagicMock()
        mock_ds = MagicMock()
        mock_ds.ds.client = mock_client
        mock_ds_fn.return_value = mock_ds

        # Return fewer items than rows → scroll exhausted
        mock_client.search.return_value = {
            "hits": {
                "total": {"value": 2},
                "hits": [
                    {"_source": {"howler": {"id": "h1"}}, "_index": "howler-hit_hot"},
                ],
            },
            "_scroll_id": "scroll-xyz",
        }

        result = search_service.search("hit", query="*:*", deep_paging_id="*", rows=100)

        mock_client.clear_scroll.assert_called_once_with(scroll_id="scroll-xyz")
        assert "next_deep_paging_id" not in result

    @patch("howler.services.search_service.datastore")
    def test_deep_paging_clears_old_scroll_when_none_returned(self, mock_ds_fn):
        """When scroll continuation returns no new scroll ID, old one is cleared."""
        mock_client = MagicMock()
        mock_ds = MagicMock()
        mock_ds.ds.client = mock_client
        mock_ds_fn.return_value = mock_ds

        mock_client.scroll.return_value = {
            "hits": {"total": {"value": 0}, "hits": []},
        }

        search_service.search("hit", query="*:*", deep_paging_id="old-scroll-id")

        mock_client.clear_scroll.assert_called_once_with(scroll_id="old-scroll-id")

    @patch("howler.services.search_service.datastore")
    def test_track_total_hits(self, mock_ds_fn):
        """track_total_hits=True is passed to ES when not deep paging."""
        mock_client = MagicMock()
        mock_ds = MagicMock()
        mock_ds.ds.client = mock_client
        mock_ds_fn.return_value = mock_ds

        mock_client.search.return_value = {"hits": {"total": {"value": 0}, "hits": []}}

        search_service.search("hit", query="*:*", track_total_hits=True)

        call_kwargs = mock_client.search.call_args
        assert call_kwargs.kwargs["track_total_hits"] is True

    @patch("howler.services.search_service.datastore")
    def test_empty_result(self, mock_ds_fn):
        """An ES result with no hits returns zeros and empty items."""
        mock_client = MagicMock()
        mock_ds = MagicMock()
        mock_ds.ds.client = mock_client
        mock_ds_fn.return_value = mock_ds

        mock_client.search.return_value = {"hits": {"total": {"value": 0}, "hits": []}}

        result = search_service.search("hit", query="howler.id:nonexistent")

        assert result["total"] == 0
        assert result["rows"] == 0
        assert result["items"] == []
