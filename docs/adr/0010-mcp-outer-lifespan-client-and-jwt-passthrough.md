---
status: accepted
---

# Scope MCP HTTP client to Starlette lifespan and pass through caller JWTs

`mcp/howler_mcp/server.py` attaches the shared `HowlerApiClient` (`httpx.AsyncClient`) to Starlette's outer router lifespan (`_with_api_client_lifespan`) instead of FastMCP's per-session lifespan, sharing one connection pool across sessions rather than leaking or tearing down per-session clients. Incoming MCP requests are authenticated via `JSONWebTokenVerifier` against the configured OAuth/OIDC issuer and forwarded to the Howler API using the caller's token rather than a privileged service account.

## Considered Options

- **Service-account credentials on the MCP server**: Rejected because it would bypass Howler's per-user RBAC, security classification filtering, and audit logging.
- **FastMCP per-session lifespan**: Rejected because it ties process-wide connection-pool lifecycle to individual client sessions.

## Consequences

- Downstream Howler API calls enforce the invoking user's exact permissions and classification ceiling, and only clients owned by the Starlette application lifespan are closed on shutdown.
