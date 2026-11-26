---
status: accepted
---

# Isolate breaking endpoints under v2 and enforce ETag concurrency

Howler introduces breaking entity, search, and ingestion semantics (`case`, `fuzzy`, `ingest`, `search`, `task`) under `/api/v2/` alongside existing `/api/v1/` blueprints rather than mutating v1 contracts in place. For optimistic concurrency on mutable Elasticsearch documents, endpoints use `@add_etag()` (`api/howler/api/v1/utils/etag.py`) to expose document `_version` values as HTTP `ETag` headers and validate conditional `If-Match` requests instead of implementing distributed write locks.

## Consequences

- Route handlers returning `(Response, version)` tuples must be wrapped with `@add_etag()`, because unwrapped Flask `(Response, version)` returns are interpreted by Flask as `(Response, status_code)`.
- Getter-backed `@add_etag(getter=...)` endpoints receive prefetched `record` and `server_version` kwargs when the route supplies an expected ID keyword (`id`, `case_id`, or `username`).
