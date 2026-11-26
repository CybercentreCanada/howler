---
status: proposed
---

# Replace post-definition ODM mutation with startup subclass model extensions

Proposed on the `elasticsearch-dsl` branch, plugins and optional features (such as Clue) declare extra fields via `ModelExtensionRegistry` (`howler.models.extensions`) rather than mutating model descriptors in place via `modify_odm` (`add_namespace`/`remove_namespace`). Because Pydantic models cannot safely support post-definition descriptor mutation, the registry collects `ContextVar`-scoped declarations and finalizes one derived Python subclass per target model at datastore startup before any Elasticsearch mappings are generated.

## Consequences

- Base model classes (such as `Hit`) remain immutable, while runtime schemas and generated Elasticsearch mappings always reflect the finalized startup subclass.
- Plugins must declare typed extensions through `modules.models.declare_extensions`; legacy `modify_odm`-only plugins fail fast at datastore initialization.
