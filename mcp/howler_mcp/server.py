import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from pydantic import AnyHttpUrl

from .api import HowlerApiClient
from .auth import KeycloakTokenVerifier
from .config import AUTH, HOWLER_API, MCPSettings
from .prompts import RegisterPrompts
from .tools import RegisterTools

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# Validate and convert the port to an integer, defaulting to 8000 if invalid
try:
    port: int = int(MCPSettings.PORT)
except ValueError:
    logger.error("Invalid port number: %s", MCPSettings.PORT)
    port: int = 8000


api_client = HowlerApiClient()


@asynccontextmanager
async def lifespan(_: FastMCP) -> AsyncGenerator[dict[str, None]]:
    """Manage the lifespan of the MCP server.

    Ensures that long-lived resources, such as the shared HTTP client, are
    properly closed when the server shuts down.

    Args:
        _: The FastMCP application instance (unused).

    Yields:
        dict[str, None]: Empty context dictionary required by the lifespan
        protocol.
    """
    try:
        yield {}
    finally:
        await api_client.aclose()


mcp = FastMCP(
    "Howler MCP",
    token_verifier=KeycloakTokenVerifier(
        issuer=AUTH.ISSUER,
        jwks_uri=AUTH.JWKS_URI,
        audience=MCPSettings.AUDIENCE,
        required_scope=MCPSettings.SCOPE,
        timeout=AUTH.TIMEOUT,
    ),
    auth=AuthSettings(
        issuer_url=AnyHttpUrl(AUTH.ISSUER),
        resource_server_url=AnyHttpUrl(MCPSettings.BASE_URL),
        required_scopes=[MCPSettings.SCOPE],
    ),
    host=MCPSettings.HOST,
    port=port,
    lifespan=lifespan,
)

RegisterTools(mcp, api_client)
RegisterPrompts(mcp)


if __name__ == "__main__":
    # Start the MCP server using streamable-HTTP transport.

    logger.info(
        "Starting Howler MCP server on %s:%s",
        MCPSettings.HOST,
        port,
    )
    logger.info("Targeting Howler instance at %s", HOWLER_API.BASE_URL)

    mcp.run(transport="streamable-http")
