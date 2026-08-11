from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from mcp.server.auth.provider import AccessToken

from howler_mcp.api import HowlerApiClient

FAKE_TOKEN = AccessToken(token="fake-bearer", client_id="test-client", scopes=[])


@pytest.mark.asyncio
async def test_call_reuses_and_closes_owned_http_client():
    http_client = Mock()
    http_client.request = AsyncMock()
    http_client.aclose = AsyncMock()
    http_client.request.return_value = Mock(json=Mock(return_value={"api_response": {"status": "ok"}}))
    auth_provider = Mock()
    auth_provider.get_howler_token = AsyncMock(return_value="howler-token")

    with patch("howler_mcp.api.httpx.AsyncClient", return_value=http_client) as client_class:
        api_client = HowlerApiClient(auth_provider=auth_provider, timeout=2.0)
        first_response = await api_client.call(FAKE_TOKEN, "/whoami", "GET")
        second_response = await api_client.call(FAKE_TOKEN, "/whoami", "GET")
        await api_client.aclose()

    assert first_response == {"status": "ok"}
    assert second_response == {"status": "ok"}
    client_class.assert_called_once_with(timeout=2.0)
    assert http_client.request.await_count == 2
    http_client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_call_rejects_body_for_non_post_methods():
    auth_provider = Mock()
    auth_provider.get_howler_token = AsyncMock(return_value="howler-token")

    with patch("howler_mcp.api.httpx.AsyncClient", return_value=Mock()):
        api_client = HowlerApiClient(auth_provider=auth_provider)

    with pytest.raises(ValueError, match="Request body is not allowed for GET or OPTIONS"):
        await api_client.call(
            FAKE_TOKEN,
            "/whoami",
            "GET",
            body={"not": "allowed"},
        )


@pytest.mark.asyncio
async def test_call_rejects_missing_api_response_envelope():
    http_client = Mock()
    http_client.request = AsyncMock()
    http_client.aclose = AsyncMock()
    http_client.request.return_value = Mock(json=Mock(return_value={"wrong": "shape"}))
    auth_provider = Mock()
    auth_provider.get_howler_token = AsyncMock(return_value="howler-token")

    with patch("howler_mcp.api.httpx.AsyncClient", return_value=http_client):
        api_client = HowlerApiClient(auth_provider=auth_provider)

    with pytest.raises(ValueError, match="expected format"):
        await api_client.call(FAKE_TOKEN, "/whoami", "GET")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        httpx.ReadTimeout("timed out", request=httpx.Request("GET", "https://api")),
        httpx.ConnectError("connection failed", request=httpx.Request("GET", "https://api")),
        httpx.HTTPStatusError(
            "server error",
            request=httpx.Request("GET", "https://api"),
            response=httpx.Response(500, request=httpx.Request("GET", "https://api")),
        ),
    ],
)
async def test_call_reraises_original_httpx_error(error: httpx.HTTPError):
    http_client = Mock()
    http_client.request = AsyncMock(side_effect=error)
    auth_provider = Mock()
    auth_provider.get_howler_token = AsyncMock(return_value="howler-token")
    api_client = HowlerApiClient(auth_provider=auth_provider, client=http_client)

    with pytest.raises(type(error)) as raised_error:
        await api_client.call(FAKE_TOKEN, "/whoami", "GET")

    assert raised_error.value is error
    assert raised_error.value.request is error.request
