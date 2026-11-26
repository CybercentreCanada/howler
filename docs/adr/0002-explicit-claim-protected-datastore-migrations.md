---
status: accepted
---

# Run datastore migrations explicitly with claim locks

Datastore schema and data migrations are executed explicitly through `howler-migrate` (`api/howler/datastore/migrations/runner.py`) instead of running automatically when the API boots. Because migrations can scan or reindex large Elasticsearch collections and multiple API pods can start concurrently, automatic startup migrations risk startup timeouts, contend across replicas, and leave partial reindexes behind.

## Consequences

- Each migration acquires a `"running"` claim document in the `migration` index using Elasticsearch optimistic concurrency (`CREATE_TOKEN` / `_version`), while peer runners wait or reclaim stale claims after `HWL_MIGRATION_STALE_CLAIM_TIMEOUT`.
- Operators and deployment pipelines must run `howler-migrate` explicitly when releasing changes that include new migrations.
