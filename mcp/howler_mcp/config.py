import os
from urllib.parse import urlparse


def _require_https_for_non_local(url: str, env_name: str) -> str:
    """Allow HTTP only for local development endpoints.

    For production-like deployments, non-local endpoints must use HTTPS.
    """
    parsed = urlparse(url)

    if parsed.scheme not in {"http", "https"}:
        raise ValueError(
            f"{env_name} must use http or https scheme. Got: {parsed.scheme!r}"
        )

    # Verify if the request go outside of the local host. If yes is it HTTPS? if no, not allowed
    if parsed.scheme == "http" and str(parsed.hostname).strip().lower() not in {
        "localhost",
        "127.0.0.1",
        "::1",
    }:
        raise ValueError(f"{env_name} must use https for non-local hosts. Got: {url}")

    return url


class HOWLER_API:
    VERSION = os.environ.get("HOWLER_API_VERSION", "v1")
    HOST = os.environ.get("HOWLER_API_HOST", "localhost")
    PORT = os.environ.get("HOWLER_API_PORT", "3000")
    BASE_URL = _require_https_for_non_local(
        os.environ.get("HOWLER_API_BASE_URL", f"http://{HOST}:{PORT}/api/{VERSION}"),
        "HOWLER_API_BASE_URL",
    )
    AUDIENCE = os.environ.get("HOWLER_API_AUDIENCE", "howler")
    SCOPE = os.environ.get("HOWLER_API_SCOPE", "howler")
    TIMEOUT = float(os.environ.get("HOWLER_API_TIMEOUT", "5.0"))


class AUTH:
    HOST = os.environ.get("AUTH_HOST", "localhost")
    PORT = os.environ.get("AUTH_PORT", "9100")
    REALM = os.environ.get("AUTH_REALM", "HogwartsMini")
    TOKEN_URL = _require_https_for_non_local(
        os.environ.get(
            "AUTH_TOKEN_URL",
            f"http://{HOST}:{PORT}/realms/{REALM}/protocol/openid-connect/token",
        ),
        "AUTH_TOKEN_URL",
    )
    CLIENT_ID = os.environ.get("AUTH_CLIENT_ID", "howlermcp")
    CLIENT_SECRET = os.environ.get("AUTH_CLIENT_SECRET")
    JWKS_URI = _require_https_for_non_local(
        os.environ.get(
            "AUTH_JWKS_URI",
            f"http://{HOST}:{PORT}/realms/{REALM}/protocol/openid-connect/certs",
        ),
        "AUTH_JWKS_URI",
    )
    ISSUER = _require_https_for_non_local(
        os.environ.get("AUTH_ISSUER", f"http://{HOST}:{PORT}/realms/{REALM}"),
        "AUTH_ISSUER",
    )
    AS_SERVER_URL = _require_https_for_non_local(
        os.environ.get("AUTH_AS_SERVER_URL", f"http://{HOST}:{PORT}/realms/{REALM}"),
        "AUTH_AS_SERVER_URL",
    )


class MCPSettings:
    HOST = os.environ.get("MCP_HOST", "0.0.0.0")
    PUBLIC_HOST = os.environ.get(
        "MCP_PUBLIC_HOST", "localhost" if HOST in {"0.0.0.0", "::"} else HOST
    )
    PORT = os.environ.get("MCP_PORT", "8000")
    BASE_URL = _require_https_for_non_local(
        os.environ.get("MCP_BASE_URL", f"http://{PUBLIC_HOST}:{PORT}/mcp"),
        "MCP_BASE_URL",
    )
    SCOPE = os.environ.get("MCP_SCOPE", "howlermcp:access")
    AUDIENCE = os.environ.get("MCP_AUDIENCE", "howlermcp")
