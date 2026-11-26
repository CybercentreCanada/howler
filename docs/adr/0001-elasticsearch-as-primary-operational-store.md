---
status: accepted
---

# Use Elasticsearch as the sole primary operational store

Howler stores every persistent collection—including `hit`, `event`, `case`, `user`, `action`, `overview`, `template`, `view`, `dossier`, `analytic`, and `migration`—in Elasticsearch via `HowlerDatastore` (`api/howler/datastore/howler_store.py`) rather than pairing a relational database with an Elasticsearch search index. This inherits Assemblyline's `ESStore` abstraction and avoids running, backing up, and synchronizing two databases across deployments, while allowing Index Lifecycle Management (`ILM_ENABLED_INDEXES`) on high-volume collections (`hit`, `event`, `case`).

## Consequences

- Cross-entity relationships use document references (such as `howler.related` and `CaseItem` IDs) rather than relational joins or multi-document ACID transactions.
- Concurrency control relies on Elasticsearch optimistic concurrency (`_version`) rather than database row locks.
