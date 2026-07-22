import logging

from pydantic import AnyHttpUrl

from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP

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


mcp = FastMCP(
    "Howler MCP",
    token_verifier=KeycloakTokenVerifier(
        issuer=AUTH.ISSUER,
        jwks_uri=AUTH.JWKS_URI,
        audience=MCPSettings.AUDIENCE,
        required_scope=MCPSettings.SCOPE,
    ),
    auth=AuthSettings(
        issuer_url=AnyHttpUrl(AUTH.ISSUER),
        resource_server_url=AnyHttpUrl(MCPSettings.BASE_URL),
        required_scopes=[MCPSettings.SCOPE],
    ),
    host=MCPSettings.HOST,
    port=port,
)

api_client = HowlerApiClient()
RegisterTools(mcp, api_client)
RegisterPrompts(mcp)


if __name__ == "__main__":
    """Start the MCP server using streamable-HTTP transport."""

    logger.info(
        "Starting Howler MCP server on %s:%s",
        MCPSettings.HOST,
        port,
    )
    logger.info("Targeting Howler instance at %s", HOWLER_API.BASE_URL)

    mcp.run(transport="streamable-http")
