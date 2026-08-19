"""Unit tests for the active MCP tool surface.

These tests are fully mocked and require no live network access.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from mcp.server.auth.provider import AccessToken

from howler_mcp.tools import MAXIMUM_TICKET, register_tools

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
        "query_iconify",
        "get_iconify_exist",
        "whoami",
        "list_assigned_hits",
        "add_comment_to_hit",
        "get_field_values",
        "get_hit_fields",
        "lucene_query",
        "get_label_set_options",
        "add_label_to_hit",
        "create_dossier",
        "create_dossier_for_hit",
        "update_dossier",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "http_request",
    [
        None,
        SimpleNamespace(
            scope={"user": None},
            headers={},
            url=SimpleNamespace(path="/mcp"),
        ),
    ],
)
async def test_tools_continue_when_request_context_is_incomplete(tools_and_api, http_request):
    tools, mock_api = tools_and_api
    mock_api.call.return_value = {
        "username": "jdoe",
        "email": "jdoe@example.com",
        "groups": [],
        "roles": [],
    }

    with (
        patch("howler_mcp.tools.get_http_request", return_value=http_request),
        patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN),
    ):
        result = await tools["whoami"]()

    assert result.username == "jdoe"


@pytest.mark.asyncio
async def test_tools_recover_token_from_request_scope(tools_and_api):
    tools, mock_api = tools_and_api
    raw_token = SimpleNamespace(
        token="raw-bearer",
        client_id="scope-client",
        scopes=["openid"],
        expires_at=9999999999,
        resource="howler",
    )
    request = SimpleNamespace(
        scope={"user": SimpleNamespace(access_token=raw_token)},
        headers={"authorization": "Bearer raw-bearer"},
        url=SimpleNamespace(path="/mcp"),
    )
    mock_api.call.return_value = [{"howler": {"id": "hit-1"}}]

    with (
        patch("howler_mcp.tools.get_http_request", return_value=request),
        patch(GET_ACCESS_TOKEN_PATH, side_effect=ValueError("context type mismatch")),
    ):
        result = await tools["list_assigned_hits"]()

    assert result == [{"howler": {"id": "hit-1"}}]
    assert mock_api.call.call_args.kwargs["user_access_token"].token == "raw-bearer"


def test_query_iconify_requests_expected_params_without_prefix(tools_and_api):
    tools, _ = tools_and_api

    with patch("howler_mcp.tools.httpx.get") as mock_get:
        mock_get.return_value.json.return_value = {"icons": ["mdi:alert", "mdi:shield"]}

        result = tools["query_iconify"](query="alert", limit=25)

    assert result == {"mdi:alert", "mdi:shield"}
    mock_get.assert_called_once()
    call_kwargs = mock_get.call_args.kwargs
    assert call_kwargs["params"] == {"query": "alert", "limit": 25}
    assert call_kwargs["timeout"] == 10


def test_query_iconify_requests_expected_params_with_prefix(tools_and_api):
    tools, _ = tools_and_api

    with patch("howler_mcp.tools.httpx.get") as mock_get:
        mock_get.return_value.json.return_value = {"icons": ["mdi:file-document"]}

        result = tools["query_iconify"](query="file", limit=5, prefix="mdi")

    assert result == {"mdi:file-document"}
    call_kwargs = mock_get.call_args.kwargs
    assert call_kwargs["params"] == {"query": "file", "limit": 5, "prefix": "mdi"}


@pytest.mark.parametrize(
    "icon_id,status_code,expected_suffix",
    [
        ("mdi:alarm", 200, "/mdi/alarm.svg"),
        ("simple-icons", 404, "/simple-icons"),
    ],
)
def test_get_iconify_exist_url_shape_and_result(tools_and_api, icon_id, status_code, expected_suffix):
    tools, _ = tools_and_api

    with patch("howler_mcp.tools.httpx.get") as mock_get:
        mock_get.return_value.status_code = status_code

        result = tools["get_iconify_exist"](icon_id=icon_id)

    assert result is (status_code == 200)
    called_url = mock_get.call_args.args[0]
    assert called_url.endswith(expected_suffix)
    assert mock_get.call_args.kwargs["timeout"] == 10


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
    mock_api.call.return_value = {"howler.escalation": {"type": "keyword", "description": "x", "list": False}}

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
async def test_lucene_query_rejects_empty_query(tools_and_api):
    tools, mock_api = tools_and_api

    with (
        patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN),
        pytest.raises(ValueError, match="query can not be empty"),
    ):
        await tools["lucene_query"](query="   ", fl="howler.id")

    mock_api.call.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("offset", [-1, 10001])
async def test_lucene_query_offset_validation(tools_and_api, offset):
    tools, mock_api = tools_and_api
    mock_api.call.return_value = {"howler.id": {"type": "keyword"}}

    with (
        patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN),
        pytest.raises(ValueError, match="offset=.*must be between"),
    ):
        await tools["lucene_query"](query="howler.id:*", fl="howler.id", offset=offset)


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
                    "event": {"created": "2024-01-01"},
                }
            ],
        },
    ]

    with patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN):
        result = await tools["lucene_query"](
            query="howler.assignment:user",
            fl="howler.assignment,event.created,howler.assignment",
            sort="event.created desc",
            rows=20,
            offset=10,
        )

    assert result.rows == 1
    assert result.total == 1
    assert result.hits[0]["howler"]["id"] == "hit-1"
    assert result.hits[0]["event"]["created"] == "2024-01-01"

    search_call = mock_api.call.call_args_list[-1].kwargs
    assert search_call["path"] == "/search/hit"
    assert search_call["method"] == "POST"
    assert search_call["body"]["query"] == "howler.assignment:user"
    assert search_call["body"]["rows"] == 20
    assert search_call["body"]["offset"] == 10
    assert search_call["body"]["sort"] == "event.created desc"
    assert search_call["body"]["fl"] == "howler.id,howler.assignment,event.created"


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
async def test_get_label_set_options_derives_non_empty_label_categories(tools_and_api):
    tools, mock_api = tools_and_api
    mock_api.call.return_value = {
        "howler.labels.generic": {"type": "keyword"},
        "howler.labels.": {"type": "keyword"},
        "howler.status": {"type": "keyword"},
    }

    with patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN):
        result = await tools["get_label_set_options"]()

    assert result == ["generic"]


@pytest.mark.asyncio
async def test_add_label_to_hit_normalizes_category_and_returns_updated_labels(tools_and_api):
    tools, mock_api = tools_and_api
    mock_api.call.return_value = {"howler": {"labels": {"generic": ["investigate"]}}}

    with patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN):
        result = await tools["add_label_to_hit"](
            hit_id=" hit-1 ",
            labels_name=["investigate"],
            label_set="GENERIC",
        )

    assert result == ["investigate"]
    assert mock_api.call.call_args.kwargs["path"] == "/hit/hit-1/labels/generic"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("hit_id", "labels_name", "message"),
    [
        ("hit-1", [], "Label_name require"),
        ("   ", ["investigate"], "hit_id require"),
    ],
)
async def test_add_label_to_hit_validates_required_values(tools_and_api, hit_id, labels_name, message):
    tools, mock_api = tools_and_api

    with pytest.raises(ValueError, match=message):
        await tools["add_label_to_hit"](hit_id=hit_id, labels_name=labels_name, label_set="generic")

    mock_api.call.assert_not_called()


@pytest.mark.asyncio
async def test_lucene_query_rejects_unknown_query_field_before_search_call(
    tools_and_api,
):
    tools, mock_api = tools_and_api
    mock_api.call.return_value = {"howler.id": {"type": "keyword", "description": "id", "list": False}}

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
    effective_kwargs = {key: (valid_hit_id if value == "__VALID_HIT_ID__" else value) for key, value in kwargs.items()}

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


@pytest.mark.asyncio
async def test_create_dossier_all_hit_names(tools_and_api):
    tools, mock_api = tools_and_api
    mock_api.call.side_effect = [
        {"howler.id": {"type": "keyword", "description": "id", "list": False}},
        {"dossier_id": "abc-123", "title": "All Hit Names"},
    ]

    dossier_payload = {
        "title": "All Hit Names",
        "query": "howler.id:*",
        "type": "personal",
    }

    with patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN):
        result = await tools["create_dossier"](dossier_data=dossier_payload)

    assert result["dossier_id"] == "abc-123"

    call_kwargs = mock_api.call.call_args.kwargs
    assert call_kwargs["path"] == "/dossier/"
    assert call_kwargs["method"] == "POST"
    assert call_kwargs["body"]["title"] == "All Hit Names"
    assert call_kwargs["body"]["query"] == "howler.id:*"
    assert call_kwargs["body"]["type"] == "personal"


@pytest.mark.asyncio
async def test_create_dossier_rejects_invalid_lead_icon_via_verify_leads(tools_and_api):
    tools, mock_api = tools_and_api

    dossier_payload = {
        "title": "Lead Validation",
        "query": "howler.id:*",
        "type": "personal",
        "leads": [
            {
                "icon": "mdi:not-real",
                "label": {"en": "Overview", "fr": "Apercu"},
                "format": "markdown",
                "content": "Initial notes",
                "metadata": {},
            }
        ],
    }

    with (
        patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN),
        patch("howler_mcp.tools.httpx.get") as mock_get,
        pytest.raises(ValueError, match="does not exist in iconify"),
    ):
        mock_get.return_value.status_code = 404
        await tools["create_dossier"](dossier_data=dossier_payload)

    mock_api.call.assert_not_called()


@pytest.mark.asyncio
async def test_create_dossier_rejects_non_dict_lead_metadata(tools_and_api):
    tools, mock_api = tools_and_api

    dossier_payload = {
        "title": "Lead Validation",
        "query": "howler.id:*",
        "type": "personal",
        "leads": [
            {
                "icon": "mdi:file-document",
                "label": {"en": "Overview", "fr": "Apercu"},
                "format": "markdown",
                "content": "Initial notes",
                "metadata": "not-a-dict",
            }
        ],
    }

    with (
        patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN),
        patch("howler_mcp.tools.httpx.get") as mock_get,
        pytest.raises(TypeError, match="metadata key need to be a dictionary"),
    ):
        mock_get.return_value.status_code = 200
        await tools["create_dossier"](dossier_data=dossier_payload)

    mock_api.call.assert_not_called()


@pytest.mark.asyncio
async def test_create_dossier_rejects_invalid_pivot_mappings_type(tools_and_api):
    tools, mock_api = tools_and_api

    dossier_payload = {
        "title": "Pivot Validation",
        "query": "howler.id:*",
        "type": "personal",
        "pivots": [
            {
                "icon": "mdi:open-in-new",
                "label": {"en": "Pivot", "fr": "Pivot"},
                "value": "https://example.local?q={ioc}",
                "format": "link",
                "mappings": {},
            }
        ],
    }

    with (
        patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN),
        patch("howler_mcp.tools.httpx.get") as mock_get,
        pytest.raises(TypeError, match="mappings must be a list"),
    ):
        mock_get.return_value.status_code = 200
        await tools["create_dossier"](dossier_data=dossier_payload)

    mock_api.call.assert_not_called()


@pytest.mark.asyncio
async def test_create_dossier_with_valid_nested_data_calls_api(tools_and_api):
    tools, mock_api = tools_and_api
    mock_api.call.side_effect = [
        {"howler.id": {"type": "keyword", "description": "id", "list": False}},
        {"dossier_id": "d-100"},
    ]

    dossier_payload = {
        "title": "Good Dossier",
        "query": "howler.id:*",
        "type": "global",
        "leads": [
            {
                "icon": "mdi:file-document",
                "label": {"en": "Overview", "fr": "Apercu"},
                "format": "markdown",
                "content": "Initial notes",
                "metadata": {},
            }
        ],
        "pivots": [
            {
                "icon": "mdi:open-in-new",
                "label": {"en": "Pivot", "fr": "Pivot"},
                "value": "https://example.local?q={ioc}",
                "format": "link",
                "mappings": [{"key": "ioc", "field": "howler.outline.indicators"}],
            }
        ],
    }

    with (
        patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN),
        patch("howler_mcp.tools.httpx.get") as mock_get,
    ):
        mock_get.return_value.status_code = 200
        result = await tools["create_dossier"](dossier_data=dossier_payload)

    assert result["dossier_id"] == "d-100"
    call_kwargs = mock_api.call.call_args.kwargs
    assert call_kwargs["path"] == "/dossier/"
    assert call_kwargs["method"] == "POST"


@pytest.mark.asyncio
async def test_create_dossier_for_hit_appends_leads(tools_and_api):
    tools, mock_api = tools_and_api
    mock_api.call.return_value = {"howler": {"id": "hit-1", "dossier": []}}

    lead = {
        "icon": "mdi:file-document",
        "label": {"en": "Overview", "fr": "Apercu"},
        "format": "markdown",
        "content": "Initial notes",
        "metadata": {},
    }

    with (
        patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN),
        patch("howler_mcp.tools.httpx.get") as mock_get,
    ):
        mock_get.return_value.status_code = 200
        result = await tools["create_dossier_for_hit"](hit_id=" hit-1 ", leads=[lead])

    assert result["howler"]["id"] == "hit-1"
    call_kwargs = mock_api.call.call_args.kwargs
    assert call_kwargs["path"] == "/hit/hit-1/update"
    assert call_kwargs["method"] == "PUT"
    assert call_kwargs["body"] == [["APPEND", "howler.dossier", lead]]


@pytest.mark.asyncio
async def test_create_dossier_for_hit_rejects_invalid_hit_id(tools_and_api):
    tools, mock_api = tools_and_api

    with (
        patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN),
        pytest.raises(ValueError, match="path separators"),
    ):
        await tools["create_dossier_for_hit"](hit_id="hit/1", leads=[])

    mock_api.call.assert_not_called()


@pytest.mark.asyncio
async def test_create_dossier_for_hit_rejects_missing_french_label(tools_and_api):
    tools, mock_api = tools_and_api

    with (
        patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN),
        patch("howler_mcp.tools.httpx.get") as mock_get,
        pytest.raises(ValueError, match="label key should contain the keys"),
    ):
        mock_get.return_value.status_code = 200
        await tools["create_dossier_for_hit"](
            hit_id="hit-1",
            leads=[
                {
                    "icon": "openmoji:flag-canada",
                    "label": {"en": "Hello, World,"},
                    "format": "markdown",
                    "content": "O Canada!",
                    "metadata": {"source": "manual"},
                }
            ],
        )

    mock_api.call.assert_not_called()


@pytest.mark.asyncio
async def test_update_dossier_rejects_non_list_pivots(tools_and_api):
    tools, _ = tools_and_api

    with (
        patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN),
        pytest.raises(TypeError, match="pivots require to be a list"),
    ):
        await tools["update_dossier"](dossier_id="d-1", data_to_update={"pivots": {"bad": "shape"}})


@pytest.mark.asyncio
async def test_update_dossier_rejects_invalid_lead_payload(tools_and_api):
    tools, _ = tools_and_api

    with (
        patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN),
        patch("howler_mcp.tools.httpx.get") as mock_get,
        pytest.raises(ValueError, match="label key should contain the keys"),
    ):
        mock_get.return_value.status_code = 200
        await tools["update_dossier"](
            dossier_id="d-1",
            data_to_update={
                "leads": [
                    {
                        "icon": "mdi:file-document",
                        "label": {"en": "Overview", "es": "Resumen"},
                        "format": "markdown",
                        "content": "Initial notes",
                        "metadata": {},
                    }
                ]
            },
        )


@pytest.mark.asyncio
async def test_update_dossier_with_query_and_valid_nested_data_calls_api(tools_and_api):
    tools, mock_api = tools_and_api
    mock_api.call.side_effect = [
        {"howler.id": {"type": "keyword", "description": "id", "list": False}},
        {"updated": True},
    ]

    with (
        patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN),
        patch("howler_mcp.tools.httpx.get") as mock_get,
    ):
        mock_get.return_value.status_code = 200
        result = await tools["update_dossier"](
            dossier_id="d-2",
            data_to_update={
                "query": " howler.id:* ",
                "leads": [
                    {
                        "icon": "mdi:file-document",
                        "label": {"en": "Overview", "fr": "Apercu"},
                        "format": "markdown",
                        "content": "Initial notes",
                        "metadata": {},
                    }
                ],
                "pivots": [
                    {
                        "icon": "mdi:open-in-new",
                        "label": {"en": "Pivot", "fr": "Pivot"},
                        "value": "https://example.local?q={ioc}",
                        "format": "link",
                        "mappings": [],
                    }
                ],
            },
        )

    assert result == {"updated": True}

    update_call = mock_api.call.call_args_list[-1].kwargs
    assert update_call["path"] == "/dossier/d-2"
    assert update_call["method"] == "PUT"
    assert update_call["body"]["query"] == "howler.id:*"


@pytest.mark.asyncio
async def test_create_dossier_rejects_unknown_query_field(tools_and_api):
    tools, mock_api = tools_and_api
    mock_api.call.return_value = {"howler.id": {"type": "keyword", "description": "id", "list": False}}

    with (
        patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN),
        pytest.raises(ValueError, match="Invalid query field"),
    ):
        await tools["create_dossier"](
            dossier_data={
                "title": "Invalid Query",
                "query": "howler.unknown:value",
                "type": "personal",
            }
        )

    assert mock_api.call.call_count == 1
    assert mock_api.call.call_args.kwargs["path"] == "/search/fields/hit"


@pytest.mark.asyncio
async def test_create_dossier_rejects_non_list_pivot_mappings(tools_and_api):
    tools, mock_api = tools_and_api

    with (
        patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN),
        patch("howler_mcp.tools.httpx.get") as mock_get,
        pytest.raises(TypeError, match="mappings must be a list"),
    ):
        mock_get.return_value.status_code = 200
        await tools["create_dossier"](
            dossier_data={
                "title": "Invalid Pivot",
                "query": "howler.id:*",
                "type": "personal",
                "pivots": [
                    {
                        "icon": "mdi:open-in-new",
                        "label": {"en": "Pivot", "fr": "Pivot"},
                        "value": "https://example.local?q={ioc}",
                        "format": "link",
                        "mappings": {},
                    }
                ],
            }
        )

    mock_api.call.assert_not_called()


@pytest.mark.asyncio
async def test_update_dossier_rejects_malformed_pivot_values(tools_and_api):
    tools, mock_api = tools_and_api

    with (
        patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN),
        patch("howler_mcp.tools.httpx.get") as mock_get,
        pytest.raises(TypeError, match="pivot label must be a dictionary"),
    ):
        mock_get.return_value.status_code = 200
        await tools["update_dossier"](
            dossier_id="d-1",
            data_to_update={
                "pivots": [
                    {
                        "icon": "mdi:open-in-new",
                        "label": "Pivot",
                        "value": 42,
                        "format": "link",
                        "mappings": [],
                    }
                ]
            },
        )

    mock_api.call.assert_not_called()


@pytest.mark.asyncio
async def test_update_dossier_rejects_non_string_pivot_value(tools_and_api):
    tools, mock_api = tools_and_api

    with (
        patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN),
        patch("howler_mcp.tools.httpx.get") as mock_get,
        pytest.raises(TypeError, match="key value require to be of type string"),
    ):
        mock_get.return_value.status_code = 200
        await tools["update_dossier"](
            dossier_id="d-1",
            data_to_update={
                "pivots": [
                    {
                        "icon": "mdi:open-in-new",
                        "label": {"en": "Pivot", "fr": "Pivot"},
                        "value": 42,
                        "format": "link",
                        "mappings": [],
                    }
                ]
            },
        )

    mock_api.call.assert_not_called()


@pytest.mark.asyncio
async def test_create_dossier_rejects_lead_with_unexpected_keys(tools_and_api):
    tools, mock_api = tools_and_api
    dossier_payload = {
        "title": "Lead Validation",
        "query": "howler.id:*",
        "type": "personal",
        "leads": [
            {
                "icon": "mdi:file-document",
                "label": {"en": "Overview", "fr": "Apercu"},
                "format": "markdown",
                "content": "Initial notes",
                "metadata": {},
                "unexpected": True,
            }
        ],
    }

    with pytest.raises(ValueError, match="A lead should have the keys"):
        await tools["create_dossier"](dossier_data=dossier_payload)

    mock_api.call.assert_not_called()


@pytest.mark.asyncio
async def test_create_dossier_rejects_empty_lead_content(tools_and_api):
    tools, mock_api = tools_and_api
    dossier_payload = {
        "title": "Lead Validation",
        "query": "howler.id:*",
        "type": "personal",
        "leads": [
            {
                "icon": "mdi:file-document",
                "label": {"en": "Overview", "fr": "Apercu"},
                "format": "markdown",
                "content": " ",
                "metadata": {},
            }
        ],
    }

    with (
        patch("howler_mcp.tools.httpx.get") as mock_get,
        pytest.raises(ValueError, match="label must be"),
    ):
        mock_get.return_value.status_code = 200
        await tools["create_dossier"](dossier_data=dossier_payload)

    mock_api.call.assert_not_called()


def _valid_pivot() -> dict:
    return {
        "icon": "mdi:open-in-new",
        "label": {"en": "Pivot", "fr": "Pivot"},
        "value": "https://example.local?q={ioc}",
        "format": "link",
        "mappings": [{"key": "ioc", "field": "howler.outline.indicators"}],
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("pivots", "exception", "message"),
    [
        (["not-a-pivot"], TypeError, "Each pivot must be a dictionary"),
        ([{**_valid_pivot(), "unexpected": True}], ValueError, "A pivot should have the keys"),
        (
            [{key: value for key, value in _valid_pivot().items() if key != "format"}],
            ValueError,
            "missing required keys",
        ),
        ([{**_valid_pivot(), "icon": " "}], ValueError, "pivot icon must be"),
        ([{**_valid_pivot(), "label": {"en": "Pivot"}}], ValueError, "label key require"),
        ([{**_valid_pivot(), "label": {"en": "", "fr": "Pivot"}}], ValueError, "label value must be"),
        ([{**_valid_pivot(), "value": " "}], ValueError, "key value require"),
        ([{**_valid_pivot(), "mappings": ["not-a-mapping"]}], TypeError, "mapping must be a dictionary"),
        (
            [{**_valid_pivot(), "mappings": [{"key": "ioc", "field": "field", "extra": True}]}],
            ValueError,
            "may contain only",
        ),
        ([{**_valid_pivot(), "mappings": [{"key": "ioc"}]}], ValueError, "requires key and field"),
        ([{**_valid_pivot(), "mappings": [{"key": " ", "field": "field"}]}], ValueError, "key must be"),
        (
            [{**_valid_pivot(), "mappings": [{"key": "ioc", "field": "field", "custom_value": 1}]}],
            TypeError,
            "custom_value must be",
        ),
    ],
)
async def test_create_dossier_rejects_invalid_pivot_shapes(tools_and_api, pivots, exception, message):
    tools, mock_api = tools_and_api
    dossier_payload = {
        "title": "Pivot Validation",
        "query": "howler.id:*",
        "type": "personal",
        "pivots": pivots,
    }

    with (
        patch("howler_mcp.tools.httpx.get") as mock_get,
        pytest.raises(exception, match=message),
    ):
        mock_get.return_value.status_code = 200
        await tools["create_dossier"](dossier_data=dossier_payload)

    mock_api.call.assert_not_called()


@pytest.mark.asyncio
async def test_create_dossier_rejects_unknown_pivot_icon(tools_and_api):
    tools, mock_api = tools_and_api

    with (
        patch("howler_mcp.tools.httpx.get") as mock_get,
        pytest.raises(ValueError, match="Invalid image was given"),
    ):
        mock_get.return_value.status_code = 404
        await tools["create_dossier"](
            dossier_data={
                "title": "Pivot Validation",
                "query": "howler.id:*",
                "type": "personal",
                "pivots": [_valid_pivot()],
            }
        )

    mock_api.call.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("dossier_data", "exception", "message"),
    [
        ({"title": " ", "query": "howler.id:*", "type": "personal"}, ValueError, "dossier_data"),
        ({"title": "Invalid Type", "query": "howler.id:*", "type": "team"}, ValueError, "key type may"),
        (
            {"title": "Bad Pivots", "query": "howler.id:*", "type": "personal", "pivots": {}},
            TypeError,
            "key pivots must",
        ),
    ],
)
async def test_create_dossier_validates_required_values(tools_and_api, dossier_data, exception, message):
    tools, mock_api = tools_and_api

    with pytest.raises(exception, match=message):
        await tools["create_dossier"](dossier_data=dossier_data)

    mock_api.call.assert_not_called()


@pytest.mark.asyncio
async def test_update_dossier_rejects_unpermitted_field(tools_and_api):
    tools, mock_api = tools_and_api

    with pytest.raises(ValueError, match="permitted keys"):
        await tools["update_dossier"](dossier_id="d-1", data_to_update={"unexpected": True})

    mock_api.call.assert_not_called()


@pytest.mark.asyncio
async def test_update_dossier_rejects_non_list_leads(tools_and_api):
    tools, mock_api = tools_and_api

    with pytest.raises(TypeError, match="leads require to be a list"):
        await tools["update_dossier"](dossier_id="d-1", data_to_update={"leads": {}})

    mock_api.call.assert_not_called()


@pytest.mark.asyncio
async def test_update_dossier_rejects_empty_query(tools_and_api):
    tools, mock_api = tools_and_api

    with pytest.raises(ValueError, match="query must be provided"):
        await tools["update_dossier"](dossier_id="d-1", data_to_update={"query": "\n\t"})

    mock_api.call.assert_not_called()
