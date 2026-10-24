---
name: howler-row-mapping
description: Create, augment, explain, and apply reusable howler-client version-1 YAML mappings from saved JSONL row objects to Howler alerts, including safe template transforms and howler.outline (always summary, relevant target/threat, indicators wherever possible). Use RowMapping/map_rows and the client's bundled schema, discover targets through the Howler hit-index API, and keep source rows, rendered records, and validation responses in files rather than prompts. Render and validate only; never ingest.
---

# Howler-client YAML row mappings

Use the released `howler-client==3.4.0` mapping API, including the safe `template` transform
from merged PR [#689](https://github.com/CybercentreCanada/howler/pull/689) and
raw-row preservation from [#688](https://github.com/CybercentreCanada/howler/pull/688),
to create a reusable, deterministic mapping. Apply it only to already-acquired JSONL row objects.
Mapping and rendering do not call Howler, execute code from YAML, read the clock,
generate random IDs, alter source rows, or ingest alerts.

`RowMapping` and `map_rows` own YAML parsing, the bundled schema, mapping
semantics, and client-side checks. Do not copy the schema or add a custom loader,
mapping engine, or target-value validator. See [the YAML contract](references/yaml-format.md)
for the supported language and [the client reference](references/howler-client.md)
for API and validation responsibilities.

**Map `howler.outline` through the same YAML mapping, not by editing rendered
alerts.** Always provide a meaningful, nonblank `howler.outline.summary` for every
row. Set `howler.outline.target` and `howler.outline.threat` only when the source
and analytic establish a victim and attacker, respectively; omit them otherwise.
Map `howler.outline.indicators` whenever supported source observables are available.
See [outline authoring](references/outline.md) for field selection, templates,
list transforms, and null handling. These are authoring requirements, not extra
client schema rules.

**Never set `howler.id`.** It is server-generated; it is not a writable target,
even when supplied as null or through a parent object. The client and API helper
reject it. Determinism describes submitted payloads only, not server-assigned IDs
or deduplication.

## Inputs and files

Offline profiling, validation, and rendering need only the saved JSONL row
objects, a mapping YAML file, and a supplied hit-index field snapshot. They do
not require environment URLs or credentials. Confirm which Howler environment
and index the mapping targets before authoring it. The network workflow supports
the `hit` index and its validation endpoint only; it never ingests. If another
index is intended, stop rather than silently using `hit`.

Use Python 3.12+ and `uv`. Every bundled PEP 723 script pins
`howler-client==3.4.0`, the release used by this skill for native template
transforms and raw-row preservation. Initial dependency installation needs
network access; mapping itself remains offline once cached. See the
[client reference](references/howler-client.md) for the API contract.
Set `SKILL` to this skill directory and `WORK` to a private, ignored directory
for artifacts. Only network stages need the selected environment's
`HOWLER_API_URL` and API token file (`HOWLER_TOKEN_FILE`). Commands also accept
a supplied token in `HOWLER_JWT`.
Never print credentials or place them in output files.

| File                            | Purpose                                                                                          |
| ------------------------------- | ------------------------------------------------------------------------------------------------ |
| `scripts/mapping.py`            | File-first profile, draft, augmentation, client validation, and rendering; no service calls.     |
| `scripts/api_fields.py`         | Materialize hit-index field metadata from `/api/v1/search/fields/hit`.                           |
| `scripts/validate_ingestion.py` | Send saved alert JSONL to Howler's validation API and save its complete response; never ingests. |
| `references/yaml-format.md`     | Detailed client-native YAML language contract.                                                   |
| `references/howler-client.md`   | Released client API examples and division of validation responsibilities.                        |
| `references/outline.md`         | Summary, relevant target/threat, and indicator mappings using native transforms.                 |

Keep the working directory private and out of version control. Typical artifacts:

```text
results.jsonl                 # supplied source rows; do not edit
source_profile.json           # value-free profile
hit_fields.json               # supplied or freshly fetched field snapshot
mapping.yaml                  # reusable mapping, no sampled values
field_spec.yaml               # optional saved fragment for augmentation
local_validation.json         # client checks and sample diagnostics
alerts.jsonl                  # deterministic rendered records
render_validation.json        # per-row render diagnostics and provenance
hit_fields_current.json       # fresh catalog used before backend validation
backend_validation.json       # complete response and provenance
```

The helpers use private, atomic writes and protect inputs from accidental
replacement. Do not put raw rows, generated records, credentials, or reports with
rejected inputs in prompts or commits. Inspect saved artifacts with local tools.
The scripts load the JSONL row objects into memory, so use a file of appropriate
size.

Commands do not overwrite existing outputs by default. For reruns, choose new
output names or use `--replace` for the intended output only; never replace the
saved input rows or field snapshot.

## Workflow

### 1. Profile the supplied rows

```bash
uv run --script "$SKILL/scripts/mapping.py" inspect \
  --rows "$WORK/results.jsonl" --output "$WORK/source_profile.json"
```

The profile reports observed JSON types, missing keys, and null counts without
including sample values. It is descriptive, not a guarantee about future rows.
If field meaning or semantics are unclear, ask the user before mapping; do not
infer meaning from a name or type alone.

### 2. Use the supplied target snapshot or discover current fields

Use a supplied snapshot for offline authoring. To fetch or refresh target
metadata, call the Howler API's hit-index fields endpoint directly:

```bash
uv run --script "$SKILL/scripts/api_fields.py" fields \
  --api-url "$HOWLER_API_URL" --token-file "$HOWLER_TOKEN_FILE" \
  --output "$WORK/hit_fields.json"
```

The saved snapshot includes projected field names, descriptions, types, and list
flags, the API URL, and a SHA-256 fingerprint. Review relevant target metadata;
the endpoint may omit constraints such as required fields, enums, or regexes.
This helper writes snapshot version 2; refresh any older MCP-derived snapshot
before using it with this version of the skill.

### 3. Create or augment a native mapping

For a new mapping, create a draft:

```bash
uv run --script "$SKILL/scripts/mapping.py" init \
  --output "$WORK/mapping.yaml"
```

An empty draft is not a valid `RowMapping`. The draft explicitly enables the
client's default `include_raw_data: true`, which preserves the complete original
row as the first detached object in `howler.data`, before transformations. Review
unmapped source columns for sensitive data and confirm that retaining the whole
row is appropriate for the selected environment and classification. If not,
explicitly set `include_raw_data: false` in the mapping and report that decision;
this disables only the automatic entry, not an explicit `howler.data` mapping.

Author the mapping in the client's native
format; see the [YAML reference](references/yaml-format.md). Ask the user to
resolve uncertain column meanings, Howler/ECS targets, analytic labels, and
classification choices. When a column's meaning or target is uncertain, present
supported alternatives and wait for the user's selection before mapping it. It
may remain unmapped or deferred while unresolved. Do not invent operational
values, downgrade source classification to pass validation, or treat a partially
resolved draft as approved.

For new and augmented mappings, review all four outline fields against the
selected catalog and [outline guidance](references/outline.md). Require a summary
mapping with `on_null: error`, even if the document defaults to `omit`. Use a
source description or a source-grounded, user-approved `{value}` template; when
no suitable row column exists, use a user-approved constant that truthfully
describes every row. Never use a sampled value or filler such as "Unknown".
Resolve missing, null, or blank summary sources before considering the mapping
complete. Templates can use only the current mapped value, not multiple columns.
Leave unsupported target/threat fields unmapped, and document why indicators
cannot be populated when no supported observable is available.

An optional saved YAML fragment can add one target:

```yaml
column: user_principal_name
on_null: omit
transforms: [trim]
```

```bash
uv run --script "$SKILL/scripts/mapping.py" add \
  --mapping "$WORK/mapping.yaml" --fields "$WORK/hit_fields.json" \
  --target user.email --spec "$WORK/field_spec.yaml" \
  --output "$WORK/mapping_augmented.yaml"
```

Augmentation compiles the resulting document with `RowMapping` before saving.
Existing targets require `--replace-field`; existing output files require
`--replace`. YAML rewriting does not preserve comments/formatting. After
augmentation, explicitly use the new output file in subsequent commands.

### 4. Validate locally and render

```bash
uv run --script "$SKILL/scripts/mapping.py" validate \
  --mapping "$WORK/mapping.yaml" --fields "$WORK/hit_fields.json" \
  --rows "$WORK/results.jsonl" --output "$WORK/local_validation.json"

uv run --script "$SKILL/scripts/mapping.py" render \
  --mapping "$WORK/mapping.yaml" --fields "$WORK/hit_fields.json" \
  --rows "$WORK/results.jsonl" --output "$WORK/alerts.jsonl" \
  --report "$WORK/render_validation.json"
```

The helper compiles through `RowMapping` and applies saved rows through
`map_rows`. Client schema/configuration checks and per-row mapping failures are
not backend acceptance; consult the [client reference](references/howler-client.md)
for scope. The client yields a result for every row and continues after a row
error. Errors are saved privately; the helper writes no alert JSONL unless every
row succeeds. It never silently drops rows.

Before backend validation, inspect the saved output privately: every alert must
have a meaningful, nonblank summary; target/threat must be justified wherever
present; and available indicators must be represented as a list. A successful
client render alone does not check these semantic requirements or reject blank
strings. Fix the YAML or resolve source-data limitations, then rerender; never
postprocess the generated outline.

### 5. Validate the saved output through Howler

Fetch a fresh field snapshot immediately before backend validation, then pass
both the pinned and current snapshots:

```bash
uv run --script "$SKILL/scripts/api_fields.py" fields \
  --api-url "$HOWLER_API_URL" --token-file "$HOWLER_TOKEN_FILE" \
  --output "$WORK/hit_fields_current.json"

uv run --script "$SKILL/scripts/validate_ingestion.py" \
  --records "$WORK/alerts.jsonl" --fields "$WORK/hit_fields.json" \
  --current-fields "$WORK/hit_fields_current.json" \
  --api-url "$HOWLER_API_URL" --token-file "$HOWLER_TOKEN_FILE" \
  --output "$WORK/backend_validation.json"
```

The helper refuses field-snapshot drift and requires the API and saved field metadata to
share the same HTTPS origin. It sends the saved record array to
`POST /api/v2/ingest/hit/validate` (not the create/ingest route), uses a finite
timeout, refuses redirects, and saves the full HTTP response privately. Backend
validation does not prove write/classification permission or guarantee every
future row is valid. Fix the mapping, rerender from the original rows, and
validate the new output; never edit generated alerts to obtain a pass.

### 6. Report the result

Return the confirmed environment and index, mapping/snapshot/output/report paths,
sample count, unresolved decisions or approved omissions, and which local and
backend checks passed or were not run. Include the summary strategy, target/threat
relevance decisions, indicator coverage or limitations, and raw-data retention
choice. Keep the field snapshot with the mapping;
the YAML itself does not include its catalog fingerprint. Refreshing metadata is
explicit: review changed fields and deliberately select the new snapshot.
