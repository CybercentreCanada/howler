import os


class HOWLER_API:
    VERSION = os.environ.get("HOWLER_API_VERSION", "v1")
    HOST = os.environ.get("HOWLER_API_HOST", "localhost")
    PORT = os.environ.get("HOWLER_API_PORT", "3000")
    BASE_URL = os.environ.get(
        "HOWLER_API_BASE_URL", f"http://{HOST}:{PORT}/api/{VERSION}"
    )
    AUDIENCE = os.environ.get("HOWLER_API_AUDIENCE", "howler")
    SCOPE = os.environ.get("HOWLER_API_SCOPE", "howler")
    TIMEOUT = float(os.environ.get("HOWLER_API_TIMEOUT", "5.0"))


class AUTH:
    HOST = os.environ.get("AUTH_HOST", "localhost")
    PORT = os.environ.get("AUTH_PORT", "9100")
    REALM = os.environ.get("AUTH_REALM", "HogwartsMini")
    TOKEN_URL = os.environ.get(
        "AUTH_TOKEN_URL",
        f"http://{HOST}:{PORT}/realms/{REALM}/protocol/openid-connect/token",
    )
    CLIENT_ID = os.environ.get("AUTH_CLIENT_ID", "howlermcp")
    CLIENT_SECRET = os.environ.get("AUTH_CLIENT_SECRET", "lalala:)")
    JWKS_URI = os.environ.get(
        "AUTH_JWKS_URI",
        f"http://{HOST}:{PORT}/realms/{REALM}/protocol/openid-connect/certs",
    )
    ISSUER = os.environ.get("AUTH_ISSUER", f"http://{HOST}:{PORT}/realms/{REALM}")
    AS_SERVER_URL = os.environ.get(
        "AUTH_AS_SERVER_URL", f"http://{HOST}:{PORT}/realms/{REALM}"
    )


class MCPSettings:
    HOST = os.environ.get("MCP_HOST", "0.0.0.0")
    PUBLIC_HOST = os.environ.get(
        "MCP_PUBLIC_HOST", "localhost" if HOST in {"0.0.0.0", "::"} else HOST
    )
    PORT = os.environ.get("MCP_PORT", "8000")
    BASE_URL = os.environ.get("MCP_BASE_URL", f"http://{PUBLIC_HOST}:{PORT}/mcp")
    SCOPE = os.environ.get("MCP_SCOPE", "howlermcp:access")
    AUDIENCE = os.environ.get("MCP_AUDIENCE", "howlermcp")
