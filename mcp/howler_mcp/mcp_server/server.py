import logging

from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from pydantic import AnyHttpUrl

from .api import HowlerApiClient
from .auth import KeycloakTokenVerifier
from .config import AUTH, MCPSettings
from .prompts import RegisterPrompts
from .tools import RegisterTools

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

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
    host="0.0.0.0",
)

api_client = HowlerApiClient()
RegisterTools(mcp, api_client)
RegisterPrompts(mcp)


if __name__ == "__main__":
    """Start the MCP server using streamable-HTTP transport."""

    logger.info(
        "Starting Howler MCP server on %s:%s",
        MCPSettings.HOST,
        MCPSettings.PORT,
    )
    logger.info("Targeting Howler instance at %s", MCPSettings.BASE_URL)

    mcp.run(transport="streamable-http")
