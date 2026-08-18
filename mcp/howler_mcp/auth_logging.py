import logging
from collections.abc import Awaitable, Callable

from starlette.types import Message, Receive, Scope, Send

logger = logging.getLogger(__name__)


class AuthenticationLoggingMiddleware:
    """Log authentication inputs and protected endpoint 401 responses."""

    def __init__(self, app: Callable[[Scope, Receive, Send], Awaitable[None]]):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        authorization = self._get_authorization_header(scope)

        async def logging_send(message: Message) -> None:
            if message["type"] == "http.response.start" and message["status"] == 401:
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
            await send(message)

        await self.app(scope, receive, logging_send)

    @staticmethod
    def _get_authorization_header(scope: Scope) -> bytes | None:
        for name, value in scope.get("headers", []):
            if name.lower() == b"authorization":
                return value
        return None
