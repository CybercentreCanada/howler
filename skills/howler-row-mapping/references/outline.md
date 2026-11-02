# Authoring `howler.outline` with native mappings

Populate the outline in `mapping.yaml` using `RowMapping`, just like ECS fields.
Do not modify generated alerts or implement a separate outline renderer. Check
each target against the selected hit-index catalog and confirm source meanings.

## Field-selection requirements

- `howler.outline.summary`: **Always.** A meaningful, nonblank executive summary
  of the detected activity for every row, grounded in the source and approved
  analytic meaning. Use a description column, a native scalar template, or an
  approved constant valid for all rows. Set `on_null: error` explicitly.
- `howler.outline.target`: Only when relevant: the identifier best representing
  the victim/affected entity (for example, an account or host). A source/destination
  column is not automatically a victim.
- `howler.outline.threat`: Only when relevant: the identifier best representing
  the attacker/threat entity. An IP, domain, or account is not automatically an
  attacker.
- `howler.outline.indicators`: Whenever possible: a list of source-supported
  observables useful for linking or investigating the detected activity, such as
  IPs, domains, URLs, or hashes. Do not label arbitrary metadata as an IoC or
  invent indicators.

Target/threat relevance is an analytic decision, not a null check. Omit the
mapping entirely when the role is irrelevant or unconfirmed. Where a role is
established but some rows lack its identifier, `on_null: omit` may omit it for
those rows. Missing top-level keys still fail even with `omit`; author against
the saved row shape, not hypothetical columns. For mixed row types where roles
vary, require source preparation or separate approved mappings rather than
pretending YAML can infer relevance conditionally.

A template does not create evidence: its literal wording must be source-grounded
and user-approved. Do not claim compromise, exfiltration, or maliciousness that
the analytic does not establish. Do not use sampled row values as constants.
If no source description exists, ask for a truthful analytic-level summary;
do not finish with a missing summary, empty string, or filler such as "Unknown".

## Example: relevant victim, attacker, and a scalar indicator

This is illustrative, not an approved analytic. It assumes the user has confirmed
that the rows describe suspicious authentication activity, `affected_account`
identifies the affected account, and `attacker_ip` identifies the threat and a
useful observable. Remove target/threat when those roles are not established;
adapt columns and wording to the actual saved rows and approved meaning.

```yaml
version: 1
on_null: omit
include_raw_data: true
mappings:
  howler.analytic:
    value: "User-approved analytic label"
  howler.outline.summary:
    column: affected_account
    on_null: error
    transforms:
      - trim
      - op: template
        template: "Suspicious authentication activity affecting {value}"
  howler.outline.target:
    column: affected_account
    on_null: omit
    transforms: [trim]
  howler.outline.threat:
    column: attacker_ip
    on_null: omit
    transforms: [trim]
  howler.outline.indicators:
    column: attacker_ip
    on_null: omit
    transforms: [trim, list]
```

Apply `trim` (and any justified scalar `string` or `template` transform) before
`list`; transforms are not elementwise. Prefer raw searchable observables for
indicators; add literal context with a template only if useful to the analytic.
Do not wrap an existing indicator list in `json`, which would collapse it into
one JSON-text indicator.

## Example: summary without victim/attacker claims

When a saved row already contains a suitable description, a direct mapping is
preferable to an unnecessary template. This example deliberately has no
target/threat mappings. Add indicators if supported observables exist; if none
do, document that limitation rather than manufacturing them.

```yaml
version: 1
on_null: omit
include_raw_data: true
mappings:
  howler.analytic:
    value: "User-approved analytic label"
  howler.outline.summary:
    column: activity_description
    on_null: error
    transforms: [trim]
```

A user-approved constant summary is also supported via `value: "..."` when it
truthfully describes every row. It must describe the activity, not merely repeat
an arbitrary analytic label. Blank/whitespace-only strings are not null; neither
`trim` nor `on_null: error` rejects them. Privately review source suitability and
rendered summary coverage; a template prefix must not conceal an empty identifier.
Resolve incomplete input or summary wording before declaring the mapping ready.

## Example: combine existing indicator lists

If two confirmed source columns already contain lists of useful indicators, add
this field fragment with `mapping.py add --target howler.outline.indicators`:

```yaml
concat: [network_indicators, file_indicators]
on_null: omit
```

`concat` preserves order and duplicates; it does not filter, deduplicate, stringify
elements, or aggregate rows. Both top-level columns must exist. If either list is
null, the whole target is omitted under this policy, even when the other list
contains indicators. Do not lose available indicators unnoticed: use a suitable
existing non-null list column or resolve source preparation outside this mapping
workflow. An empty list is not null and can be concatenated normally.

Multiple scalar indicator columns cannot be concatenated directly: `concat`
requires lists before transforms run. Request a suitable existing/prepared list
or report the coverage limitation rather than silently discarding useful
observables. Do not repeat a target key to try to append values.

## Template limits and review

Native templates expose only the current `{value}`, not `{affected_account}`,
`{row...}`, Jinja expressions, or multiple columns. Use `{{` and `}}` for literal
braces. For structured summary input, `json` followed by a template is supported,
but a readable description or scalar entity is usually better than a raw JSON
dump. Never copy the entire raw row into the summary simply to meet coverage;
raw telemetry belongs in `howler.data`.

After local rendering, inspect the saved alerts privately and confirm summary
coverage, justified target/threat assignments, and available indicator coverage.
Record omissions and source limitations in the final report. Backend validation
checks acceptance, not analytic truth or the usefulness of the outline. Correct
the mapping and rerender from the original saved rows; never edit alerts to pass.
