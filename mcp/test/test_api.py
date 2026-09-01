from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from mcp.server.auth.provider import AccessToken

from howler_mcp.api import HowlerApiClient
from howler_mcp.config import HOWLER_API

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
        limits = httpx.Limits(
            max_connections=10,
            max_keepalive_connections=4,
            keepalive_expiry=3.0,
        )
        await api_client.start(limits=limits)
        await api_client.start(limits=httpx.Limits(max_connections=1))
        first_response = await api_client.call(FAKE_TOKEN, "/whoami", "GET")
        second_response = await api_client.call(FAKE_TOKEN, "/whoami", "GET")
        await api_client.aclose()
        await api_client.aclose()

    assert first_response == {"status": "ok"}
    assert second_response == {"status": "ok"}
    client_class.assert_called_once_with(timeout=2.0, limits=limits)
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
        await api_client.start()

    with pytest.raises(ValueError, match="expected format"):
        await api_client.call(FAKE_TOKEN, "/whoami", "GET")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("content_type", "response_content", "logged_response"),
    [
        ("application/json", b'{"api_error_message":"invalid query"}', '{"api_error_message":"invalid query"}'),
        ("application/json", b"not json", "not json"),
        ("text/plain", b"invalid query", "invalid query"),
    ],
)
async def test_call_logs_http_error_response(caplog, content_type, response_content, logged_response):
    request = httpx.Request("GET", "https://api/whoami")
    response = httpx.Response(
        400,
        headers={"content-type": content_type},
        content=response_content,
        request=request,
    )
    http_client = Mock()
    http_client.request = AsyncMock(return_value=response)
    auth_provider = Mock()
    auth_provider.get_howler_token = AsyncMock(return_value="howler-token")
    api_client = HowlerApiClient(auth_provider=auth_provider, client=http_client)

    with caplog.at_level("WARNING", logger="howler_mcp.api"), pytest.raises(httpx.HTTPStatusError):
        await api_client.call(FAKE_TOKEN, "/whoami", "GET")

    assert f"response={logged_response}" in caplog.text


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


@pytest.mark.asyncio
async def test_call_requires_started_http_client():
    api_client = HowlerApiClient()

    with pytest.raises(RuntimeError, match="has not been started"):
        await api_client.call(FAKE_TOKEN, "/whoami", "GET")


@pytest.mark.asyncio
async def test_call_fails_after_owned_http_client_is_closed():
    http_client = Mock()
    http_client.aclose = AsyncMock()

    with patch("howler_mcp.api.httpx.AsyncClient", return_value=http_client):
        api_client = HowlerApiClient()
        await api_client.start()
        await api_client.aclose()

    with pytest.raises(RuntimeError, match="has not been started"):
        await api_client.call(FAKE_TOKEN, "/whoami", "GET")


@pytest.mark.asyncio
async def test_client_startup_error_is_propagated():
    startup_error = RuntimeError("unable to create HTTP client")

    with patch("howler_mcp.api.httpx.AsyncClient", side_effect=startup_error) as client_class:
        api_client = HowlerApiClient()

        with pytest.raises(RuntimeError, match="unable to create HTTP client"):
            await api_client.start()

    client_class.assert_called_once_with(timeout=HOWLER_API.TIMEOUT)


@pytest.mark.asyncio
async def test_injected_http_client_is_detached_but_not_closed():
    http_client = Mock()
    http_client.aclose = AsyncMock()
    api_client = HowlerApiClient(client=http_client)

    await api_client.start(limits=httpx.Limits(max_connections=1))
    await api_client.aclose()

    assert api_client._client is None
    http_client.aclose.assert_not_awaited()


@pytest.mark.asyncio
async def test_restart_after_injected_client_is_owned_and_closed():
    injected_client = Mock()
    injected_client.aclose = AsyncMock()
    restarted_client = Mock()
    restarted_client.aclose = AsyncMock()
    limits = httpx.Limits(max_connections=3)

    with patch("howler_mcp.api.httpx.AsyncClient", return_value=restarted_client) as client_class:
        api_client = HowlerApiClient(client=injected_client)
        await api_client.aclose()
        await api_client.start(limits=limits)
        await api_client.aclose()

    client_class.assert_called_once_with(timeout=HOWLER_API.TIMEOUT, limits=limits)
    injected_client.aclose.assert_not_awaited()
    restarted_client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_call_fails_after_injected_http_client_is_closed():
    http_client = Mock()
    api_client = HowlerApiClient(client=http_client)

    await api_client.aclose()

    with pytest.raises(RuntimeError, match="has not been started"):
        await api_client.call(FAKE_TOKEN, "/whoami", "GET")
