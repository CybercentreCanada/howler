# Howler-client mapping YAML, version 1

This is the native mapping format implemented by the
[released client 3.4.0](howler-client.md), including raw-row preservation and template
transforms. `RowMapping` owns parsing, document validation, and
mapping execution. This skill does not maintain a parallel schema or mapping
engine.

## Document structure

The following is illustrative, not a production analytic. Use exact source keys
present in the saved row profile, targets in the selected hit-index field
catalog, and user-approved meanings and classification. Do not copy sample values
into constants.

```yaml
version: 1
on_null: error
include_raw_data: true
mappings:
  howler.analytic:
    value: "User-approved analytic label"
  howler.outline.summary:
    column: activity_description
    on_null: error
    transforms: [trim]
  user.id:
    column: principal_id
  user.email:
    column: email
    on_null: omit
    transforms: [trim]
  organization.name:
    column: profile
    path: [organization, name]
    on_null: omit
  user.roles:
    concat: [role_names, elevated_role_names]
  event.created:
    column: observed_at
    transforms:
      - op: timestamp
        assume_timezone: UTC # only if the source is known to be UTC
```

| Key                | Meaning                                                                                         |
| ------------------ | ----------------------------------------------------------------------------------------------- |
| `version`          | Required integer `1`.                                                                           |
| `on_null`          | Document-wide `error` (default) or `omit`; a target may override it.                            |
| `include_raw_data` | Boolean, default `true`; prepend the complete source row as a detached object in `howler.data`. |
| `mappings`         | Nonempty dictionary keyed by exact dotted Howler fields.                                        |

Only those four keys belong at document level. Index, environment, source
provenance, and field-catalog fingerprints belong in separate artifacts, not in
mapping YAML. `version: 1` names the format, not a mapping revision. An empty
draft is not a valid `RowMapping`; unmapped source columns are ignored, so report
unresolved columns and approved omissions explicitly.

Unmapped columns are ignored for target mapping but still retained in the raw
entry when `include_raw_data` is true. Set it to `false` to disable the automatic
entry; explicitly mapped `howler.data` entries remain. Review sensitive columns
and source classification before retaining the complete row.

Always author `howler.outline.summary`; add target/threat only when relevant and
indicators wherever supported. See [outline authoring](outline.md) for examples.

## Source expressions

Each target has exactly one expression:

| Expression                          | Client behavior                                                                                                         |
| ----------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| `column: name`                      | Read an exact top-level row key. Dots in a source key are literal. Missing top-level keys always error.                 |
| `column` plus `path: [key, 0, ...]` | Traverse dictionaries and nonnegative list indexes. A missing nested key/index is null; a wrong container type errors.  |
| `concat: [a, b, ...]`               | Append two or more list-valued columns in order, retaining duplicates. With metadata, the target must be a list field.  |
| `value: ...`                        | Use a JSON-compatible constant. The client validates/transforms it at compile time and returns detached copies per row. |

For `concat`, all named top-level columns must exist; a null value cannot hide a
missing column. If any list is null, the target's null policy applies to the
whole target. Repeating a column repeats its contents. Concatenation is not
string joining, deduplication, filtering, or aggregation.

## Nulls and transforms

Null handling occurs before transforms. The document default is `error`; set a
target's `on_null` to `omit` to omit that whole target. Missing top-level columns,
wrong containers, and failed transforms remain errors. Empty strings, zero,
`false`, and empty lists are not null. A row whose every target is omitted is
rejected.

Transforms run in written order on the whole value:

| Transform                                      | Behavior                                                                                                     |
| ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| `string`                                       | Convert a scalar to string; structured values require `json`.                                                |
| `integer`, `number`                            | Numeric conversion; reject booleans, fractional integers, and non-finite values.                             |
| `boolean`                                      | Accept native booleans or exact strings `"true"` and `"false"`.                                              |
| `trim`, `lower`, `upper`                       | String-only cleanup; change case only when the meaning permits it.                                           |
| `list`                                         | Wrap a non-list in a list; leave an existing list unchanged. No elementwise coercion.                        |
| `json`                                         | Convert to compact JSON text with sorted keys; this does not parse JSON strings.                             |
| `{op: timestamp}`                              | Parse an ISO-8601 string and convert to UTC with six fractional digits and `Z`; source timezone is required. |
| `{op: timestamp, assume_timezone: UTC}`        | Also accept naive/date-only strings only when the source is known to be UTC.                                 |
| `{op: template, template: "Detected {value}"}` | Insert the current scalar value into literal text; use `json` first for lists/objects.                       |

Transforms are not elementwise: for example, apply `trim` before `list` to
convert one string, not after `list`. Templates support only `{value}` (repeatable);
escape literal braces with `{{` and `}}`. Syntax is checked at compile time.
Other placeholders, field access, conversions such as `{value!r}`, format
specifiers such as `{value:03d}`, and unmatched braces are rejected. Templates do
not interpolate another row column or evaluate expressions. Null handling still
occurs first; a template cannot turn a null source into a summary or indicator.

The mapping language has no parser, general expression evaluator, remote lookup,
multi-column string interpolation, conditional, coalesce, or implicit default. Any required
preparation must already be reflected in the supplied row objects or be handled
outside this mapping workflow.

## YAML and output behavior

- `RowMapping.from_file` and `RowMapping.from_yaml` use the client's safe YAML
  parser. Quote constants that must remain strings, including boolean-like words,
  dates, and numeric-looking identifiers. YAML dates, sets, binary values,
  non-finite numbers, and cycles are not JSON-compatible mapping values.
- Do not rely on duplicate keys, aliases, or merge-key tricks. This skill adds no
  custom loader or parser behavior.
- Dotted target fields are expanded into nested objects. Do not map a parent and
  its child (such as `user` and `user.id`).
- The client never sets `howler.id`, including through a parent `howler` object.
  Howler assigns it. Other identifiers such as `user.id` may be mapped.
- No implicit analytic, classification, timestamp, or outline defaults are added.
  The automatic raw-data entry is the only addition described above; it does not
  rescue a row whose every mapped target was omitted.
  Repeated source rows remain repeated payloads; deterministic rendering does not
  promise ingestion deduplication or identical server-created IDs.

## Validation boundaries

Compiling a mapping checks the client's bundled document schema and native
mapping constraints. With field metadata, it also checks target existence and
deprecation and requires a list target for `concat`. Applying rows checks source
lookups, null policies, and transforms; each row produces a success or a mapping
error. The file wrapper saves errors privately and does not write partial alert
output.

The client does not validate mapped target value types, list elements/shape,
enums, regexes, required backend fields, or classification permission. Do not
duplicate those checks in this skill; use Howler's backend validation for its
authoritative acceptance response. Backend validation still does not authorize
ingestion or prove write/classification permission.
