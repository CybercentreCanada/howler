import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from pydantic import AnyHttpUrl
from starlette.applications import Starlette

from .api import HowlerApiClient
from .auth import JSONWebTokenVerifier
from .config import AUTH, HOWLER_API, MCPSettings
from .prompts import register_prompts
from .request_logging import RequestLoggingMiddleware
from .tools import register_tools

logging.basicConfig(
    level=MCPSettings.LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# Validate and convert the port to an integer, defaulting to 8000 if invalid
try:
    port: int = int(MCPSettings.PORT)
except ValueError:
    logger.error(f"server_config_error invalid_port={MCPSettings.PORT}")
    port = 8000


api_client = HowlerApiClient()


mcp = FastMCP(
    "Howler MCP",
    token_verifier=JSONWebTokenVerifier(
        issuer=AUTH.ISSUER,
        jwks_uri=AUTH.JWKS_URI,
        audience=MCPSettings.AUDIENCE,
        required_scopes=MCPSettings.SCOPE.split(),
        timeout=AUTH.TIMEOUT,
    ),
    auth=AuthSettings(
        issuer_url=AnyHttpUrl(AUTH.ISSUER),
        resource_server_url=AnyHttpUrl(MCPSettings.BASE_URL),
        required_scopes=MCPSettings.SCOPE.split(),
    ),
    host=MCPSettings.HOST,
    port=port,
)


def _with_api_client_lifespan(app: Starlette, client: HowlerApiClient) -> Starlette:
    original_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncGenerator[None, None]:
        limits = httpx.Limits(
            max_connections=HOWLER_API.MAX_CONNECTIONS,
            max_keepalive_connections=HOWLER_API.MAX_KEEPALIVE_CONNECTIONS,
            keepalive_expiry=HOWLER_API.KEEPALIVE_EXPIRY,
        )
        try:
            await client.start(limits=limits)
            async with original_lifespan(app):
                yield
        finally:
            await client.aclose()

    app.router.lifespan_context = lifespan
    return app


_streamable_http_app = mcp.streamable_http_app


def streamable_http_app_with_request_logging() -> Starlette:
    app = _streamable_http_app()
    app.add_middleware(RequestLoggingMiddleware)
    return _with_api_client_lifespan(app, api_client)


mcp.streamable_http_app = streamable_http_app_with_request_logging  # type: ignore[method-assign]

register_tools(mcp, api_client)
register_prompts(mcp)


if __name__ == "__main__":
    # Start the MCP server using streamable-HTTP transport.

    logger.info(f"server_start host={MCPSettings.HOST} port={port}")
    logger.info(f"server_backend_target base_url={HOWLER_API.BASE_URL}")
    mcp.run(transport="streamable-http")
