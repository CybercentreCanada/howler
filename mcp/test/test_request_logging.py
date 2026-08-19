import logging

import pytest

from howler_mcp.request_logging import RequestLoggingMiddleware


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

    middleware = RequestLoggingMiddleware(app)
    scope = {"type": "http", "path": "/mcp", "method": "POST", "headers": headers}

    async def send(message):
        return None

    with caplog.at_level(logging.WARNING, logger="howler_mcp.request_logging"):
        await middleware(scope, None, send)

    assert f"reason={reason}" in caplog.text


@pytest.mark.asyncio
async def test_does_not_log_when_response_is_not_401(caplog):
    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    middleware = RequestLoggingMiddleware(app)
    scope = {"type": "http", "path": "/.well-known", "method": "GET", "headers": []}

    async def send(message):
        return None

    with caplog.at_level(logging.WARNING, logger="howler_mcp.request_logging"):
        await middleware(scope, None, send)

    assert "auth_response" not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("headers", "session_id_present"),
    [([], "False"), ([(b"mcp-session-id", b"session-id")], "True")],
)
async def test_logs_404_with_session_header_presence(caplog, headers, session_id_present):
    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 404, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    middleware = RequestLoggingMiddleware(app)
    scope = {"type": "http", "path": "/mcp", "method": "POST", "headers": headers}

    async def send(message):
        return None

    with caplog.at_level(logging.WARNING, logger="howler_mcp.request_logging"):
        await middleware(scope, None, send)

    assert "not_found_response path=/mcp method=POST status=404 detail=empty_response_body" in caplog.text
    assert f"mcp_session_id_present={session_id_present}" in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("body", "detail"),
    [
        (b'{"error":{"message":"Session not found"}}', "Session not found"),
        (b"Not Found", "Not Found"),
    ],
)
async def test_logs_404_response_detail(caplog, body, detail):
    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 404, "headers": []})
        await send({"type": "http.response.body", "body": body})

    middleware = RequestLoggingMiddleware(app)
    scope = {"type": "http", "path": "/mcp", "method": "POST", "headers": []}

    async def send(message):
        return None

    with caplog.at_level(logging.WARNING, logger="howler_mcp.request_logging"):
        await middleware(scope, None, send)

    assert f"not_found_response path=/mcp method=POST status=404 detail={detail}" in caplog.text
