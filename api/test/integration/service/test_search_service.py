from unittest.mock import patch

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
        "name asc",
        {"name": "asc"},
        [{"name": "asc"}],
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
        assert len(list(item.keys())) == 2


def test_search_with_fl_list(datastore):
    result = search_service.search("user", query="uname:*", fl=["uname", "name"], rows=5)

    assert len(result["items"]) > 0
    for item in result["items"]:
        assert "uname" in item
        assert "name" in item
        assert len(list(item.keys())) == 2


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
