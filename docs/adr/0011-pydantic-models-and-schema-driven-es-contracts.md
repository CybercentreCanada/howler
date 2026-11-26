---
status: proposed
---

# Replace custom ODM with Pydantic models and schema-driven ES contracts

Proposed on the `elasticsearch-dsl` branch, Howler replaces the custom Assemblyline-derived `howler.odm` layer with Pydantic v2 models under `howler.models`, paired with schema-driven Elasticsearch index, mapping, and ILM contract generation (`howler.models.schema` and `howler.datastore.ilm_contract`). The custom ODM required maintaining a bespoke validation/serialization engine and manual mapping helpers, whereas Pydantic provides standard static typing, validation, and IDE support while keeping generated Elasticsearch mappings compatible with existing indices.

## Consequences

- All internal packages and plugins (`evidence`, `sentinel`, `sync`) migrate from `howler.odm` field descriptors to Pydantic annotations and `howler.models`.
- Index settings, dynamic templates, and ILM contract comparisons are derived directly from the finalized Pydantic model registry rather than hand-maintained mapping templates.
