---
status: accepted
---

# Replace hit bundles with Cases and compatibility shims

Nested bundle fields on `Hit` could not support hierarchical folders, heterogeneous evidence (`Event`, `Case`, references, markdown), or rule-driven correlation, so grouping was moved to dedicated `Case` documents under `/api/v2/case/`. Existing ingestion producers that still call legacy bundle operations are served by `api/howler/services/bundle_compat_service.py`, which translates a bundle into an auto-created `Case` and links root/child hits via `howler.related` back-references without retaining bundle-specific fields in the `Hit` schema.

## Consequences

- Legacy bundle callers continue operating without schema changes on `Hit`, at the cost of maintaining the translation shim until legacy producers migrate to `/api/v2/case/`.
- Finding the `Case` corresponding to a legacy bundle hit depends on `howler.related` back-references populated by `case_service.append_case_item`.
