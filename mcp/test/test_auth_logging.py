import logging

import pytest

from howler_mcp.auth_logging import AuthenticationLoggingMiddleware


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("headers", "reason"),
    [
        ([], "missing_authorization_header"),
        ([(b"authorization", b"Basic credentials")], "unsupported_authorization_scheme"),
        ([(b"authorization", b"Bearer invalid")], "invalid_or_expired_bearer_token"),
    ],
)
async def test_logs_reason_for_401_response(caplog, headers, reason):
    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 401, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    middleware = AuthenticationLoggingMiddleware(app)
    scope = {"type": "http", "path": "/mcp", "method": "POST", "headers": headers}

    async def send(message):
        return None

    with caplog.at_level(logging.WARNING, logger="howler_mcp.auth_logging"):
        await middleware(scope, None, send)

    assert f"reason={reason}" in caplog.text


@pytest.mark.asyncio
async def test_does_not_log_when_response_is_not_401(caplog):
    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    middleware = AuthenticationLoggingMiddleware(app)
    scope = {"type": "http", "path": "/.well-known", "method": "GET", "headers": []}

    async def send(message):
        return None

    with caplog.at_level(logging.WARNING, logger="howler_mcp.auth_logging"):
        await middleware(scope, None, send)

    assert "auth_response" not in caplog.text
