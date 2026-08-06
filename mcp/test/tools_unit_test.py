"""Unit tests for the active MCP tool surface.

These tests are fully mocked and require no live network access.
"""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from howler_mcp.tools import MAXIMUM_TICKET, register_tools
from mcp.server.auth.provider import AccessToken

FAKE_TOKEN = AccessToken(token="fake-bearer", client_id="test-client", scopes=[])
GET_ACCESS_TOKEN_PATH = "howler_mcp.tools.get_access_token"


class _CaptureMCP:
    """Minimal FastMCP stand-in that captures registered tools."""

    def __init__(self):
        self._tools: dict = {}

    def tool(self, name: str, **_kwargs):
        def decorator(fn):
            self._tools[name] = fn
            return fn

        return decorator


@pytest.fixture()
def tools_and_api():
    mock_mcp = _CaptureMCP()
    mock_api = AsyncMock()
    register_tools(mock_mcp, mock_api)
    return mock_mcp._tools, mock_api


def test_registered_tool_surface(tools_and_api):
    tools, _ = tools_and_api
    assert set(tools.keys()) == {
        "whoami",
        "list_assigned_hits",
        "add_comment_to_hit",
        "get_field_values",
        "get_hit_fields",
        "lucene_query",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool_name,kwargs",
    [
        ("whoami", {}),
        ("list_assigned_hits", {}),
        ("add_comment_to_hit", {"hit_id": str(uuid4()), "comment": "hello"}),
        ("get_field_values", {"field": "howler.escalation"}),
        ("get_hit_fields", {}),
        ("lucene_query", {"query": "howler.id:*", "fl": "howler.id"}),
    ],
)
async def test_access_token_required(tools_and_api, tool_name, kwargs):
    tools, _ = tools_and_api
    with (
        patch(GET_ACCESS_TOKEN_PATH, return_value=None),
        pytest.raises(ValueError, match="Access token is not available"),
    ):
        await tools[tool_name](**kwargs)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_hit_id",
    ["", "id/with/slash", "id\\with\\slash", "bad\nid", "bad\tid"],
)
async def test_add_comment_validates_hit_id_safety(tools_and_api, bad_hit_id):
    tools, mock_api = tools_and_api
    with (
        patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN),
        pytest.raises(ValueError, match="hit_id"),
    ):
        await tools["add_comment_to_hit"](hit_id=bad_hit_id, comment="note")

    mock_api.call.assert_not_called()


@pytest.mark.asyncio
async def test_add_comment_allows_non_uuid_hit_id(tools_and_api):
    tools, mock_api = tools_and_api
    mock_api.call.return_value = {}

    with patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN):
        result = await tools["add_comment_to_hit"](hit_id="hit-001", comment="note")

    assert result == "Comment added successfully."
    call_kwargs = mock_api.call.call_args.kwargs
    assert call_kwargs["path"] == "/hit/hit-001/comments"


@pytest.mark.asyncio
async def test_whoami_returns_structured_response(tools_and_api):
    tools, mock_api = tools_and_api
    mock_api.call.return_value = {
        "username": "jdoe",
        "email": "jdoe@example.com",
        "groups": ["analysts"],
        "roles": ["user"],
    }

    with patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN):
        result = await tools["whoami"]()

    assert result.username == "jdoe"
    assert result.email == "jdoe@example.com"
    assert result.groups == ["analysts"]
    assert result.roles == ["user"]

    call_kwargs = mock_api.call.call_args.kwargs
    assert call_kwargs["path"] == "/user/whoami"
    assert call_kwargs["method"] == "GET"


@pytest.mark.asyncio
async def test_list_assigned_hits_calls_expected_endpoint(tools_and_api):
    tools, mock_api = tools_and_api
    mock_api.call.return_value = [{"howler": {"id": "abc"}}]

    with patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN):
        result = await tools["list_assigned_hits"]()

    assert result[0]["howler"]["id"] == "abc"

    call_kwargs = mock_api.call.call_args.kwargs
    assert call_kwargs["path"] == "/hit/user"
    assert call_kwargs["method"] == "GET"


@pytest.mark.asyncio
async def test_add_comment_sends_correct_payload(tools_and_api):
    tools, mock_api = tools_and_api
    mock_api.call.return_value = {}
    hit_id = str(uuid4())

    with patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN):
        result = await tools["add_comment_to_hit"](hit_id=hit_id, comment="test note")

    assert result == "Comment added successfully."
    call_kwargs = mock_api.call.call_args.kwargs
    assert call_kwargs["path"] == f"/hit/{hit_id}/comments"
    assert call_kwargs["method"] == "POST"
    assert call_kwargs["body"] == {"value": "From MCP Client: test note"}


@pytest.mark.asyncio
async def test_get_hit_fields_projects_expected_shape(tools_and_api):
    tools, mock_api = tools_and_api
    mock_api.call.return_value = {
        "howler.escalation": {
            "type": "keyword",
            "indexed": True,
            "stored": False,
            "list": False,
            "description": "Escalation value",
        },
        "ignore.this": "not-a-dict",
    }

    with patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN):
        result = await tools["get_hit_fields"]()

    assert result == {
        "howler.escalation": {
            "list": False,
            "type": "keyword",
            "description": "Escalation value",
        }
    }

    call_kwargs = mock_api.call.call_args.kwargs
    assert call_kwargs["path"] == "/search/fields/hit"
    assert call_kwargs["method"] == "GET"


@pytest.mark.asyncio
async def test_get_field_values_requires_field(tools_and_api):
    tools, _ = tools_and_api

    with (
        patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN),
        pytest.raises(ValueError, match="field parameter is required"),
    ):
        await tools["get_field_values"](field="   ")


@pytest.mark.asyncio
async def test_get_field_values_rejects_unknown_field(tools_and_api):
    tools, mock_api = tools_and_api
    mock_api.call.return_value = {
        "howler.escalation": {"type": "keyword", "description": "x", "list": False}
    }

    with (
        patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN),
        pytest.raises(ValueError, match="not a valid option"),
    ):
        await tools["get_field_values"](field="howler.unknown")


@pytest.mark.asyncio
async def test_get_field_values_calls_facet_endpoint(tools_and_api):
    tools, mock_api = tools_and_api
    mock_api.call.side_effect = [
        {
            "howler.escalation": {
                "type": "keyword",
                "description": "Escalation value",
                "list": False,
            }
        },
        {"alert": 120, "hit": 340, "miss": 5},
    ]

    with patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN):
        result = await tools["get_field_values"](field="howler.escalation")

    assert result["alert"] == 120

    facet_call = mock_api.call.call_args_list[-1].kwargs
    assert facet_call["path"] == "/search/facet/hit/howler.escalation"
    assert facet_call["method"] == "GET"
    assert facet_call["params"] == {"query": "howler.id:*"}


@pytest.mark.asyncio
@pytest.mark.parametrize("rows", [-1, MAXIMUM_TICKET + 1])
async def test_lucene_query_rows_validation(tools_and_api, rows):
    tools, mock_api = tools_and_api
    mock_api.call.return_value = {"howler.id": {"type": "keyword"}}

    with (
        patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN),
        pytest.raises(ValueError, match="must be between 0"),
    ):
        await tools["lucene_query"](query="howler.id:*", fl="howler.id", rows=rows)


@pytest.mark.asyncio
async def test_lucene_query_requires_fl(tools_and_api):
    tools, mock_api = tools_and_api
    mock_api.call.return_value = {"howler.id": {"type": "keyword"}}

    with (
        patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN),
        pytest.raises(ValueError, match="fl must be provided"),
    ):
        await tools["lucene_query"](query="howler.id:*", fl="   ")


@pytest.mark.asyncio
async def test_lucene_query_rejects_non_int_offset(tools_and_api):
    tools, mock_api = tools_and_api
    mock_api.call.return_value = {"howler.id": {"type": "keyword"}}

    with (
        patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN),
        pytest.raises(TypeError),
    ):
        await tools["lucene_query"](query="howler.id:*", fl="howler.id", offset="10")


@pytest.mark.asyncio
async def test_lucene_query_builds_projected_body(tools_and_api):
    tools, mock_api = tools_and_api
    mock_api.call.side_effect = [
        {
            "howler.assignment": {
                "type": "keyword",
                "description": "assignment",
                "list": False,
            }
        },
        {
            "rows": 1,
            "total": 1,
            "items": [
                {
                    "classification": "TLP:WHITE",
                    "howler": {"id": "hit-1", "assignment": "user"},
                    "timestamp": "2024-01-01",
                }
            ],
        },
    ]

    with patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN):
        result = await tools["lucene_query"](
            query="howler.assignment:user",
            fl="howler.assignment",
            sort="event.created desc",
            rows=20,
            offset=10,
        )

    assert result.rows == 1
    assert result.total == 1
    assert result.hits[0]["howler"]["id"] == "hit-1"

    search_call = mock_api.call.call_args_list[-1].kwargs
    assert search_call["path"] == "/search/hit"
    assert search_call["method"] == "POST"
    assert search_call["body"]["query"] == "howler.assignment:user"
    assert search_call["body"]["rows"] == 20
    assert search_call["body"]["offset"] == 10
    assert search_call["body"]["sort"] == "event.created desc"
    assert search_call["body"]["fl"] == "howler.id,howler.assignment"


@pytest.mark.asyncio
async def test_lucene_query_omits_sort_when_empty(tools_and_api):
    tools, mock_api = tools_and_api
    mock_api.call.side_effect = [
        {"howler.id": {"type": "keyword", "description": "id", "list": False}},
        {"rows": 0, "total": 0, "items": []},
    ]

    with patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN):
        await tools["lucene_query"](query="howler.id:*", fl="howler.id")

    search_call = mock_api.call.call_args_list[-1].kwargs
    assert "sort" not in search_call["body"]


@pytest.mark.asyncio
async def test_lucene_query_rejects_unknown_query_field_before_search_call(
    tools_and_api,
):
    tools, mock_api = tools_and_api
    mock_api.call.return_value = {
        "howler.id": {"type": "keyword", "description": "id", "list": False}
    }

    with (
        patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN),
        pytest.raises(ValueError, match="Invalid query field"),
    ):
        await tools["lucene_query"](query="howler.unknown:value", fl="howler.id")

    # Field discovery is expected, but the search endpoint must not be called.
    assert mock_api.call.call_count == 1
    first_call = mock_api.call.call_args_list[0].kwargs
    assert first_call["path"] == "/search/fields/hit"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool_name,kwargs",
    [
        ("whoami", {}),
        ("list_assigned_hits", {}),
        (
            "add_comment_to_hit",
            {"hit_id": "__VALID_HIT_ID__", "comment": "note"},
        ),
        ("get_hit_fields", {}),
    ],
)
async def test_tool_call_error_is_propagated_simple(tools_and_api, tool_name, kwargs):
    tools, mock_api = tools_and_api
    mock_api.call.side_effect = ValueError("Missing 'api_response' in response JSON")
    valid_hit_id = str(uuid4())
    effective_kwargs = {
        key: (valid_hit_id if value == "__VALID_HIT_ID__" else value)
        for key, value in kwargs.items()
    }

    with (
        patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN),
        pytest.raises(ValueError, match="Missing 'api_response'"),
    ):
        await tools[tool_name](**effective_kwargs)


@pytest.mark.asyncio
async def test_get_field_values_error_is_propagated(tools_and_api):
    tools, mock_api = tools_and_api
    mock_api.call.side_effect = ValueError("Missing 'api_response' in response JSON")

    with (
        patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN),
        pytest.raises(ValueError, match="Missing 'api_response'"),
    ):
        await tools["get_field_values"](field="howler.escalation")


@pytest.mark.asyncio
async def test_lucene_query_error_is_propagated(tools_and_api):
    tools, mock_api = tools_and_api
    mock_api.call.side_effect = [
        {"howler.id": {"type": "keyword", "description": "id", "list": False}},
        ValueError("Missing 'api_response' in response JSON"),
    ]

    with (
        patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN),
        pytest.raises(ValueError, match="Missing 'api_response'"),
    ):
        await tools["lucene_query"](query="howler.id:*", fl="howler.id")
