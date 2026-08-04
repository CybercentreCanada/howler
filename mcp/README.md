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

| Tool             | Backend path              | Method | Purpose                                                     |
| ---------------- | ------------------------- | ------ | ----------------------------------------------------------- |
| WhoAmI           | /user/whoami              | GET    | Return current user identity and roles.                     |
| ListAssignedHits | /hit/user                 | GET    | Return hits assigned to the authenticated user.             |
| AddCommentToHit  | /hit/{hit_id}/comments    | POST   | Append an analyst comment to a hit.                         |
| GetHitFields     | /search/fields/hit        | GET    | Return valid searchable fields for hit Lucene queries.      |
| GetFieldValues   | /search/facet/hit/{field} | GET    | Return value distribution for one field.                    |
| luceneQuery      | /search/hit               | POST   | Execute Lucene search with field projection and pagination. |

Important note: older helper tools such as ListAlerts, GetHitById, SearchHitsWithIndicators, GetFalsePositiveHits, and ListHitsByAnalytic were replaced by luceneQuery plus discovery helpers GetHitFields and GetFieldValues.

## Prompt Surface

The server currently registers prompt guidance for:

- WhoAmI
- ListAssignedHits
- AddCommentToHit
- GetFieldValues
- GetHitFields
- luceneQuery

## Project Layout

- howler_mcp/server.py: FastMCP server construction and lifecycle.
- howler_mcp/auth.py: JWT verifier and token pass-through provider.
- howler_mcp/api.py: HTTP client wrapper for Howler API.
- howler_mcp/tools.py: MCP tool registration and validation logic.
- howler_mcp/prompts.py: Prompt registration.
- howler_mcp/config.py: Environment-driven config with HTTPS enforcement for non-local hosts.
- howler_mcp/dev_setup.py: local developer bootstrap helper.

## Development Helper (dev_setup)

The dev helper script exists for local development with the dockerized test realm:

- Writes mcp/.env with local defaults.
- Optionally verifies Keycloak reachability.
- Optionally fetches a local dev bearer token.
- Optionally writes .vscode/mcp.json Authorization header for instant local MCP usage.

This local token write is intentional for developer productivity in local docker environments. Non-development environments are expected to use proper secret handling and environment-specific auth setup managed by the operator.

Typical usage from mcp/:

- poetry run python -m howler_mcp.dev_setup
- poetry run python -m howler_mcp.dev_setup --verify
- poetry run python -m howler_mcp.dev_setup --token
- poetry run python -m howler_mcp.dev_setup --start

## Environment Variables

Primary runtime variables:

- HOWLER_API_BASE_URL
- HOWLER_API_TIMEOUT
- AUTH_ISSUER
- AUTH_JWKS_URI
- AUTH_TOKEN_URL
- AUTH_CLIENT_ID
- AUTH_CLIENT_SECRET (optional in local public-client flow, often required in managed deployments)
- MCP_BASE_URL
- MCP_HOST
- MCP_PORT
- MCP_AUDIENCE
- MCP_SCOPE

Config guardrails:

- config.py allows http only for localhost, 127.0.0.1, and ::1.
- non-local endpoints must use https.

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

## Deployment Notes

Container:

- docker build -t howler-mcp-server:latest .
- docker compose up -d

Repository compose currently uses host networking for local simplicity. For production, use explicit container networking and ingress policy controls.

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
- use GetHitFields and GetFieldValues before complex luceneQuery filters.

## Security Model Summary

- Authentication and authorization are enforced by JWT verification and downstream API controls.
- Tool-level validation focuses on request correctness and usability.
- API-side validation remains authoritative for enforcement.
