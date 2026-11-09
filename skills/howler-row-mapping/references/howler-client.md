# Howler-client 3.4.0 mapping API

The helper scripts use the released `howler-client==3.4.0`. Their PEP 723 dependency is:

```text
howler-client==3.4.0
```

Update all script version pins and these references together when adopting a
newer release. No Git dependency or local editable checkout is required.

The released client's public
`RowMapping` and `map_rows` API is the sole mapping parser, schema validator, and
execution engine used by this skill.

## Offline mapping

```python
from howler_client import RowMapping, map_rows

# `fields_snapshot` and `saved_rows` are loaded from local artifacts.
mapping = RowMapping.from_file(
    "mapping.yaml", fields=fields_snapshot["fields"]
)
for hit, error in map_rows(saved_rows, mapping):
    if error is not None:
        save_private_error(error)
    else:
        save_private_hit(hit)
```

The file wrapper is preferred: it reads local artifacts and refuses to publish
partial alert output. Applications using the API directly must consume every
result and apply their own file/privacy policy.

- `RowMapping(document, fields=...)`, `RowMapping.from_file(path, fields=...)`,
  and `RowMapping.from_yaml(text, fields=...)` construct compiled mappings.
- `map_rows(rows, mapping)` accepts a `RowMapping`, a document, or a YAML file
  path. A string passed directly to `map_rows` is a path, not YAML text. Supply
  fields when compiling; do not pass them again for an existing mapping.
- The iterator lazily yields one `(hit, None)` or `(None, MappingError)` per row
  in order, continuing after mapping errors. Configuration errors occur before
  source iteration; source-iterator exceptions propagate.
- `mapping.map_row(row)` returns one nested hit or raises `MappingError`.
  `mapping.mapping` returns a detached document copy.
- `{op: template, template: "Detected {value}"}` is a native transform: it
  formats only the current scalar mapped value. It cannot read another column,
  execute code, or provide a null fallback. Use `json` first for structured values.
- `include_raw_data` defaults to `true`. A detached, JSON-compatible object copy of
  the entire untransformed source row is prepended to `howler.data`; explicit data
  entries follow it. Set `false` to disable only that automatic entry.

## Validation responsibility

The client uses its bundled Draft 2020-12 schema plus native checks. With field
metadata it checks mapped target existence/deprecation and list targets for
`concat`. Row application checks source lookups, null handling, and transforms.
The client intentionally does not validate output types/list shape, enums,
regexes, required backend values, or classification permission. Howler backend
validation is authoritative for backend acceptance; neither local nor backend
validation is ingestion authorization.

The skill additionally requires summary coverage and source-grounded outline
semantics during authoring and private output review; these are not client schema
checks. Do not implement a second mapping engine or target-value validator to
enforce them. See [outline authoring](outline.md).

An already-connected client exposes backend validation as
`client.v2.ingest.validate("hit", records)`. The file helper
`scripts/validate_ingestion.py` calls that same validation endpoint using the
saved records. It remains a direct REST client to preserve the full HTTP
envelope, finite timeout, no-redirect behavior, field-snapshot checks, and
private file reporting; it does not implement mapping or schema validation.
Never use an ingestion/create method in this workflow.
