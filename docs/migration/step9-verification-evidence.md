# Step 9 verification evidence

This is a record of the Step 9 verification, **not approval for the cutover**. The remaining production gates belong to Step 10.

- Branch: `elasticsearch-dsl`, rebased onto `origin/main` `2da444e4`. Pinned base for this wrap-up: `a920c751`.
- Target stack: Elasticsearch/Kibana 9.5.2 and `elasticsearch-py` 9.5.0.
- Date: 2026-11-12. Unless stated otherwise, checks ran on Python 3.12.

## Legacy ODM removal and frozen contracts

| Check | Result |
| --- | --- |
| Runtime imports of `howler.odm`, `elasticsearch_dsl`, `elasticsearch._sync.*` | None. Remaining mentions are only in docstrings, comments, and import-boundary tests. |
| Frozen ODM contract inventory (`api/test/unit/odm/fixtures/odm_contract_inventory.json`) | Regenerated from upstream legacy models in `a920c751`. SHA-256 `60636d74…f44c` is pinned in `test_contract_golden.py`. |
| Model/field goldens without Elasticsearch (`test/unit/models`) | 669 passed on each of Python 3.10, 3.11, and 3.13. |
| Application fixture | `application-v2.json` (canonical SHA-256 `29617daf…aae1`). Its schemas come from the current inventory. Its stored documents were captured through `origin/main`'s legacy `ESCollection.save()`. The capture scripts are stored byte-for-byte in `api/test/fixtures/step9_application/provenance/`. `application-v1.json` is kept as a historical artifact. |
| `__index` | Real persisted legacy behavior. Legacy Hit and Case model saves stored `__index` (`hit`/`case`); User saves did not. v2 records the real saved documents. |

## Isolated 8.19.11 → 9.5.2 rehearsal with application reads and writes

The full mapping corpus was seeded on 8.19.11 before the snapshot was taken. It was then restored, the same volume was restarted on 9.5.2, and the application checks and write checks below were run. Finally, an independent fresh 8.19.11 rollback restore was performed.

```text
cd api
poetry run python build_scripts/step9_upgrade_writes.py --api-root "$PWD" \
  --run-id wrapwrites-v2-confirm-20261112 \
  --work-dir /tmp/opencode/step9-wrap/writes-run-wrapwrites-v2-confirm-20261112 \
  --report /tmp/opencode/step9-wrap/writes-report.json --timeout 900
```

Exit code `0`. `workflow_result: PASS`. Report SHA-256: `87b71e5e7621c8d250b6e765939d4ecdf90dd40f373d51c9d7b620df1b384acb` (3.7 MB, kept locally and not committed).

| Gate | Result | Evidence |
| --- | --- | --- |
| `mapping_parity` | PASS | Exact settings and mappings for all 11 collections, with no normalization. |
| `upgrade` | PASS | The same cluster UUID and index UUIDs before and after the 9.5.2 restart. Aliases, mappings, counts, and source hashes were unchanged. No reindex. |
| `raw_queries` | PASS | ID search, exact lookup, relevance order and scores, and the status aggregation were identical between 8.19 and 9.5. Scores were neither rounded nor reordered. |
| `application` | PASS | Missing key → `401`; wrong key → `403`. Per-user ACL search IDs, counts, and facets matched the fixture. Hit ETag with `If-Match` → `304`. Case GET payload was exact. |
| `no_app_mutation` | PASS | Protected sources, counts, mappings, aliases, and UUIDs were identical before and after the read probes. |
| `write_probe` | PASS | These operations ran through registered collections on the existing 8.19-created `hit_hot` index: full save and read; a stale-version save rejected with `VersionConflictException`; typed SET, APPEND, REMOVE, and mapping SET/DELETE; `CREATE_TOKEN` create; delete; and a bulk field merge that left other fields intact. The original `_source` was restored exactly. One mapping change is explained exactly: deleting a source key does not remove the dynamic keyword mapping that the probe's temporary `labels` key created. |
| `rollback` | PASS | Fresh 8.19.11 volume restore. Health, sources, aliases, mappings, and counts matched the donor. |

The independent review approved this rehearsal and the fixture refresh. Recommended follow-ups:

- Add Case write coverage.
- Add offline tests for the runner orchestration and its child-source compile.

## ES8/ES9 paired search baseline

`api/test/integration/regression/test_step9_es8_es9_baseline.py` with its frozen corpus and results fixture was captured on 2026-10-01. It recorded zero pair, contract, oracle, and frozen differences between 8.19.11 and 9.5.2. The offline contract checks still pass (45 passed, 1 skipped). The live paired rerun needs the deleted 2026-10-01 seed containers and was not repeated. The rehearsal above repeated the raw ES8/ES9 query comparisons on the v2 corpus instead.

## Test suites on the current tree

| Scope | Result |
| --- | --- |
| API full suite (`poetry run test`, Python 3.12, ES 9.5.2) | First run: 2969 passed. 4 deterministic failures in integration tests ported from upstream were then fixed; the fixes were test-only and reviewed. Second run: 2988 passed, 4 skipped, 1 xfailed, and 4 setup errors caused by the dev cluster's 1000-shard limit (leaked `howler-test-*` indices). After cleanup, the 4 errored tests passed when rerun (6 passed in those files). |
| API Mypy, Pyright (CI-equivalent), Ruff | Clean after two small typing fixes in `datastore/collection.py` and `datastore/utils.py`. |
| Python 3.10, 3.11, 3.13 full API suites | Left to CI. Only the model goldens above were run locally. |
| Plugins with checkout manifests, run sequentially | Evidence 2 passed. Sentinel 76 passed. Sync (unit + integration) 29 passed. Ruff and type checks are clean. |
| UI | `tsc`, `oxfmt`, `oxlint` (0 errors), translation and import hooks are clean. The full Vitest suite had 2077 of 2078 passing. The one failure, `src/utils/constants.test.tsx`, also fails without these changes: it depends on the time zone, fails under EST, and passes with `TZ=UTC`. |
| Client SDK and MCP live integration | Left to CI. The last local runs (2026-10-01, before the upstream port) were 56 and 7 passed. |

## Generated surfaces

- **Markdown model docs.** The generator in `api/build_scripts/generate_md_docs.py` now reproduces the legacy layout: type vocabulary, required/optional semantics, row order, and class selection. It adds `alrecord`, `localizedlabel`, and `mitre` pages, which are now in the nav. The 28 remaining metadata differences were approved by the user on 2026-11-12. Most are descriptions that legacy attached to list children and that are now rendered at field level; the rest are straight apostrophes, the `hit.message` label `EmptyableKeyword`, and the ECS reference URL.
- **TypeScript entity types.** `api/build_scripts/generate_classes.py` now derives types from API field metadata and the registered schema instead of random sample documents. Two runs with fresh reseeds in between produced byte-identical output (167 files). Regenerating corrected types that were stale against `origin/main`'s own legacy models:
  - the lightweight `EventHowler`;
  - Case `log`, `visible`, `classification`, and `enrichments[]`;
  - `ECSRule` separated from the Case `Rule`;
  - `UserUser.dashboard[]`;
  - Lead with no ownership fields.

  The user approved landing these on 2026-11-12. Seven UI consumers now narrow hit vs event with `isHit`, and the change has focused tests. No type differences were caused by the migration itself. Follow-ups: commit the six generator regression tests, which still live outside the repository, and simplify the generator's naming and ordering tables.

## Runtime hardening found during verification

`ESCollection` now waits for yellow status after it creates an index, both on the legacy `_hot` path and on an ILM fresh install. Without the wait, `_check_fields` calls `field_caps`, which fails with `illegal_index_shard_state_exception` (RECOVERING) on a loaded cluster and aborted collection startup. `_wait_for_status` now logs Elasticsearch 8+ health timeouts, which arrive as HTTP 200 with `timed_out: true`.

## Gates still open (Step 10 / CI)

1. API Python 3.10, 3.11, and 3.13 full suites, plus client and MCP live integration: CI.
2. A rehearsal with an **approved representative production 8.19 snapshot**, including ILM, system features, deployment settings, and a multi-node rolling order. This environment has only sanitized synthetic fixtures.
3. The production runbook and cutover itself (Step 10).
4. Test-infrastructure follow-ups:
   - Full API runs leak namespaced `howler-test-*` indices, which eventually hit the shard limit.
   - `test_execute_action_no_results` does not actually wait for the queue worker, so it passes without checking anything.
