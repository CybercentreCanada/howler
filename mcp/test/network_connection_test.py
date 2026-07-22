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
    """Build a client-safe MCP URL for tests."""
    base_url = MCPSettings.BASE_URL
    parsed = urlparse(base_url)
    host = parsed.hostname

    if host not in {"0.0.0.0", "::"}:
        return base_url

    netloc = "localhost"
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"

    parsed = parsed._replace(netloc=netloc)
    return urlunparse(parsed)


# region helpers
def get_token():
    url_token = AUTH.TOKEN_URL
    payload = {
        "grant_type": "password",
        "client_id": AUTH.CLIENT_ID,
        "username": TEST_USERNAME,
        "password": TEST_PASSWORD,
        "scope": TEST_SCOPE,
    }
    if AUTH.CLIENT_SECRET:
        payload["client_secret"] = AUTH.CLIENT_SECRET

    response = requests.post(url_token, data=payload, timeout=HOWLER_API.TIMEOUT)
    response.raise_for_status()
    return response.json().get("access_token")


def call_mcp_tool(token: str, tool_name: str, arguments: dict | None = None) -> dict:
    """Helper function to initialize an MCP session, execute a tool call, and parse the SSE response."""
    if arguments is None:
        arguments = {}

    url_mcp = _mcp_request_url()

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }

    # 1. Establish session via initialize request to get a session ID
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
    )  # type: ignore
    assert init_response.status_code == 200, (
        f"Initialization failed: {init_response.text}"
    )

    # Extract session ID from headers (case-insensitive check)
    session_id = init_response.headers.get(
        "mcp-session-id"
    ) or init_response.headers.get("Mcp-Session-Id")
    assert session_id is not None, (
        f"Server did not return a session ID in headers. Available headers: {init_response.headers}"
    )

    # 2. Call the tool using the verified session ID and required headers
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
    )  # type: ignore
    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}. Response: {response.text}"
    )

    response_data = None
    for line in response.text.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            json_str = line.replace("data:", "", 1).strip()
            response_data = json.loads(json_str)
            break

    assert response_data is not None, (
        f"Could not find 'data:' payload in response: {response.text}"
    )
    assert "result" in response_data, (
        f"Response did not contain a valid JSON-RPC result. Full data: {response_data}"
    )

    return response_data["result"]


# endregion


# region tests
def test_mcp_server_connection():
    """Assert that the MCP server accepts the Auth token and responds to initialize."""
    token = get_token()
    url_mcp = _mcp_request_url()

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }

    mcp_payload = {
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
        url_mcp, headers=headers, json=mcp_payload, timeout=HOWLER_API.TIMEOUT
    )
    assert response.status_code == 200, f"Expected 200, got {response.status_code}."

    response_data = None
    for line in response.text.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            json_str = line.replace("data:", "", 1).strip()
            response_data = json.loads(json_str)
            break

    assert response_data is not None
    assert "result" in response_data
    assert response_data["result"]["serverInfo"]["name"] == "Howler MCP"


def test_tool_whoami():
    """Test the WhoAmI tool execution."""
    token = get_token()
    result = call_mcp_tool(token, "WhoAmI")

    assert not result.get("isError", False), f"Tool execution failed: {result}"
    assert len(result["content"]) > 0
    assert result["content"][0]["type"] == "text"

    tool_output = json.loads(result["content"][0]["text"])
    assert "username" in tool_output
    assert TEST_USERNAME == tool_output["username"]

    assert "email" in tool_output
    assert TEST_EMAIL == tool_output["email"]
    assert "roles" in tool_output
    assert (
        isinstance(tool_output["roles"], list)
        and "admin" in tool_output["roles"]
        and "user" in tool_output["roles"]
    )


def test_tool_list_alerts():
    """Test the ListAlerts tool with custom parameters."""
    token = get_token()
    result = call_mcp_tool(token, "ListAlerts", {"lookback_in_days": 1, "limit": 5})

    assert not result.get("isError", False)
    assert len(result["content"]) > 0

    tool_output = json.loads(result["content"][0]["text"])
    assert isinstance(tool_output, dict)


def test_tool_search_hits_with_indicators():
    """Test the SearchHitsWithIndicators tool ensuring lists are processed properly."""
    token = get_token()
    api_response = requests.post(
        headers={"Authorization": f"Bearer {token}"},
        url=f"{HOWLER_API.BASE_URL}/search/hit",
        json={"query": r"howler.comment.id:*", "fl": None, "filters": [], "rows": 1},
        timeout=HOWLER_API.TIMEOUT,
    )
    api_response.raise_for_status()
    response = api_response.json()

    indicators = [
        response["api_response"]["items"][0]["howler"]["outline"]["target"],
        response["api_response"]["items"][0]["howler"]["outline"]["threat"],
    ]

    for indicator in response["api_response"]["items"][0]["howler"]["outline"][
        "indicators"
    ]:
        if indicator not in indicators:
            indicators.append(indicator)

    result = call_mcp_tool(
        token,
        "SearchHitsWithIndicators",
        {
            "indicators": indicators,
            "limit": 20,  # make it quite large to ensure the original is in there
        },
    )

    assert (
        result["structuredContent"]["total"] > 0
    )  # we took it from a hit, so we should have at LEAST 1
    is_ticket_present = False
    # hits ID are unique. If its present the tool worked properly to grab the hits with the indicators. We don't care about the order, just that its present.
    for hit in result["structuredContent"]["hits"]:
        if hit["howler"]["id"] == response["api_response"]["items"][0]["howler"]["id"]:
            is_ticket_present = True
            break

    assert not result.get("isError", False)
    assert is_ticket_present, "Expected hit not found in MCP result."


def test_tool_get_hit_by_id():
    """Test fetching a specific hit by ID."""
    token = get_token()
    api_response = requests.post(
        headers={"Authorization": f"Bearer {token}"},
        url=f"{HOWLER_API.BASE_URL}/search/hit",
        json={"query": r"howler.comment.id:*", "fl": None, "filters": [], "rows": 1},
        timeout=HOWLER_API.TIMEOUT,
    )
    api_response.raise_for_status()
    response = api_response.json()

    hit_id = response["api_response"]["items"][0]["howler"]["id"]

    result = call_mcp_tool(token, "GetHitById", {"hit_id": hit_id})
    # ensure we grabbed the same ticket that I requested from the API :
    is_same = (
        (
            result["structuredContent"]["howler"]["id"]
            == response["api_response"]["items"][0]["howler"]["id"]
        )
        and (
            result["structuredContent"]["howler"]["analytic"]
            == response["api_response"]["items"][0]["howler"]["analytic"]
        )
        and (
            result["structuredContent"]["howler"]["assignment"]
            == response["api_response"]["items"][0]["howler"]["assignment"]
        )
        and (
            result["structuredContent"]["howler"]["bundle_size"]
            == response["api_response"]["items"][0]["howler"]["bundle_size"]
        )
    )

    assert not result.get("isError", False)
    assert is_same, (
        f"Expected hit data does not match. MCP result: {result['structuredContent']['howler']}, API response: {response['api_response']['items'][0]['howler']}"
    )


def test_tool_add_comment_to_hit():
    """Test adding a comment to a hit via the POST tool."""
    token = get_token()
    api_response = requests.post(
        headers={"Authorization": f"Bearer {token}"},
        url=f"{HOWLER_API.BASE_URL}/search/hit",
        json={"query": r"howler.comment.id:*", "fl": None, "filters": [], "rows": 1},
        timeout=HOWLER_API.TIMEOUT,
    )
    api_response.raise_for_status()
    hit_id = api_response.json()["api_response"]["items"][0]["howler"]["id"]

    call_mcp_tool(
        token,
        "AddCommentToHit",
        {"hit_id": hit_id, "comment": "unit testing making the comment"},
    )  # write : "From MCP Client: unit testing making the comment"

    # get comment back :
    comment_response = requests.post(
        headers={"Authorization": f"Bearer {token}"},
        url=f"{HOWLER_API.BASE_URL}/search/hit",
        json={"query": f"howler.id:{hit_id}", "fl": None, "filters": [], "rows": 1},
        timeout=HOWLER_API.TIMEOUT,
    )
    comment_response.raise_for_status()
    comment = comment_response.json()["api_response"]["items"][0]["howler"]["comment"]

    is_pass = False
    for e in comment:
        if e["value"] == "From MCP Client: unit testing making the comment":
            is_pass = True
            break

    assert is_pass, f"Expected comment not found in hit {hit_id}. Comments: {comment}"


def test_tool_get_false_positive_hit():
    token = get_token()
    lookback_in_days = 7
    limit = 25
    http_response = requests.post(
        headers={"Authorization": f"Bearer {token}"},
        url=f"{HOWLER_API.BASE_URL}/search/hit",
        json={
            "query": "howler.assessment:false-positive",
            "fl": None,
            "filters": [f"event.created:[now-{lookback_in_days}d TO now]"],
            "rows": limit,
        },
        timeout=HOWLER_API.TIMEOUT,
    )
    http_response.raise_for_status()
    howler_answer = http_response.json()

    response = call_mcp_tool(
        token,
        "GetFalsePositiveHits",
        {"lookback_in_days": lookback_in_days, "limit": limit},
    )

    structured_content = response["structuredContent"]
    api_response = howler_answer["api_response"]

    assert not response.get("isError", False)
    assert structured_content["total"] == api_response["total"]
    assert structured_content["rows"] == api_response["rows"]

    expected_ids = {item["howler"]["id"] for item in (api_response.get("items") or [])}
    returned_ids = {
        hit["howler"]["id"] for hit in (structured_content.get("hits") or [])
    }
    assert returned_ids == expected_ids, (
        "Expected false-positive hit IDs from MCP do not match direct API results."
    )


def test_tool_list_hits_by_analytic():
    token = get_token()
    api_response = requests.post(
        headers={"Authorization": f"Bearer {token}"},
        url=f"{HOWLER_API.BASE_URL}/search/hit",
        json={"query": r"howler.comment.id:*", "fl": None, "filters": [], "rows": 1},
        timeout=HOWLER_API.TIMEOUT,
    )
    api_response.raise_for_status()
    howler_ticket = api_response.json()
    analytic = howler_ticket["api_response"]["items"][0]["howler"]["analytic"]
    get_analytic = call_mcp_tool(
        token,
        "ListHitsByAnalytic",
        {
            "analytic_name": analytic,
            "lookback_in_days": 7,
            "limit": 25,  # make it quite large to ensure the original is in there
        },
    )
    is_valid = False
    for hit in get_analytic["structuredContent"]["hits"]:
        if (
            hit["howler"]["id"]
            == howler_ticket["api_response"]["items"][0]["howler"]["id"]
        ):
            is_valid = True
            break
    assert is_valid, (
        f"Expected hit ID from MCP does not match the API response for analytic {analytic}."
    )


# endregion

if __name__ == "__main__":
    pytest.main(["-v", __file__])
