import json
import os
from urllib.parse import urlparse, urlunparse

import pytest
import requests
from howler_mcp.config import AUTH, HOWLER_API, MCPSettings

RUN_MCP_NETWORK_TESTS = os.environ.get("RUN_MCP_NETWORK_TESTS", "").lower() in {
    "1",
    "true",
    "yes",
}

pytestmark = pytest.mark.skipif(
    not RUN_MCP_NETWORK_TESTS,
    reason=(
        "Live MCP network tests are disabled by default. "
        "Set RUN_MCP_NETWORK_TESTS=1 to enable."
    ),
)

TEST_USERNAME = os.environ.get("TEST_AUTH_USERNAME")
TEST_PASSWORD = os.environ.get("TEST_AUTH_PASSWORD")
TEST_SCOPE = os.environ.get("TEST_AUTH_SCOPE", MCPSettings.SCOPE)
TEST_EMAIL = os.environ.get("TEST_AUTH_EMAIL")

if RUN_MCP_NETWORK_TESTS:
    missing_vars = [
        name
        for name, value in {
            "TEST_AUTH_USERNAME": TEST_USERNAME,
            "TEST_AUTH_PASSWORD": TEST_PASSWORD,
            "TEST_AUTH_EMAIL": TEST_EMAIL,
        }.items()
        if not value
    ]
    if missing_vars:
        pytest.skip(
            "Missing required environment variables for live MCP network tests: "
            + ", ".join(missing_vars),
            allow_module_level=True,
        )


def _mcp_request_url() -> str:
    base_url = MCPSettings.BASE_URL
    parsed = urlparse(base_url)

    if parsed.hostname not in {"0.0.0.0", "::"}:
        return base_url

    netloc = "localhost"
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"

    return urlunparse(parsed._replace(netloc=netloc))


def get_token() -> str:
    payload = {
        "grant_type": "password",
        "client_id": AUTH.CLIENT_ID,
        "username": TEST_USERNAME,
        "password": TEST_PASSWORD,
        "scope": TEST_SCOPE,
    }
    if AUTH.CLIENT_SECRET:
        payload["client_secret"] = AUTH.CLIENT_SECRET

    response = requests.post(AUTH.TOKEN_URL, data=payload, timeout=HOWLER_API.TIMEOUT)
    response.raise_for_status()
    token = response.json().get("access_token")
    assert token, "Token response did not include access_token"
    return token


def call_mcp_tool(token: str, tool_name: str, arguments: dict | None = None) -> dict:
    if arguments is None:
        arguments = {}

    url_mcp = _mcp_request_url()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }

    init_payload = {
        "jsonrpc": "2.0",
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "pytest-tool-tester", "version": "1.0.0"},
        },
        "id": 1,
    }

    init_response = requests.post(
        url_mcp, headers=headers, json=init_payload, timeout=HOWLER_API.TIMEOUT
    )
    assert init_response.status_code == 200, (
        f"Initialization failed: {init_response.text}"
    )

    session_id = init_response.headers.get(
        "mcp-session-id"
    ) or init_response.headers.get("Mcp-Session-Id")
    assert session_id is not None, "Server did not return mcp-session-id"

    tool_headers = headers.copy()
    tool_headers["mcp-session-id"] = session_id
    tool_headers["Mcp-Method"] = "tools/call"
    tool_headers["Mcp-Name"] = tool_name

    mcp_payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
        "id": 2,
    }

    response = requests.post(
        url_mcp, headers=tool_headers, json=mcp_payload, timeout=HOWLER_API.TIMEOUT
    )
    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}. Response: {response.text}"
    )

    response_data = None
    for line in response.text.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            response_data = json.loads(line.replace("data:", "", 1).strip())
            break

    assert response_data is not None, "Could not find JSON-RPC payload in response"
    assert "result" in response_data, "Response did not contain a JSON-RPC result"
    return response_data["result"]


def _get_any_hit_id(token: str) -> str:
    response = requests.post(
        headers={"Authorization": f"Bearer {token}"},
        url=f"{HOWLER_API.BASE_URL}/search/hit",
        json={"query": "howler.id:*", "rows": 1, "offset": 0, "fl": "howler.id"},
        timeout=HOWLER_API.TIMEOUT,
    )
    response.raise_for_status()
    items = response.json().get("api_response", {}).get("items") or []
    assert items, "No hits available for live network test"
    return items[0]["howler"]["id"]


def test_mcp_server_connection():
    token = get_token()
    url_mcp = _mcp_request_url()

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }

    payload = {
        "jsonrpc": "2.0",
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "pytest-connection-checker", "version": "1.0.0"},
        },
        "id": 1,
    }

    response = requests.post(
        url_mcp, headers=headers, json=payload, timeout=HOWLER_API.TIMEOUT
    )
    assert response.status_code == 200


def test_tool_whoami():
    token = get_token()
    result = call_mcp_tool(token, "WhoAmI")

    assert not result.get("isError", False), f"Tool execution failed: {result}"
    tool_output = json.loads(result["content"][0]["text"])
    assert tool_output["username"] == TEST_USERNAME
    assert tool_output["email"] == TEST_EMAIL


def test_tool_list_assigned_hits():
    token = get_token()
    result = call_mcp_tool(token, "ListAssignedHits")

    assert not result.get("isError", False)
    assert "content" in result


def test_tool_get_hit_fields():
    token = get_token()
    result = call_mcp_tool(token, "GetHitFields")

    assert not result.get("isError", False)
    tool_output = json.loads(result["content"][0]["text"])
    assert isinstance(tool_output, dict)
    assert "howler.id" in tool_output


def test_tool_get_field_values():
    token = get_token()
    result = call_mcp_tool(token, "GetFieldValues", {"field": "howler.escalation"})

    assert not result.get("isError", False)
    tool_output = json.loads(result["content"][0]["text"])
    assert isinstance(tool_output, dict)


def test_tool_lucene_query():
    token = get_token()
    result = call_mcp_tool(
        token,
        "luceneQuery",
        {
            "query": "howler.id:*",
            "fl": "howler.id,howler.assignment",
            "rows": 5,
            "offset": 0,
            "sort": "event.created desc",
        },
    )

    assert not result.get("isError", False)
    structured = result.get("structuredContent") or {}
    assert "rows" in structured
    assert "total" in structured
    assert "hits" in structured


def test_tool_add_comment_to_hit():
    token = get_token()
    hit_id = _get_any_hit_id(token)

    result = call_mcp_tool(
        token,
        "AddCommentToHit",
        {"hit_id": hit_id, "comment": "network test comment"},
    )

    assert not result.get("isError", False)
    text = result["content"][0]["text"]
    assert "Comment added successfully" in text


if __name__ == "__main__":
    pytest.main(["-v", __file__])
