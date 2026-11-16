# Howler ODM to `elasticsearch.dsl` and Pydantic Migration Plan

## Goal and scope

This migration replaces Howler's in-house `api/howler/odm` model, validation, mapping, and serialization system with Pydantic v2 models built on `elasticsearch.dsl.pydantic.BaseESModel`. It also moves Howler from Elasticsearch 8.19 to 9.x.

The following must stay the same:

- stored document format
- Elasticsearch mappings
- query behavior
- HTTP API responses
- plugin-visible schemas
- generated UI types and documentation

The change ships as one coordinated cutover covering Elasticsearch 9 and the application. Production will have no `howler.odm` compatibility layer and no switch between the old and new implementations.

### Confirmed decisions

- **One cutover:** a single coordinated cutover for Elasticsearch 9 and the Pydantic application.
- **Legacy ODM removed:** `api/howler/odm` is deleted.
  - Internal Python APIs may change freely.
  - HTTP endpoints, stored documents, mappings, query behavior, and generated/public schemas are compatibility contracts.
- **Pydantic integration:** use the `elasticsearch-py` Pydantic integration, which is a Technical Preview. Isolate it behind Howler-owned base classes and adapters.
- **Out of scope:**
  - ECS schema upgrades
  - API redesign
  - search relevance changes
  - unrelated datastore refactoring
- **Direct client calls:** keep direct `elasticsearch-py` calls for cluster administration that the DSL does not improve: ILM, rollover, shrink/split, reindex tasks, and low-level optimistic concurrency.
- **Stale generated types:** the committed TypeScript types were stale compared with `origin/main`'s own legacy models. They may be corrected, with the UI consumers that depend on them updated (approved 2026-11-12).

## Status

|              |                                                                                                       |
| ------------ | ----------------------------------------------------------------------------------------------------- |
| Branch       | `elasticsearch-dsl`, rebased onto `origin/main` `2da444e4`, all commits signed                        |
| Target stack | Elasticsearch/Kibana `9.5.2`, `elasticsearch-py` `9.5.0`, Pydantic v2                                 |
| Done         | Steps 1–9                                                                                             |
| Open         | CI-only verification gates, Step 10 (cutover), and follow-ups. See [Remaining work](#remaining-work). |
| Evidence     | `docs/migration/step9-verification-evidence.md` and `docs/migration/step9-upgrade-rehearsal.md`       |

| Step                                  | Status                  | Commit(s)                          |
| ------------------------------------- | ----------------------- | ---------------------------------- |
| 1. Compatibility baselines            | Complete                | `7d7d14a4`                         |
| 2. Elasticsearch 8.19 readiness       | Complete                | `b9b4487d`                         |
| 3. Pin the Elasticsearch 9 stack      | Complete                | `9de9910f`                         |
| 4. Pydantic/DSL foundation            | Complete                | `fba6c3ed`                         |
| 5. Rewrite every model                | Complete                | `ac38ec6c`                         |
| 6. Mapping and index registration     | Complete                | `e3863a6b`                         |
| 7. Persistence, updates, and searches | Complete                | `9ce5b636`                         |
| 8. Consumers and generated surfaces   | Complete                | `1e2f6bc5`                         |
| 9. Verification and legacy removal    | Complete; CI gates open | `26e2b65b`, `b33cdb0b`, `ebf80c52` |
| 10. Coordinated cutover               | Not started             | —                                  |

## Completed work

### Model layer (`api/howler/models`)

- **Base classes.** `HowlerESModel` and the embedded model bases cover:
  - common configuration
  - stable `to_doc`/`from_doc` wrappers
  - aliases
  - Elasticsearch metadata
  - immutability and equality
  - error translation into Howler's public validation errors
- **Field builders.** Annotated builders and validators cover every legacy field category: dates, IPs, domains, URIs, hashes, enums, classification, JSON, optional/list, compound, mapping, flattened, and case-insensitive keywords.
- **Registry.** A canonical model/field registry provides deterministic flat-field traversal. Datastore update validation, field introspection, and the doc/type generators all use it.
- **Classification.** Classification serialization and the four access fields (`__access_lvl__`, `__access_req__`, `__access_grp1__`, `__access_grp2__`) are generated as before.
- **Lenient construction.** `construct_safe()` keeps its lenient behavior.
- **Model rewrite.** All shared, ECS, provider, embedded, and top-level models are rewritten. This includes the `howler.id` semantics, the Case cross-field rules, and the upstream ODM features ported in `b33cdb0b`:
  - action/dossier/view ownership
  - permission requests
  - migration records
  - shared log/header
  - pivot validation
  - case-insensitive metadata
  - Sentinel fields
- **Typed extension registry (`models/extensions.py`).** This replaces runtime `add_namespace` mutation.
  - Plugins declare extensions before finalization.
  - Ordering is deterministic. Conflicts and illegal names fail explicitly.
  - Legacy-only `modify_odm` extensions fail startup.
  - Clue, Evidence, and Sentinel declare typed Hit extensions. Plugin author documentation is in `docs/api/plugins.md`.

### Mappings and index lifecycle

- **Schema builder.** `models/schema.py` and `schema_defaults.py` generate the following from finalized models:
  - strict mappings
  - analyzers and normalizers
  - date formats and `copy_to`
  - `index`/`store`/`doc_values` flags
  - classification fields and total-field limits
  - ordered dynamic templates
  - ILM composable templates
- **Mapping parity.** All 11 collection contracts match the legacy generator exactly, including Hit with the Clue, Evidence, and Sentinel extensions. **Existing 8.x indices need no reindex.**
- **Reconciliation.**
  - Verifies the existing field type, indexing, analyzer, normalizer, format, `ignore_above`, `copy_to`, `enabled`, and `doc_values`.
  - Adds only safe missing properties, on every backing index.
  - Scopes field-limit increases to the affected collection.
  - Requires active dynamic templates to exist and keep their order.
  - Keeps obsolete plugin templates, with a warning.
- **Field metadata.** `ESCollection.fields()` combines a live mapping read with `field_caps` and registry metadata. It rejects conflicting types across rollover indices.
- **Shard readiness.** Index creation, on both the legacy `_hot` path and an ILM fresh install, now waits for yellow status before the `field_caps` schema check. Without this, startup failed on RECOVERING shards on a loaded cluster.

### Persistence, updates, and search

- **CRUD.** Get, require, multiget, exists, save, and delete use finalized models. This preserves:
  - synthetic stored `id`
  - classification access fields
  - ILM alias-safe reads
  - concrete-index version tokens
  - `CREATE_TOKEN`
  - refresh, retry, and conflict behavior
- **Updates.** `ElasticBulkPlan`, partial updates, field expansion, and update/update-by-query validate through the registry:
  - Full writes require complete models.
  - Partial merges validate only the selected fields.
  - Painless scripts and NDJSON shapes are unchanged.
- **Search.** Collection and cross-index search and faceting use the public `Search`/`Q`/`A` APIs. Fuzzy query construction stays raw. EQL explicitly allows partial search results but not partial sequence results, and rejects incomplete results.
- **Elasticsearch 9 compatibility.**
  - Response and error helpers are updated for the 9.x client.
  - No private `elasticsearch._sync.*` imports remain.
  - Lucene 10 explain normalization uses balanced parsing.

### Consumers, plugins, and generated surfaces

- **Consumers.** Services, API routes, helpers, cron jobs, sample data (`howler.sample_data`), and the Evidence, Sentinel, and Sync plugins use Pydantic models. A static import test and a fresh-process import test enforce that nothing imports the legacy package.
- **Markdown docs.**
  - `generate_md_docs.py` reproduces the legacy layout: type vocabulary, required markers, row order, and class selection.
  - CI runs `--check`.
  - 28 metadata differences were approved. Most are list-item descriptions now rendered at field level, plus apostrophe changes, the `hit.message` label, and the ECS reference URL.
  - Three missing class pages were added to the nav.
- **TypeScript types.**
  - `generate_classes.py` derives types from API field metadata and the registered schema, not from random sample documents. Its output is identical byte for byte across fresh reseeds.
  - The regenerated types fix a stale baseline:
    - lightweight `EventHowler`
    - Case `log`/`visible`/`classification`/`enrichments[]`
    - `ECSRule` separated from Case `Rule`
    - `UserUser.dashboard[]`
    - Lead without ownership fields
  - Seven UI consumers now distinguish hits from events with `isHit`.

### Legacy removal and frozen contracts

- **Legacy code deleted.** `api/howler/odm` and the plugins' legacy `odm/models` are gone. Differential tests were converted to frozen goldens:
  - the ODM contract inventory (`api/test/unit/odm/fixtures/odm_contract_inventory.json`, SHA-256 pinned in `test_contract_golden.py`)
  - primitive, serialization, and validation goldens
  - dynamic-template order
  - legacy Evidence and Sentinel plugin contracts
- **Contract check.** `build_scripts/generate_odm_contract.py --check` only verifies the frozen baseline. It cannot regenerate it.
- **Application fixture.** `api/test/fixtures/step9_application/application-v2.json`:
  - Its schemas come from the current inventory.
  - Its stored documents were captured through `origin/main`'s legacy `ESCollection.save()`. The capture scripts are stored byte for byte under `provenance/`.
  - Legacy Hit and Case saves did persist `__index`.
  - `application-v1.json` is kept for history.

### Verification tooling and results (Step 9)

- **Upgrade rehearsal.** Three runners exercise the upgrade:
  - `build_scripts/upgrade_rehearsal.py` handles the Elasticsearch side: an isolated, Docker-owned 8.19.11 restore, an upgrade of the same volume to 9.5.2, and a rollback.
  - `step9_application_rehearsal.py` adds authenticated HTTP application checks.
  - `step9_upgrade_writes.py` adds writes through registered collections on the existing 8.19-created indices.

  The live run passed every gate:
  - mapping parity
  - upgrade (same cluster/index UUIDs, no reindex)
  - raw 8.19 vs 9.5 queries and scores
  - application auth, ACL, counts, facets, and ETag
  - no unintended mutation
  - writes: save, stale-version refusal, typed updates, bulk, create, delete
  - rollback

- **Search baseline.** The fixed-corpus 8.19 vs 9.5.2 search baseline (`test_step9_es8_es9_baseline.py`) recorded zero differences.
- **Suites on Python 3.12:**
  - API full suite: 2988 passed. Four further errors were caused by the dev cluster's shard limit and passed on rerun.
  - Ruff, mypy, and Pyright are clean.
  - Plugins: Evidence 2, Sentinel 76, Sync 29 passed.
  - UI: `tsc`, `oxlint`, and `oxfmt` are clean. Vitest passed 2077 of 2078; the one failure is a pre-existing timezone issue.
  - Model goldens also pass on Python 3.10, 3.11, and 3.13.

## Remaining work

### A. Verification gates left to CI

- [ ] API full suite on Python 3.10, 3.11, and 3.13 (`api-workflow.yml`).
- [ ] Client SDK live integration (`client-workflow.yml`). Last local run, 2026-10-01: 56 passed.
- [ ] MCP live network tests and the authenticated Chainguard image build (`mcp-workflow.yml`). Last local run: 7 passed.
- [ ] Plugin workflows on their Python matrices.

### B. Step 10: prepare and execute the coordinated cutover

- [ ] **Representative production rehearsal.** Restore an approved representative 8.19 production snapshot on a multi-node 8.19 cluster:
  - Run preflight: Upgrade Assistant, `_migration/deprecations`, system features, ILM, and deployment settings.
  - Perform a rolling upgrade to 9.5.2.
  - Deploy the new application and run the application and write verifiers.
  - Rehearse the snapshot-based rollback.

  The synthetic rehearsals do not cover production data shapes or multi-node ordering.

- [ ] **Runbook.** Write the runbook, covering:
  - preflight commands
  - write quiescing / maintenance mode
  - a fresh verified snapshot immediately before cutover
  - node order and health gates
  - Kibana upgrade, after the cluster is healthy on 9.x
  - application deployment and smoke tests
  - ownership of rollback

  Rollback means rebuilding on 8.19 and restoring the snapshot, **never** an in-place downgrade.

- [ ] **Execute the cutover.**
  - Keep the 8.x application client during the server upgrade; it can use REST compatibility mode.
  - Deploy the 9.x application only after the cluster is healthy.
  - Before reopening writes, verify:
    - aliases and write indices
    - ILM rollover and mappings
    - access control
    - CRUD, search, and bulk/update
    - plugins and background jobs
- [ ] **Release.** Write release notes and changelog entries through Release Please/conventional commits. Remove any temporary fixtures that contain implementation code; keep the golden contracts.

### C. Follow-ups (not blocking the cutover)

- [ ] **Generator tests.** Commit the TypeScript generator regression tests, which currently live outside the repository, under `api/test/unit/`. Simplify the generator's hard-coded naming/order tables, such as `MEMBER_ORDER` and the `EnrichmentsIndicator` clone.
- [ ] **Write-probe coverage.** Add Case write coverage to `step9_upgrade_writes.py`, plus offline tests for its orchestration and child-source compile.
- [ ] **Leaked test indices.** The API test wrapper leaks namespaced `howler-test-*` indices. Repeated full runs reach the 1000-shard limit.
- [ ] **Queue worker wait.** `test_execute_action_no_results` does not wait for the queue worker, so its assertion is vacuous.
- [ ] **Timezone-dependent UI test.** `ui/src/utils/constants.test.tsx` fails outside UTC.
- [ ] **Health-wait robustness.** Consider bounding `ESCollection._wait_for_status`. It retries indefinitely, though it now logs while waiting.
- [ ] **Worktree helper under zsh.** `.agents/skills/howler-worktrees/scripts/worktree-helpers.sh` uses `local path`, which overwrites `PATH` under zsh. Run it with bash, or rename the variable.

### Acceptance criteria

| Criterion                                                                                                                 | Status                                                       |
| ------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| No runtime imports from `howler.odm`, `elasticsearch_dsl`, or `elasticsearch._sync.*`                                     | Met (enforced by tests)                                      |
| Every persisted model is a Pydantic/DSL model finalized through the registry                                              | Met                                                          |
| Approved legacy inputs give identical stored/public primitives and mappings; invalid inputs give equivalent public errors | Met (frozen goldens)                                         |
| Existing 8.x indices are readable and writable after the 9.x upgrade without reindexing                                   | Met in synthetic rehearsal; production rehearsal pending (B) |
| Classification filtering and the four access fields are unchanged                                                         | Met                                                          |
| Plugin extensions are deterministic, conflict-checked, documented, and tested                                             | Met                                                          |
| CRUD, bulk/update, search, aggregation, EQL, ILM, alias, reindex, and concurrency suites pass on 9.5.2                    | Met on Python 3.12; other versions pending CI (A)            |
| Generated TypeScript and docs have no unapproved changes                                                                  | Met (differences approved 2026-11-12)                        |
| CI and deployment manifests pin consistent Elasticsearch/Kibana and Python versions                                       | Met                                                          |
| Production runbook includes a tested snapshot rollback with no node downgrade                                             | Pending (B)                                                  |

## Invariants to preserve

- **Dynamic-template order is part of the mapping contract.** The first matching template wins. Never sort templates in comparisons or treat reordered active templates as equivalent.
- **Total-field limit.** With the Clue, Evidence, and Sentinel extensions, Hit has `1656` flattened fields and a `2156` total-field limit. Always compute the limit after extension finalization.
- **Extension registry reset.** `model_extensions.clear()` at datastore startup is intentional. The registry is a process singleton, and tests and tools create several datastores.
- **Collection models.**
  - Registered collections pass the same finalized class as `model_class` and `schema_model`.
  - Ad-hoc Pydantic collections infer `schema_model`.
  - Legacy models are rejected.
- **Frozen fixtures.** The frozen inventory, goldens, and `application-v2.json` are hash-pinned. Change them only with provenance and review, never by regenerating them silently.
- **`optional()` wrappers** must keep the wrapped field's Howler metadata and DSL mapping.
- **Projections.** Partial projections preserve explicit `None` defaults without invoking default factories.
- **`__index` is persisted** on Hit and Case documents. The UI relies on it to tell hits from events.

## Development and validation notes

- **Run datastore-mutating suites sequentially.**
  - `poetry run test` gives each run a unique `howler-test-<uuid>` prefix, but runs still share cluster capacity.
  - Plugin suites use the shared collections.
  - If the shard limit is reached, delete only leaked `howler-test-<uuid>-*` indices.
- **Plugin manifests.** To test plugin manifests from the checkout rather than installed plugins, set `HWL_PLUGIN_DIRECTORY=/path/to/howler/plugins`. Plugin virtualenvs install `howler-api` from `../../api` as a non-editable copy. Reinstall it after API changes (`pip uninstall howler-api` then `poetry install`).
- **8.19 access.** The 9.x Python client cannot talk to Elasticsearch 8.19. Use raw REST (`urllib`/`curl`) for 8.19 access, as the rehearsal scripts do.
- **Rehearsal isolation.** Rehearsal runners own all of their Docker resources and accept no cluster URLs. Never point them, or ad-hoc tests, at the shared dev stack or at default `howler-*` indices.
- **Evidence plugin tests.** Evidence's `poetry run test` wrapper references a missing `.coveragerc.pytest`. Use `poetry run pytest` directly.
- **Commits must be GPG-signed.** The repository rejects unsigned commits. Rebases must re-sign, for example with `git rebase --force-rebase --gpg-sign <base>`.

## Principal risks

- **Pydantic integration is a Technical Preview.** It is isolated behind `HowlerESModel` and the adapters, dependencies are pinned, and contract tests cover the wrapper.
- **Production data shapes are untested on 9.x.** Only synthetic corpora have been rehearsed. The representative snapshot rehearsal (B) is the remaining mitigation.
- **Rollback cannot downgrade the cluster.** Rollback relies on verified snapshots and a practiced rebuild-and-restore procedure.
- **Technical Preview API drift in future client upgrades.** Pin exact versions, and rerun the golden and mapping parity suites before any client bump.

## References

- Python client: https://www.elastic.co/docs/reference/elasticsearch/clients/python/
- DSL migration: https://www.elastic.co/docs/reference/elasticsearch/clients/python/dsl-migrating
- DSL/Pydantic guide: https://www.elastic.co/docs/reference/elasticsearch/clients/python/elasticsearch-dsl
- Client release notes: https://www.elastic.co/docs/release-notes/elasticsearch/clients/python
- Upgrade path: https://www.elastic.co/docs/deploy-manage/upgrade
- Upgrade preparation and Assistant: https://www.elastic.co/docs/deploy-manage/upgrade/prepare-to-upgrade
- Breaking changes: https://www.elastic.co/docs/release-notes/elasticsearch/breaking-changes
- Known issues: https://www.elastic.co/docs/release-notes/elasticsearch/known-issues
- Snapshot and restore: https://www.elastic.co/docs/deploy-manage/tools/snapshot-and-restore
