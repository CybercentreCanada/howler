"""
Unit tests for MCP tool validation and behavior.

No live server or network access required — all HTTP is mocked.
These run in the normal CI test suite. The network_connection_test.py
file contains opt-in integration tests for live-server validation.
"""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from howler_mcp.tools import MAXIMUM_LOOK_BACK, MAXIMUM_TICKET, RegisterTools
from mcp.server.auth.provider import AccessToken

# ── Fixtures ──────────────────────────────────────────────────────────────────

FAKE_TOKEN = AccessToken(token="fake-bearer", client_id="test-client", scopes=[])
GET_ACCESS_TOKEN_PATH = "howler_mcp.tools.get_access_token"


class _CaptureMCP:
    """Minimal stand-in for FastMCP that captures registered tool functions by name."""

    def __init__(self):
        self._tools: dict = {}

    def tool(self, name: str, **_kwargs):
        def decorator(fn):
            self._tools[name] = fn
            return fn

        return decorator


@pytest.fixture()
def tools_and_api():
    """Returns (tools_dict, mock_api_client) after calling RegisterTools."""
    mock_mcp = _CaptureMCP()
    mock_api = AsyncMock()
    RegisterTools(mock_mcp, mock_api)
    return mock_mcp._tools, mock_api


# ── Validation: ListAlerts ────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kwargs",
    [
        {"lookback_in_days": 0},
        {"lookback_in_days": MAXIMUM_LOOK_BACK + 1},
        {"limit": 0},
        {"limit": MAXIMUM_TICKET + 1},
    ],
)
async def test_list_alerts_validation(tools_and_api, kwargs):
    tools, _ = tools_and_api
    with pytest.raises(ValueError):
        await tools["ListAlerts"](**kwargs)


# ── Validation: GetFalsePositiveHits ─────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kwargs",
    [
        {"lookback_in_days": 0},
        {"lookback_in_days": MAXIMUM_LOOK_BACK + 1},
        {"limit": 0},
        {"limit": MAXIMUM_TICKET + 1},
    ],
)
async def test_get_false_positive_hits_validation(tools_and_api, kwargs):
    tools, _ = tools_and_api
    with pytest.raises(ValueError):
        await tools["GetFalsePositiveHits"](**kwargs)


# ── Validation: ListHitsByAnalytic ────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kwargs",
    [
        {"analytic_name": "x", "lookback_in_days": 0},
        {"analytic_name": "x", "lookback_in_days": MAXIMUM_LOOK_BACK + 1},
        {"analytic_name": "x", "limit": 0},
        {"analytic_name": "x", "limit": MAXIMUM_TICKET + 1},
        {"analytic_name": "\n\t\r"},  # whitespace-only collapses to empty string
    ],
)
async def test_list_hits_by_analytic_validation(tools_and_api, kwargs):
    tools, _ = tools_and_api
    with pytest.raises(ValueError):
        await tools["ListHitsByAnalytic"](**kwargs)


# ── Validation: SearchHitsWithIndicators ──────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kwargs",
    [
        {"indicators": []},
        {"indicators": ["x"], "limit": 0},
        {"indicators": ["x"], "limit": MAXIMUM_TICKET + 1},
    ],
)
async def test_search_hits_with_indicators_validation(tools_and_api, kwargs):
    tools, _ = tools_and_api
    with pytest.raises(ValueError):
        await tools["SearchHitsWithIndicators"](**kwargs)


# ── Validation: UUID on GetHitById and AddCommentToHit ───────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool_name,kwargs",
    [
        ("GetHitById", {"hit_id": "not-a-uuid"}),
        ("GetHitById", {"hit_id": "12345"}),
        ("AddCommentToHit", {"hit_id": "not-a-uuid", "comment": "hi"}),
        ("AddCommentToHit", {"hit_id": "", "comment": "hi"}),
    ],
)
async def test_uuid_validation(tools_and_api, tool_name, kwargs):
    tools, _ = tools_and_api
    with pytest.raises(ValueError, match="UUID"):
        await tools[tool_name](**kwargs)


# ── Happy path: WhoAmI ────────────────────────────────────────────────────────


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
        result = await tools["WhoAmI"]()

    assert result.username == "jdoe"
    assert result.email == "jdoe@example.com"
    assert result.groups == ["analysts"]
    assert result.roles == ["user"]


# ── Happy path: ListAlerts ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_alerts_passes_correct_filter(tools_and_api):
    tools, mock_api = tools_and_api
    mock_api.call.return_value = {"rows": 0, "total": 0, "items": []}
    with patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN):
        await tools["ListAlerts"](lookback_in_days=3, limit=10)

    body = mock_api.call.call_args.kwargs["body"]
    assert body["rows"] == 10
    assert "now-3d" in body["filters"][0]
    assert "howler.escalation:alert" in body["query"]


# ── Happy path: SearchHitsWithIndicators escaping ─────────────────────────────


@pytest.mark.asyncio
async def test_search_hits_escapes_lucene_special_chars(tools_and_api):
    """Special Lucene characters in indicators must be backslash-escaped."""
    tools, mock_api = tools_and_api
    mock_api.call.return_value = {"rows": 0, "total": 0, "items": []}
    with patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN):
        result = await tools["SearchHitsWithIndicators"](
            indicators=["foo+bar", "192.168.1.1:80", "foo OR bar"]
        )

    query = mock_api.call.call_args.kwargs["body"]["query"]
    assert "foo\\+bar" in query  # '+' escaped
    assert "192.168.1.1\\:80" in query  # ':' escaped
    assert "foo\\ OR\\ bar" in query  # spaces escaped
    assert result.total == 0


@pytest.mark.asyncio
async def test_search_hits_returns_shaped_howler_response(tools_and_api):
    tools, mock_api = tools_and_api
    mock_api.call.return_value = {
        "rows": 1,
        "total": 1,
        "items": [
            {
                "classification": "TLP:WHITE",
                "howler": {"id": "abc", "analytic": "test"},
                "timestamp": "2024-01-01",
            }
        ],
    }
    with patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN):
        result = await tools["SearchHitsWithIndicators"](indicators=["abc"])

    assert result.total == 1
    assert result.hits[0]["classification"] == "TLP:WHITE"


# ── Happy path: ListHitsByAnalytic injection prevention ──────────────────────


@pytest.mark.asyncio
async def test_list_hits_by_analytic_escapes_closing_quote(tools_and_api):
    """A closing double-quote in analytic_name must not break the Lucene phrase query."""
    tools, mock_api = tools_and_api
    mock_api.call.return_value = {"rows": 0, "total": 0, "items": []}
    malicious = 'legit" OR howler.id:*'
    with patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN):
        await tools["ListHitsByAnalytic"](analytic_name=malicious)

    query = mock_api.call.call_args.kwargs["body"]["query"]
    assert '\\"' in query  # the injected quote must be escaped
    assert query.startswith('howler.analytic:"')
    assert query.endswith('"')


# ── Happy path: GetFalsePositiveHits ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_false_positive_hits_shapes_response(tools_and_api):
    tools, mock_api = tools_and_api
    mock_api.call.return_value = {
        "rows": 1,
        "total": 2,
        "items": [
            {
                "classification": "TLP:AMBER",
                "__analytic": {"analytic_id": "analytic-42"},
                "howler": {"id": "hit-1"},
                "timestamp": "2024-06-01",
            }
        ],
    }
    with patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN):
        result = await tools["GetFalsePositiveHits"]()

    assert result.total == 2
    assert result.hits[0]["analytic_id"] == "analytic-42"
    assert result.hits[0]["classification"] == "TLP:AMBER"


# ── Happy path: AddCommentToHit ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_add_comment_sends_correct_payload(tools_and_api):
    tools, mock_api = tools_and_api
    mock_api.call.return_value = {}
    hit_id = str(uuid4())
    with patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN):
        result = await tools["AddCommentToHit"](hit_id=hit_id, comment="test note")

    call_kwargs = mock_api.call.call_args.kwargs
    assert call_kwargs["path"] == f"/hit/{hit_id}/comments"
    assert call_kwargs["method"] == "POST"
    assert call_kwargs["body"]["value"] == "From MCP Client: test note"
    assert result == "Comment added successfully."


# ── Happy path: GetHitById ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_hit_by_id_calls_correct_path(tools_and_api):
    tools, mock_api = tools_and_api
    hit_id = str(uuid4())
    mock_api.call.return_value = {"howler": {"id": hit_id}}
    with patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN):
        result = await tools["GetHitById"](hit_id=hit_id)

    assert mock_api.call.call_args.kwargs["path"] == f"/hit/{hit_id}"
    assert result["howler"]["id"] == hit_id


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool_name,kwargs",
    [
        ("WhoAmI", {}),
        ("GetHitById", {"hit_id": "__VALID_HIT_ID__"}),
        ("ListAlerts", {}),
        ("ListAssignedHits", {}),
        ("SearchHitsWithIndicators", {"indicators": ["ioc-value"]}),
        ("GetFalsePositiveHits", {}),
        ("ListHitsByAnalytic", {"analytic_name": "Valid analytic"}),
        (
            "AddCommentToHit",
            {
                "hit_id": "__VALID_HIT_ID__",
                "comment": "note",
            },
        ),
        ("GetHitFields", {}),
        ("GetFieldValues", {"field": "howler.escalation"}),
        ("luceneQuery", {"query": "howler.id:*"}),
    ],
)
async def test_tool_call_error_is_propagated(tools_and_api, tool_name, kwargs):
    """Tools should surface api_client.call failures instead of swallowing them."""
    tools, mock_api = tools_and_api
    mock_api.call.side_effect = ValueError("Missing 'api_response' in response JSON")
    valid_hit_id = str(uuid4())
    effective_kwargs = {
        key: (valid_hit_id if value == "__VALID_HIT_ID__" else value)
        for key, value in kwargs.items()
    }

    with patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN):
        with pytest.raises(ValueError, match="Missing 'api_response'"):
            await tools[tool_name](**effective_kwargs)


# ── Happy path: GetHitFields ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_hit_fields_calls_correct_path(tools_and_api):
    tools, mock_api = tools_and_api
    mock_api.call.return_value = {
        "howler.escalation": {"type": "keyword", "indexed": True, "stored": False}
    }
    with patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN):
        result = await tools["GetHitFields"]()

    call_kwargs = mock_api.call.call_args.kwargs
    assert call_kwargs["path"] == "/search/fields/hit"
    assert call_kwargs["method"] == "GET"
    assert "howler.escalation" in result


# ── Happy path: GetFieldValues ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_field_values_calls_facet_endpoint(tools_and_api):
    tools, mock_api = tools_and_api
    mock_api.call.return_value = {"alert": 120, "hit": 340, "miss": 5}
    with patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN):
        result = await tools["GetFieldValues"](field="howler.escalation")

    call_kwargs = mock_api.call.call_args.kwargs
    assert call_kwargs["path"] == "/search/facet/hit/howler.escalation"
    assert call_kwargs["method"] == "GET"
    assert call_kwargs["params"] == {"query": "howler.id:*"}
    assert result["alert"] == 120


@pytest.mark.asyncio
async def test_get_field_values_passes_field_verbatim(tools_and_api):
    """The field name must appear verbatim in the path, including dots."""
    tools, mock_api = tools_and_api
    mock_api.call.return_value = {}
    with patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN):
        await tools["GetFieldValues"](field="howler.assessment")

    assert (
        "/search/facet/hit/howler.assessment" in mock_api.call.call_args.kwargs["path"]
    )


# ── Happy path / validation: luceneQuery ─────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "rows",
    [0, -1, MAXIMUM_TICKET + 1],
)
async def test_lucene_query_rows_validation(tools_and_api, rows):
    tools, _ = tools_and_api
    with pytest.raises(ValueError):
        await tools["luceneQuery"](query="howler.id:*", rows=rows)


@pytest.mark.asyncio
async def test_lucene_query_sends_correct_body(tools_and_api):
    tools, mock_api = tools_and_api
    mock_api.call.return_value = {"rows": 1, "total": 1, "items": []}
    with patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN):
        await tools["luceneQuery"](query="howler.assignment:user", rows=20, offset=30)

    body = mock_api.call.call_args.kwargs["body"]
    assert body["query"] == "howler.assignment:user"
    assert body["rows"] == 20
    assert body["offset"] == 30


@pytest.mark.asyncio
async def test_lucene_query_omits_sort_when_empty(tools_and_api):
    """sort must not appear in the POST body when the caller leaves it as the default empty string."""
    tools, mock_api = tools_and_api
    mock_api.call.return_value = {"rows": 0, "total": 0, "items": []}
    with patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN):
        await tools["luceneQuery"](query="howler.id:*")

    body = mock_api.call.call_args.kwargs["body"]
    assert "sort" not in body


@pytest.mark.asyncio
async def test_lucene_query_includes_sort_when_provided(tools_and_api):
    tools, mock_api = tools_and_api
    mock_api.call.return_value = {"rows": 0, "total": 0, "items": []}
    with patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN):
        await tools["luceneQuery"](query="howler.id:*", sort="event.created desc")

    body = mock_api.call.call_args.kwargs["body"]
    assert body["sort"] == "event.created desc"


@pytest.mark.asyncio
async def test_lucene_query_shapes_howler_response(tools_and_api):
    tools, mock_api = tools_and_api
    mock_api.call.return_value = {
        "rows": 1,
        "total": 5,
        "items": [
            {
                "classification": "TLP:WHITE",
                "howler": {"id": "hit-abc", "analytic": "test"},
                "timestamp": "2024-01-01",
            }
        ],
    }
    with patch(GET_ACCESS_TOKEN_PATH, return_value=FAKE_TOKEN):
        result = await tools["luceneQuery"](query="howler.id:*")

    assert result.rows == 1
    assert result.total == 5
    assert result.hits[0]["classification"] == "TLP:WHITE"
    assert result.hits[0]["howler"]["id"] == "hit-abc"
