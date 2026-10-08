"""Unit tests for the v1 search scroll client module."""

import json
from unittest.mock import MagicMock

import pytest

from howler_client.common.utils import ClientError
from howler_client.module.search import Search


def _make_search() -> tuple[Search, MagicMock]:
    connection = MagicMock()
    return Search(connection), connection


def test_scroll_open_starts_at_first_page_and_returns_response_unchanged():
    search, connection = _make_search()
    response = {"items": [{"howler": {"id": "hit-1"}}], "next_deep_paging_id": "scroll-1"}
    connection.post.return_value = response

    result = search.scroll.open("hit", "howler.id:*", keep_alive="2m", rows=10)

    assert result is response
    path, request = connection.post.call_args.args[0], connection.post.call_args.kwargs
    assert path == "api/v1/search/hit"
    body = json.loads(request["data"])
    assert body == {
        "query": "howler.id:*",
        "deep_paging_id": "*",
        "scroll": "2m",
        "rows": 10,
    }


def test_scroll_open_validates_index():
    search, connection = _make_search()

    with pytest.raises(ClientError, match="Index event is not searchable"):
        search.scroll.open("event", "*:*", keep_alive="1m")

    connection.post.assert_not_called()


def test_scroll_next_uses_latest_identifier_and_keep_alive():
    search, connection = _make_search()
    first_page = {"items": [{"howler": {"id": "hit-1"}}], "next_deep_paging_id": "scroll-1"}
    second_page = {"items": [{"howler": {"id": "hit-2"}}], "next_deep_paging_id": "scroll-2"}
    final_page = {"items": []}
    connection.post.side_effect = [first_page, second_page, final_page]

    opened = search.scroll.open(
        "hit",
        "howler.id:*",
        keep_alive="2m",
        rows=10,
        filters=["howler.status:open"],
        fl="howler.id",
    )
    advanced = search.scroll.next(opened["next_deep_paging_id"], "3m")
    result = search.scroll.next(advanced["next_deep_paging_id"], "4m")

    assert advanced is second_page
    with pytest.raises(ClientError, match="Unknown or expired scroll ID: scroll-1"):
        search.scroll.next("scroll-1", "3m")
    assert result is final_page
    assert connection.post.call_args_list[1].args[0] == "api/v1/search/hit"
    assert json.loads(connection.post.call_args_list[1].kwargs["data"]) == {
        "query": "howler.id:*",
        "deep_paging_id": "scroll-1",
        "scroll": "3m",
        "rows": 10,
        "filters": ["howler.status:open"],
        "fl": "howler.id",
    }
    assert connection.post.call_args_list[2].args[0] == "api/v1/search/hit"
    assert json.loads(connection.post.call_args_list[2].kwargs["data"]) == {
        "query": "howler.id:*",
        "deep_paging_id": "scroll-2",
        "scroll": "4m",
        "rows": 10,
        "filters": ["howler.status:open"],
        "fl": "howler.id",
    }


def test_scroll_next_returns_empty_final_page_unchanged_and_removes_context():
    search, connection = _make_search()
    first_page = {"items": [{"howler": {"id": "hit-1"}}], "next_deep_paging_id": "scroll-final"}
    response = {"items": [], "total": 1, "rows": 1}
    connection.post.side_effect = [first_page, response]

    opened = search.scroll.open("hit", "howler.id:*", rows=1)
    result = search.scroll.next(opened["next_deep_paging_id"], "1m")

    assert result is response
    assert result["items"] == []
    assert "next_deep_paging_id" not in result
    assert connection.post.call_args_list[1].args[0] == "api/v1/search/hit"
    assert json.loads(connection.post.call_args_list[1].kwargs["data"]) == {
        "query": "howler.id:*",
        "deep_paging_id": "scroll-final",
        "scroll": "1m",
        "rows": 1,
    }
    with pytest.raises(ClientError, match="Unknown or expired scroll ID: scroll-final"):
        search.scroll.next("scroll-final", "1m")


def test_scroll_contexts_keep_independent_request_state():
    search, connection = _make_search()
    connection.post.side_effect = [
        {"items": [], "next_deep_paging_id": "hit-scroll"},
        {"items": [], "next_deep_paging_id": "action-scroll"},
        {"items": []},
        {"items": []},
    ]

    hit_response = search.scroll.open("hit", "howler.id:*", rows=2, filters=["howler.status:open"], fl="howler.id")
    action_response = search.scroll.open("action", "action_id:*", rows=3, filters=["status:enabled"], fl="action_id")

    search.scroll.next(hit_response["next_deep_paging_id"], "2m")
    search.scroll.next(action_response["next_deep_paging_id"], "3m")

    hit_path, hit_request = connection.post.call_args_list[2].args[0], connection.post.call_args_list[2].kwargs
    action_path, action_request = connection.post.call_args_list[3].args[0], connection.post.call_args_list[3].kwargs
    assert hit_path == "api/v1/search/hit"
    assert json.loads(hit_request["data"]) == {
        "query": "howler.id:*",
        "deep_paging_id": "hit-scroll",
        "scroll": "2m",
        "rows": 2,
        "filters": ["howler.status:open"],
        "fl": "howler.id",
    }
    assert action_path == "api/v1/search/action"
    assert json.loads(action_request["data"]) == {
        "query": "action_id:*",
        "deep_paging_id": "action-scroll",
        "scroll": "3m",
        "rows": 3,
        "filters": ["status:enabled"],
        "fl": "action_id",
    }


def test_scroll_clear_sends_scroll_id_and_removes_context():
    search, connection = _make_search()
    connection.post.return_value = {"items": [], "next_deep_paging_id": "scroll-4"}
    response = {"cleared": True}
    connection.delete.return_value = response

    search.scroll.open("hit", "howler.id:*")
    result = search.scroll.clear("scroll-4")

    assert result is response
    connection.delete.assert_called_once_with("api/v1/search/scroll", json={"scroll_id": "scroll-4"})
    with pytest.raises(ClientError, match="Unknown or expired scroll ID: scroll-4"):
        search.scroll.next("scroll-4", "1m")
