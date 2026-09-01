# Howler MCP Server

## Overview

Howler MCP is a FastMCP server that exposes authenticated Howler search and triage tools.

Request flow:

1. The MCP runtime provides the caller bearer token.
2. The server validates token signature and claims using Keycloak JWKS.
3. The same user token is forwarded to the Howler API.
4. The tool returns the Howler API result.

This service intentionally uses token pass-through. It does not mint a second backend token.

## Current Tool Surface

The server currently registers these tools:

| Tool                   | Backend path              | Method | Purpose                                                     |
| ---------------------- | ------------------------- | ------ | ----------------------------------------------------------- |
| whoami                 | /user/whoami              | GET    | Return current user identity and roles.                     |
| craft_howler_url       | —                         | —      | Build a UI URL for a hit or event object.                   |
| list_assigned_hits     | /hit/user                 | GET    | Return hits assigned to the authenticated user.             |
| add_comment_to_hit     | /hit/{hit_id}/comments    | POST   | Append an analyst comment to a hit.                         |
| get_hit_fields         | /search/fields/hit        | GET    | Return valid searchable fields for hit Lucene queries.      |
| get_field_values       | /search/facet/hit/{field} | GET    | Return value distribution for one field.                    |
| lucene_query           | /search/hit               | POST   | Execute Lucene search with field projection and pagination. |
| create_dossier         | /dossier/                 | POST   | Create a reusable dossier from a Lucene query.              |
| create_dossier_for_hit | /hit/{hit_id}/update      | PUT    | Append dossier leads to one alert.                          |

Important note: older helper tools such as ListAlerts, GetHitById, SearchHitsWithIndicators, GetFalsePositiveHits, and ListHitsByAnalytic were replaced by lucene_query plus discovery helpers get_hit_fields and get_field_values.

## Prompt Surface

The server currently registers prompt guidance for:

- whoami
- list_assigned_hits
- craft_howler_url
- add_comment_to_hit
- get_field_values
- get_hit_fields
- lucene_query
- create_dossier
- create_dossier_for_hit

## Capability Summary

Current server capabilities:

- Authenticates requests by validating JWT signature and claims via Keycloak JWKS.
- Forwards the validated user token to Howler API (token pass-through model).
- Exposes analyst triage tools for identity checks, assigned-hit retrieval, commenting, field discovery, and Lucene hit search.
- Validates Lucene query fields against backend-exposed searchable fields before issuing search requests.
- Creates reusable query dossiers or appends dossier leads to a single alert.
- Use `create_dossier` only for dossiers applying to a large number of alerts; use `create_dossier_for_hit` when the target alert list contains exactly one alert.

## Project Layout

- howler_mcp/server.py: FastMCP server construction and lifecycle.
- howler_mcp/auth.py: JWT verifier and token pass-through provider.
- howler_mcp/api.py: HTTP client wrapper for Howler API.
- howler_mcp/tools.py: MCP tool registration and validation logic.
- howler_mcp/prompts.py: Prompt registration.
- howler_mcp/config.py: Environment-driven config with HTTPS enforcement for non-local hosts.
- dev/dev_setup.py: local developer bootstrap helper.

## Development Helper (dev_setup)

The dev helper script exists for local development with the dockerized test realm:

- Writes mcp/.env with local defaults.
- Optionally verifies Keycloak reachability.
- Optionally fetches a local dev bearer token.
- Optionally writes .vscode/mcp.json Authorization header for instant local MCP usage.

By default, `--start` only manages the MCP server itself (clears its port, verifies Keycloak,
fetches a token, updates `.vscode/mcp.json`, and runs the server). Dependencies
(elasticsearch/redis/keycloak/howler-api) are assumed to already be running; start them
separately with `docker compose up -d` (from api/dev/) if needed.

This local token write is intentional for developer productivity in local docker environments. Non-development environments are expected to use proper secret handling and environment-specific auth setup managed by the operator.

Security note: `mcp/.env` and `.vscode/mcp.json` are gitignored and chmod'd to 0600 by the
script right after writing, since neither VS Code's `http` server transport (`headers`/`oauth`
only, no `env`/`envFile`) nor `docker compose` support pulling these values from an environment
variable at that point — a literal dev-only secret is unavoidable for zero-prompt automation.
Static analysis findings about clear-text secret storage on these lines are expected and
mitigated by file permissions rather than suppressed by design changes.

Typical usage from mcp/:

- poetry run python -m dev.dev_setup
- poetry run python -m dev.dev_setup --verify
- poetry run python -m dev.dev_setup --token
- poetry run python -m dev.dev_setup --start

## Environment Variables

Primary runtime variables:

- HOWLER_API_BASE_URL
- HOWLER_UI_BASE_URL (defaults to `http://localhost:3000`)
- HOWLER_API_TIMEOUT
- HOWLER_API_MAX_CONNECTIONS
- HOWLER_API_MAX_KEEPALIVE_CONNECTIONS
- HOWLER_API_KEEPALIVE_EXPIRY
- AUTH_ISSUER
- AUTH_JWKS_URI
- AUTH_TOKEN_URL
- AUTH_CLIENT_ID
- AUTH_CLIENT_SECRET (optional in local public-client flow, often required in managed deployments)
- MCP_BASE_URL
- MCP_HOST
- MCP_PORT
- MCP_LOG_LEVEL
- MCP_AUDIENCE
- MCP_SCOPE

Config guardrails:

- config.py allows http only for localhost, 127.0.0.1, and ::1.
- non-local endpoints must use https.
- config.py calls `load_dotenv()` (mirroring api/howler/app.py), so a `mcp/.env` file is
  picked up automatically on import; vars already exported in the shell take precedence.

## Local Run

From mcp/:

1. poetry install
2. poetry run python -m howler_mcp.server

Why module execution is used:

- package-relative imports require module execution from project root.

## Tests

Unit tests (mocked API, no network):

- poetry run pytest test/tools_unit_test.py -v
- poetry run pytest test/api_unit_test.py -v

Optional live network tests:

1. export RUN_MCP_NETWORK_TESTS=1
2. export TEST_AUTH_USERNAME=<username>
3. export TEST_AUTH_PASSWORD=<password>
4. export TEST_AUTH_EMAIL=<email>
5. poetry run pytest test/network_connection_test.py -v

## Linting and Validation

Run Ruff linting and formatting from `mcp/`:

- `poetry run ruff check .`
- `poetry run ruff format .`

## Deployment Notes

Container:

- docker build -t howler-mcp-server:latest .
- docker compose up -d

Repository compose currently uses host networking for local simplicity. For production, use explicit container networking and ingress policy controls.

The shared Howler API HTTP client is created when the streamable-HTTP application starts, using the configured connection limits, and is closed when the application shuts down.

Kubernetes recommendations:

- inject secrets via Kubernetes Secret.
- restrict ingress and egress paths.
- add readiness and liveness probes.
- monitor token verification failures and backend authorization failures.

## Common Failures

401 or 403 from MCP:

- token missing MCP_SCOPE.
- token audience missing MCP_AUDIENCE.
- issuer or JWKS mismatch.

401 or 403 from Howler API:

- forwarded user token is not accepted by backend policies.

Empty/failed query execution:

- invalid field names in Lucene query.
- invalid values for enumerated fields.
- use get_hit_fields and get_field_values before complex lucene_query filters.

## Security Model Summary

- Authentication and authorization are enforced by JWT verification and downstream API controls.
- Tool-level validation focuses on request correctness and usability.
- API-side validation remains authoritative for enforcement.
