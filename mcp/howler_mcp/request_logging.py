import json
import logging
from collections.abc import Awaitable, Callable

from starlette.types import Message, Receive, Scope, Send

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware:
    """Log authentication failures and diagnostic details for protocol 404 responses."""

    def __init__(self, app: Callable[[Scope, Receive, Send], Awaitable[None]]):
        """Initialize the middleware with the next ASGI application."""
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Forward the request while logging relevant HTTP response failures.

        Authentication failures can be logged when response headers are sent. A
        404 diagnostic is logged after the final response body chunk so FastMCP's
        JSON-RPC error message is available.
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        authorization = self._get_authorization_header(scope)
        session_id_present = self._get_header(scope, b"mcp-session-id") is not None
        response_status: int | None = None
        response_body = bytearray()

        async def logging_send(message: Message) -> None:
            nonlocal response_status

            if message["type"] == "http.response.start":
                response_status = message["status"]
                if response_status == 401:
                    if authorization is None:
                        reason = "missing_authorization_header"
                    elif not authorization.lower().startswith(b"bearer "):
                        reason = "unsupported_authorization_scheme"
                    else:
                        reason = "invalid_or_expired_bearer_token"
                    logger.warning(
                        "auth_response path=%s method=%s status=401 reason=%s",
                        scope.get("path", ""),
                        scope.get("method", ""),
                        reason,
                    )
            elif message["type"] == "http.response.body" and response_status == 404:
                # FastMCP returns the session failure reason in the response body.
                response_body.extend(message.get("body", b"")[: 4096 - len(response_body)])
                if not message.get("more_body", False):
                    logger.warning(
                        "not_found_response path=%s method=%s status=404 detail=%s mcp_session_id_present=%s",
                        scope.get("path", ""),
                        scope.get("method", ""),
                        self._get_response_detail(bytes(response_body)),
                        session_id_present,
                    )
            await send(message)

        await self.app(scope, receive, logging_send)

    @staticmethod
    def _get_header(scope: Scope, header_name: bytes) -> bytes | None:
        """Return a request header value using a case-insensitive name match."""
        for name, value in scope.get("headers", []):
            if name.lower() == header_name:
                return value
        return None

    @classmethod
    def _get_authorization_header(cls, scope: Scope) -> bytes | None:
        """Return the raw Authorization header from an ASGI request scope."""
        return cls._get_header(scope, b"authorization")

    @staticmethod
    def _get_response_detail(body: bytes) -> str:
        """Extract a safe, bounded diagnostic detail from a response body.

        FastMCP uses JSON-RPC error objects, while a route-level 404 may be
        plain text. Empty responses receive an explicit diagnostic value.
        """
        if not body:
            return "empty_response_body"

        detail: object = None
        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            detail = body.decode("utf-8", errors="replace")
        else:
            if isinstance(payload, dict):
                error = payload.get("error")
                if isinstance(error, dict):
                    detail = error.get("message")
            if not isinstance(detail, str):
                detail = body.decode("utf-8", errors="replace")

        return " ".join(detail.split())[:256]
