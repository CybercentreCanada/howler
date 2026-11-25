# Model compatibility after the ODM migration

## What the regression tests compare

- **Elasticsearch:** [legacy index contracts](../../api/test/unit/models/fixtures/legacy_public_contract.json)
  pin the complete settings and mappings for each of the 12 pre-migration collections,
  including `migration` and the model-free `user_avatar`. Hit is also checked with each
  nonempty combination of Clue, Evidence, and Sentinel, after applying the real typed
  declarations and finalizing the model. The settings use one shard and zero replicas;
  Hit's total-field limit is 1500 without extensions and 2161 with all three.
  JSON object key order is immaterial; array order is preserved because Elasticsearch
  applies the **first** matching dynamic template.
- **Documents:** [readable examples](../../api/test/unit/models/fixtures/legacy_public_contract_examples.json)
  cover a legacy Case read and save (including the top-level storage `id`, nested item
  `id`, `__index` and classification access fields), Hit serialization with integer IPs,
  and the three extension payloads on one Hit. Each fixture identifies its legacy
  commit and source. [The tests](../../api/test/unit/models/test_legacy_parity.py) use
  these local captures; they do not need an old checkout or Elasticsearch.
- **Sync:** `/sync/schema/hit` describes the datastore's finalized Hit. A field without
  a non-null default or factory allows null in Spark. An explicit `optional()` field
  also allows null, even with a non-null default. This rule applies independently to
  array elements and map values: `tags` and `labels` have non-null collection defaults,
  but `tags.containsNull` and `labels.valueContainsNull` are both `true`.
  `howler.labels.nullable` is also `true`. The [schema tests](../../plugins/sync/test/unit/iceberg/test_build_schema.py)
  check representative public fields. Description text comes from the current models;
  extensions appear in finalization order rather than the old plugin load order.

To reproduce the document comparisons from `api/`, use the same classification policy
as the captures:

```bash
HWL_CONF_FOLDER="$PWD/build_scripts" HWL_CLASSIFICATION_PATH="$PWD/build_scripts/classification.yml" \
  poetry run pytest -q --confcutdir=test/unit/models test/unit/models/test_legacy_parity.py
```

## Retired internal helper

The migration plan proposed retaining `howler.odm.base.construct_safe()`. That helper
was retired with the ODM. It recursively separated unrecognized or invalid values from
usable input and returned `(model_or_none, dropped_data)`. No API endpoint called it.
Full writes validate the document. Permissive Hit ingest can omit unknown fields and
report warnings, but still validates known values. Projected datastore reads validate
the selected fields without requiring their missing siblings. Neither operation exposes
the old helper's return contract.

## What the upgrade rehearsal established

The [Step 9 evidence recorded on 2026-11-12](https://github.com/CybercentreCanada/howler/blob/09f9044e4e69fa9480f1598b79f46fdc1e3b13e0/docs/migration/step9-verification-evidence.md)
reports a successful synthetic Elasticsearch 8.19.11 → 9.5.2 same-volume upgrade,
authenticated reads, write probes, and rollback to a fresh 8.19.11 restore. Its corpus
covered 11 collections. The full inventory, `application-v2.json`, and Step 9 runners
were archived; those checks are not a recurring CI gate. The offline comparisons above
check generated data contracts.
