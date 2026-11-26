---
status: accepted
---

# Version seven monorepo packages independently with Release Please

Howler keeps `api/`, `ui/`, `client/`, `mcp/`, `plugins/evidence/`, `plugins/sentinel/`, and `plugins/sync/` in one repository for coordinated cross-layer changes and shared CI, while configuring path-scoped Release Please (`.release-please-config.json`, `docs/patching.md`) to release each package independently with `<component>-vX.Y.Z` tags. Lockstep versioning was rejected because UI, SDK, MCP, or plugin fixes should not force unnecessary API releases or container rebuilds.

## Consequences

- Release Please scopes releases by changed file paths rather than commit-message scope tags, so changes meant for one package must stay inside that package's directory.
- `GITHUB_TOKEN`-created release tags do not automatically trigger tag-push workflows, so the central Release Please workflow explicitly dispatches each component's publish workflow at its native tag.
