# Howler ODM to `elasticsearch.dsl` and Pydantic Migration Plan

## Problem and proposed approach

Replace Howler's home-grown `api/howler/odm` model, validation, mapping, and serialization system with models built on `elasticsearch.dsl.pydantic.BaseESModel` and Pydantic v2, while preserving Howler's stored-document format, mappings, query behavior, API responses, plugin extensions, and generated UI/documentation contracts.

The implementation can be developed in incremental workstreams, but it will ship as one coordinated Elasticsearch 9 and application cutover. The production runtime will not retain a `howler.odm` compatibility facade or a configuration switch between implementations. During development, the legacy and new implementations will coexist only to run differential tests. Before deleting the legacy runtime, approved differential results will be frozen as durable golden fixtures and schema snapshots.

## Confirmed decisions

- Use a single coordinated Elasticsearch 9/Pydantic application cutover.
- Rewrite runtime consumers and remove `api/howler/odm` at cutover.
- Internal Python ODM compatibility is not required. Preserve HTTP endpoint contracts, stored
  documents, Elasticsearch mappings, query behavior, and generated/public schemas, but freely
  rewrite internal model and persistence APIs.
- Use the Pydantic integration introduced in `elasticsearch-py` 9.2.0 despite its Technical Preview status, but isolate it behind Howler-owned base classes and adapters.
- Preserve current external and persistence behavior. An ECS schema upgrade, API redesign, search relevance changes, and unrelated datastore refactoring are out of scope.
- Keep direct `elasticsearch-py` client calls for cluster administration features that the DSL does not improve, such as ILM policy management, rollover, shrink/split, reindex task handling, and low-level optimistic concurrency.

## Implementation status and handoff

**Branch:** `elasticsearch-dsl`

**Completed:** Steps 1–7

**Next:** Step 8, rewriting remaining application consumers

**Working tree at this handoff:** Step 7 is implemented but uncommitted. The prior Step 6 handoff
update was preserved and extended with the Step 7 result and validation notes.

| Step | Status | Commit | Result |
| ---- | ------ | ------ | ------ |
| 1. Compatibility baselines | Complete | `62fa1c1f` | Added deterministic ODM contract inventories and compatibility fixtures. |
| 2. Elasticsearch 8.19 readiness | Complete | `8a9bcaf4` | Aligned and checked the pre-upgrade 8.19 baseline. |
| 3. Elasticsearch 9 stack | Complete | `3f32fe6c` | Pinned Elasticsearch/Kibana 9.5.2 and `elasticsearch-py` 9.5.0 across the repository. |
| 4. Pydantic/DSL foundation | Complete | `ae78105c` | Added Howler model bases, annotated fields, registry, serializers, safe construction, and differential tests. |
| 5. Rewrite every model | Complete | `67f46f5d` | Rewrote the domain/ECS/provider/plugin model surface with Pydantic and Elasticsearch DSL metadata. |
| 6. Mapping and index registration | Complete | `a293c452` | Switched index schemas, templates, introspection, and reconciliation to finalized Pydantic models. |
| 7. Persistence, updates, and searches | Complete | Uncommitted | Switched registered collection CRUD, bulk/update validation, projections, searches, EQL, and Lucene normalization to finalized models and Elasticsearch 9 response semantics. |

### Work completed in Steps 1–3

- Added a machine-readable inventory of legacy fields, models, mappings, settings, extension
  hooks, serialization surfaces, and datastore call sites. The frozen inventory is
  `api/test/unit/odm/fixtures/odm_contract_inventory.json`.
- Added generation/check tooling in `api/build_scripts/generate_odm_contract.py` and kept the
  legacy contract collector in `api/howler/odm/contract.py`.
- Prepared the 8.19 upgrade baseline, then pinned the target stack to Elasticsearch/Kibana
  `9.5.2` and the Python client `9.5.0`. Pydantic v2 and the integrated
  `elasticsearch.dsl` implementation are now the selected model foundation.

### Work completed in Step 4

- Added `api/howler/models` with:
  - `HowlerESModel`, embedded model bases, adapters, stable `to_doc`/`from_doc` conversion,
    aliases, Elasticsearch metadata, immutability, equality, and error translation.
  - Annotated field builders and validators for all legacy scalar/container categories,
    including dates, IPs, domains, URIs, hashes, enums, classification, JSON, optional/list,
    compound, mapping, and flattened fields.
  - A canonical model/field registry with deterministic flat-field traversal and mapping
    metadata.
  - Classification serialization and generation of `__access_lvl__`, `__access_req__`,
    `__access_grp1__`, and `__access_grp2__`.
  - A Pydantic implementation of lenient `construct_safe()` behavior.
- Added differential tests against legacy validation, coercion, serialization, mappings,
  metadata, round trips, and rejected-field paths.

### Work completed in Step 5

- Rewrote all shared, ECS, provider, embedded, and top-level document models under
  `api/howler/models`.
- Preserved stored aliases, defaults, validators, descriptions, ECS metadata, mapping options,
  `howler.id`, Case cross-field rules, classification behavior, and round-trip output.
- Added a typed startup extension registry in `api/howler/models/extensions.py`.
  - Plugins declare fields before finalization instead of mutating Pydantic classes after
    definition.
  - Extension ordering is deterministic, conflicts and illegal names fail explicitly, and
    registry state is isolated between datastore instances.
  - Clue, Evidence, and Sentinel expose typed Hit extensions.
- Legacy plugin `modify_odm` hooks remain active because persistence still uses legacy ODM
  objects until Step 7.
- The model registry deliberately preserves auto-derived model IDs when creating extension
  subclasses; this matters for models such as `User`, whose resolved `user_id` is not a declared
  field.

### Work completed in Step 6

- Added `api/howler/models/schema.py`, the canonical Pydantic/DSL index-contract builder, and
  `api/howler/models/schema_defaults.py`, the neutral home for shared analyzers, normalizers, and
  default templates. `api/howler/datastore/support/schemas.py` is now only a legacy re-export
  path.
- Collection registration now retains a deliberate dual-model boundary:
  - `model_class`: legacy ODM model used for persistence, deserialization, searches, and updates.
  - `schema_model`: finalized Pydantic model used for index settings, mappings, templates,
    field metadata, and reconciliation.
- `HowlerDatastore` registers both models from one `INDEX_MODELS` table, applies legacy plugin
  mutation for runtime compatibility, declares typed Pydantic extensions, finalizes each schema,
  validates its complete mapping, and registers it with `ESStore`.
- Generated contracts include:
  - Explicit flattened properties and synthetic `id`/`__text__` fields.
  - Classification access fields.
  - Exact analyzers, normalizers, keyword limits, date formats, `copy_to`, index/store/doc-values
    behavior, shard/replica settings, and total-field limits.
  - Deterministic dynamic templates in canonical field-registry order.
  - ILM composable templates and lifecycle settings.
- `ESCollection.fields()` now uses live mapping GET plus `field_caps`, with the Pydantic registry
  supplying descriptions, list/storage status, regexes, enum values, and deprecation metadata.
  It rejects conflicting field types/mappings across rollover indices.
- Reconciliation now:
  - Verifies existing field type, indexing, analyzer, normalizer, date format, `ignore_above`,
    `copy_to`, `enabled`, and doc-values behavior.
  - Adds only safe missing explicit properties to every physical backing index.
  - Scopes total-field-limit increases to the affected collection instead of the whole cluster.
  - Requires every active dynamic template to exist, match, and retain precedence order on every
    rollover index.
  - Retains obsolete templates from disabled/removed plugins with a warning because removing
    them is unnecessary and would otherwise prevent startup.
  - Validates mappings before updating the ILM composable template, avoiding partially-applied
    migrations on refusal.
- The production ILM path now uploads the same `schema.ilm_template_body()` payload covered by
  contract tests. Existing `_hot` migration, alias, rollover, clone, recovery, and administration
  behavior remains intact.

### Step 6 compatibility conclusion

- All 11 collection contracts created from the frozen legacy generator and the new schema
  generator produced identical canonical mappings and relevant settings on a disposable
  Elasticsearch `8.19.11` node.
- Mapping/settings/template parity was also verified for the finalized Hit schema with Clue,
  Evidence, and Sentinel extensions.
- Existing 8.x-created Howler indices therefore do **not** require a reindex or alias swap for
  this migration. Reindex only if a later, explicitly approved mapping change introduces an
  incompatible contract.
- Final validation included:
  - `1308` API unit tests.
  - Live schema reconciliation and ILM integration tests.
  - Evidence (`1`), Sentinel (`10`), and Sync (`28`) plugin tests, run sequentially.
  - Ruff formatting/linting, Mypy, CI-equivalent Pyright, contract freshness, and diff checks.
  - Two independent review passes; all reported correctness and structural findings were fixed.

### Work completed in Step 7

- Registered Howler collections now use finalized Pydantic/DSL models for persistence and
  deserialization while the exported legacy `INDEXES` table remains available for differential
  tooling and Step 8 consumers.
- Converted CRUD and normalization paths:
  - Full writes validate complete models; stored reads ignore removed/plugin fields while still
    rejecting invalid declared values.
  - Synthetic stored `id`, classification access fields, aliases, raw schema-less values, and
    Elasticsearch metadata are normalized without dropping legitimate nested `id` fields.
  - Search projections create validated partial models, preserve legacy `None` defaults without
    invoking unrelated/default-factory values, and retain the existing dictionary projection
    shapes.
  - ILM alias-safe reads, concrete-index version tokens, `CREATE_TOKEN`, refresh options, retries,
    and conflict behavior are preserved.
- Converted `ElasticBulkPlan`, field expansion/pruning, update validation, operation helpers, and
  update/update-by-query inputs to registry/Pydantic validation:
  - Full index/create/upsert operations require complete models.
  - Partial merges validate only selected fields, including compound/list/mapping values supplied
    by remaining legacy callers.
  - NDJSON action/body shapes, Painless scripts, stored date/IP/classification/model primitives,
    access helpers, and per-batch retry behavior remain stable.
- Consolidated exact-parity search request components on public `elasticsearch.dsl` `Search`,
  `Q`, and `A` APIs for collection and cross-index search/faceting. Fuzzy query generation remains
  behavior-sensitive raw construction, with only response/error normalization changed.
- Kept EQL on public `client.eql.search`, explicitly setting
  `allow_partial_search_results=True` and `allow_partial_sequence_results=False`; Elasticsearch 9
  response wrappers and total-hit forms are normalized, and incomplete/running EQL results are
  rejected instead of being presented as complete.
- Added shared Elasticsearch 9 response/error helpers and removed application imports from private
  Elasticsearch client namespaces in this scope. Task polling now retries structured timeout error
  types correctly.
- Reworked Lucene explain normalization for Lucene 10 wrappers using balanced parsing while
  preserving phrase, wildcard, exists, range, boolean, and endpoint response behavior.
- Added narrow Step 7 compatibility edits for remaining legacy consumers that immediately receive
  new datastore models (field introspection, model item assignment/membership, case/record saves,
  API response coercion, comments, and related indicators). The broad consumer rewrite remains
  Step 8.
- Post-review hardening now validates every model-backed Painless path (including typed mapping
  children and mapping-key DELETE operations), fully revalidates Pydantic instances before full
  save/create/index/upsert writes, coerces embedded Case values to the parent model family, resolves
  ILM multiget/delete IDs to concrete rollover indices, rejects timed-out/failed-shard EQL results,
  propagates Lucene validation transport failures, and fails startup for legacy-only plugin model
  extensions that would otherwise be dropped. Typed extensions also reject the synthetic top-level
  `id` field so it cannot be silently stripped or conflict with Elasticsearch metadata.
- The Step 1 ODM contract inventory remains byte-for-byte frozen. Its check verifies the frozen
  baseline hash, while live inventory generation requires an explicit alternate output path.

### Step 7 validation and handoff

- Post-review focused regressions: `291` passed, covering collection persistence/update/EQL/ILM,
  bulk full-vs-partial writes, Case service compatibility, Lucene validation, ILM configuration,
  and the frozen ODM contract.
- Focused Step 7 unit suites: `328` passed.
- Full API unit collection: `1201` passed, `12` skipped, and `133` failed only during shared
  datastore setup because the local node is Elasticsearch `8.19.11` while the repository client is
  `9.5.0`; no distinct code assertion failure was observed. Contract/schema suites passed
  separately (`47` passed).
- Search service integration: `38` passed, `24` skipped. Lucene live integration was unavailable
  (`3` skipped). Datastore suites requiring the incompatible local node were skipped; ETag tests
  passed (`17` passed, `2` skipped).
- Plugin tests were run sequentially with the checkout plugin directory:
  - Evidence: `1` passed.
  - Sentinel: `10` skipped because the external Defender/Sentinel connection was unavailable.
  - Sync: `16` passed, `12` skipped because the external Howler service was unavailable.
- Ruff format/lint, full Mypy, changed-file Pyright, frozen ODM contract, and diff checks passed.
  Multiple read-only correctness reviews were run; all high-confidence Step 7 findings were fixed.
- Step 8 should remove the temporary legacy consumer typing/imports and localized compatibility
  branches, migrate constructors/helpers/services to `howler.models`, and leave the frozen legacy
  contract/reference implementation intact until Step 9.

### Important implementation details to preserve

- `api/howler/odm/contract.py` intentionally forces `schema_model=None` while collecting the
  frozen legacy contract. Do not switch that collector to the new generator before the legacy
  implementation is deleted and the fixtures become permanent goldens.
- Keep `api/howler/datastore/support/build.py` and the legacy ODM models available as differential
  references until Step 9. They are no longer authoritative for registered index schemas.
- Dynamic-template order is part of the mapping contract because Elasticsearch applies the first
  matching template. Do not sort templates in comparisons or treat reordered active templates as
  equivalent.
- When plugins add Evidence + Sentinel + Clue to Hit, the finalized schema has `1656` flattened
  fields and receives a `2156` total-field limit. Always calculate the limit after extension
  finalization.
- `model_extensions.clear()` at datastore startup is intentional. The extension registry is a
  process singleton, while tests and some tools construct more than one datastore.
- Registered collections pass the same finalized class as `model_class` and `schema_model`.
  Legacy model registration remains only for deliberate differential/ad hoc compatibility paths
  until the Step 8/9 cleanup.

### Validation and environment pitfalls

- API and plugin datastore suites share the same development Elasticsearch collections and wipe
  or recreate them. **Never run datastore-mutating API/plugin suites concurrently.** Concurrent
  runs caused field-limit, missing-shard, count, and pagination failures that disappeared when
  rerun sequentially.
- Plugin tests can silently import installed plugins from `/etc/howler/plugins` because
  `howler.app` prepends `HWL_PLUGIN_DIRECTORY`. To test checkout manifests and typed extension
  hooks, set:

  ```bash
  HWL_PLUGIN_DIRECTORY=/path/to/howler/plugins
  ```

- The 9.5 Python client sends REST compatibility headers that Elasticsearch 8.19 rejects.
  Live 8.19 mapping comparisons must use raw JSON REST calls (`curl`/`urllib`) or an 8.x client,
  not the repository's 9.x virtual environment.
- Evidence's `poetry run test` wrapper currently references a missing `.coveragerc.pytest` and can
  abort before test collection. Use the workflow's direct Pytest command or targeted
  `poetry run pytest` unless that unrelated wrapper is repaired.
- For API subsets, run direct Pytest from `api/`:

  ```bash
  poetry run pytest -q <paths>
  ```

  The full API wrapper is:

  ```bash
  poetry run test test/unit
  ```

### Workflow for the next agent

- Continue one numbered plan step at a time and keep a commit boundary between steps.
- Do not run `git commit` automatically. Commit signing prompts for a password, so stage the
  completed step and ask the user to run the proposed commit command.
- Start Step 8 from the finalized collection runtime. Do not revert registered persistence to the
  legacy models.
- Rewrite remaining application imports, constructors, annotations, helpers, plugin action
  consumers, and service assumptions from `howler.odm.models` to `howler.models`.
- Remove localized Step 7 compatibility branches only as their consumers are migrated and covered.
- Preserve HTTP endpoints, stored primitives, mappings, queries, response shapes, and concurrency
  behavior; keep legacy contract/reference code and fixtures until Step 9.

## Original state before implementation

### Versions

- Python client: `elasticsearch==8.19.3` in `api/pyproject.toml` and `api/poetry.lock`.
- Transport: `elastic-transport==8.17.1`.
- Elasticsearch server:
  - `8.19.11` in API development/CI, client tests, and MCP Docker Compose.
  - `8.19.9` in demo Docker Compose.
- Kibana development image: `8.3.3`, which is already out of lockstep with Elasticsearch.
- API CI covers Python 3.10 through 3.13; `elasticsearch-py>=9.2` requires Python 3.10 or newer.
- ECS model metadata remains based on ECS 8.3/8.5. That schema version is independent of the Elasticsearch server version and will not be changed by this migration.

### ODM and datastore surface

- `api/howler/odm/base.py` implements roughly 40 field types, validation, defaults, model decoration, flat/nested conversion, dynamic namespaces, strict and lenient construction, serialization, field metadata, immutability, equality, and documentation generation.
- `api/howler/odm/models` contains approximately 136 decorated model registrations across top-level Howler models and ECS field sets.
- `api/howler/datastore/support/build.py` and `api/howler/datastore/constants.py` compile ODM fields into mappings, analyzers, normalizers, dynamic templates, and reverse field metadata.
- `api/howler/datastore/collection.py` combines CRUD, bulk/update semantics, search/aggregation construction, mapping reconciliation, index creation, ILM, aliases, retries, and maintenance operations.
- Independent raw query builders exist in `ESCollection._search`, `search_service`, `fuzzy_service`, EQL handling, and Lucene query validation.
- Plugin hooks mutate models at startup with `add_namespace`; Clue fields are also attached dynamically.
- Model metadata feeds generated TypeScript declarations and published ODM documentation through `ESCollection.fields()`, `generate_classes.py`, and `generate_md_docs.py`.

### Highest-risk compatibility contracts

- Classification values and generated `__access_lvl__`, `__access_req__`, `__access_grp1__`, and `__access_grp2__` fields.
- Flattened input reconstruction, lists of compound values, mappings, optional fields, masks, unknown-field rejection, and `construct_safe` dropped-field behavior.
- IP and timestamp serialization modes, enum values, custom hash/domain/URI validators, defaults, aliases, and model-level Case validation.
- `id_field`, `howler.id`, Elasticsearch metadata, ILM-aware version tokens, and optimistic concurrency.
- Dynamic plugin namespaces, startup model finalization, and model registry cache isolation.
- Exact mapping characteristics: strict dynamic behavior, analyzers, normalizers, `copy_to`, date formats, keyword limits, dynamic templates, field counts, and classification helper fields.
- Painless update operations and field-scoped bulk merges.
- Search payloads and response normalization for sort, collapse/grouping, facets, histograms, statistics, arbitrary aggregations, EQL, and partial results.
- Lucene 10 explain output, which can break the existing regex-based query normalization during the Elasticsearch 9 upgrade.

## Target architecture

### Howler model layer

Create a new `api/howler/models` package with these responsibilities:

1. `HowlerESModel`, derived from `elasticsearch.dsl.pydantic.BaseESModel`, owns common Pydantic configuration, immutability, aliases, primitive serialization, Elasticsearch metadata conversion, and stable wrappers around the Technical Preview API.
2. Pydantic `BaseModel` subclasses represent embedded object/nested structures. `typing.Annotated` attaches explicit `elasticsearch.dsl` field definitions where inferred mappings are insufficient.
3. Reusable Howler annotated types and validators replace ODM field subclasses for classification, dates, IPs, domains, URIs, hashes, enums, case-normalized keywords, bounded numbers, JSON, mappings, and flattened structures.
4. A Howler model/field metadata registry replaces `@odm.model`, `fields()`, and `flat_fields()`. It exposes one canonical view for datastore update validation, mapping inspection, generated UI types, documentation, and plugins.
5. Model-level Pydantic validators replace custom `__init__` validation in Case-related models. Pydantic serializers preserve `as_primitives()` behavior, including timestamp/IP options and hidden classification fields.
6. A lenient validation service reproduces `construct_safe()` by validating fields independently, recording rejected paths, and constructing a valid partial model only where the legacy behavior permits it.

### Plugin and dynamic model composition

Pydantic models cannot safely support the current post-definition descriptor mutation. Replace `add_namespace`/`remove_namespace` with a startup model-extension registry:

1. Plugins declare typed extension models and their target namespace before datastore registration.
2. The registry detects conflicts and invalid field names, then uses Pydantic's supported model-construction facilities to finalize one derived model per target.
3. Elasticsearch DSL mappings are generated only after all extensions, including Clue, are applied.
4. Tests prove multiple plugin extensions, enable/disable behavior, registry cache isolation, and unchanged serialized/mapping output.
5. Publish the new extension API and migrate in-repository plugins in the same release; fail startup with actionable errors for plugins still using the removed mutation API.

### Datastore and query layer

- Replace ODM-specific model construction and mapping compilation in `ESCollection` with the model registry, generated `Document` classes, DSL mappings, and Pydantic conversion.
- Preserve the service-facing collection operations where they encode Howler behavior, but update all model types/imports and remove ODM-specific branches.
- Consolidate search construction around `elasticsearch.dsl.Search`, `Q`, typed query/aggregation objects, and public `client.indices` APIs. Keep direct client calls for EQL and cluster APIs when no DSL equivalent exists.
- Keep Howler's update operation vocabulary and wildcard merge behavior. Translate it through a single typed operation compiler to `Document.update`, `UpdateByQuery`, or core bulk helpers while preserving Painless scripts and concurrency tokens.
- Replace hand-built bulk NDJSON with `elasticsearch.helpers.streaming_bulk`/`bulk` or DSL `Document.bulk` where parity tests show identical retry, error, refresh, and partial-update behavior.
- Remove imports from `elasticsearch._sync.*`; use documented public client namespaces.
- Separate index lifecycle/administration code from document persistence enough that model migration tests can run without exercising cluster maintenance.

## Compatibility strategy

### Contract inventory

Before rewriting models, create a machine-readable contract inventory covering:

- Every legacy field class and each constructor option.
- Every decorated model, field path, default, optional/list/mapping status, ID field, description, and Elasticsearch mapping.
- All top-level collection registrations and ILM settings.
- Every public serialization mode and datastore operation used by services, routes, cron jobs, plugins, and tests.
- Generated TypeScript and Markdown outputs.

Classify compatibility as:

- **Exact:** stored JSON, public API JSON, field names/aliases, mapping semantics, query filters, update effects, access-control fields, ID/version tokens, plugin-visible schemas, and generated TypeScript types.
- **Semantically equivalent:** internal exception classes/messages, object representation, and query JSON ordering, provided API error envelopes and behavior remain unchanged.
- **Intentionally changed:** only changes documented and approved during implementation, with dedicated migration handling.

### Differential harness

While both implementations exist on the migration branch:

1. Parameterize the current ODM unit corpus so identical inputs run through legacy models and new Pydantic/DSL models.
2. Compare accepted/rejected values, normalized values, defaults, dropped paths, primitive output, round trips, equality, immutability, IDs, and public validation errors.
3. Generate deterministic representative documents for every model, plus boundary/invalid cases for every field type.
4. Normalize non-semantic ordering and compare complete mapping/settings/template output for all top-level collections.
5. Compare raw Elasticsearch requests and normalized responses for CRUD, search, aggregation, EQL, bulk, and update operations.
6. Record explicitly approved results as versioned JSON fixtures and mapping snapshots.
7. After deleting `api/howler/odm`, run the new implementation against those fixtures so compatibility remains enforced without shipping legacy code.

## Implementation todos

### 1. Establish compatibility baselines — complete (`62fa1c1f`)

- Inventory all ODM models, fields, imports, plugin hooks, generated artifacts, and datastore call sites.
- Extend existing ODM tests rather than replacing them, especially `test_odm.py`, `test_as_primitives.py`, `test_case.py`, `test_clue.py`, `test_datastore_odm.py`, `test_datastore.py`, `test_access_control.py`, `test_bulk.py`, and Lucene service tests.
- Add schema snapshot generation for model metadata, mappings, index settings/templates, and generated UI/documentation outputs.
- Add representative valid/invalid input fixtures and API response fixtures before changing implementation.

### 2. Make the existing 8.19 deployment upgrade-ready — complete (`8a9bcaf4`)

- Align demo, API development/CI, client, MCP, and Kibana on the latest available 8.19 patch before starting the major upgrade.
- Run the latest 8.19 Kibana Upgrade Assistant, `GET /_migration/deprecations`, deprecation logging/indexing, and system-feature checks against representative and production-like clusters.
- Resolve every critical deprecation and classify warnings. Inventory index creation versions, templates, component templates, ILM policies, ingest pipelines, analyzers, security realms, snapshots, and remote/monitoring relationships.
- Reindex, delete, or explicitly archive any pre-8.0 indices; verify all Howler aliases and ILM rollover indices.
- Add automated checks for unsupported 9.x settings/APIs and record a clean pre-upgrade baseline.

### 3. Pin the target Elasticsearch 9 stack — complete (`3f32fe6c`)

- Select one exact, current, supported Elasticsearch/Kibana/client 9.x patch at implementation time, with `9.2.0` as the minimum client feature level. Do not pin bare `9.2.0`; if remaining on the 9.2 line, use at least a patch containing the 9.2.4 upgrade fix (9.2.5 or newer).
- Pin matching Elasticsearch and Kibana server versions and a compatible `elasticsearch-py` version at or above 9.2.
- Add Pydantic v2 as an explicit direct dependency; it is not installed by an Elasticsearch extra.
- Update Poetry locks, Docker Compose images, Helm/default deployment values, CI services, client/MCP test stacks, and support documentation together.
- Verify Python, OS/JDK, Docker, third-party Sigma/Lucene dependencies, and exact target-patch known issues before locking the release.

### 4. Build the Pydantic/DSL foundation — complete (`ae78105c`)

- Add `HowlerESModel`, embedded model bases, common configuration, stable `to_doc`/`from_doc` wrappers, serializers, aliases, error translation, and Elasticsearch metadata handling.
- Implement reusable annotated types/validators and explicit DSL mapping annotations for all legacy field categories.
- Implement the canonical model/field metadata registry and flat-field traversal.
- Implement classification serialization/access-field generation and `construct_safe` parity.
- Add focused differential unit tests for each primitive/container field and model-level behavior before migrating domain models.

### 5. Rewrite every model — complete (`67f46f5d`)

- Migrate shared enums, primitives, and embedded models first.
- Rewrite the ECS field-set models and `Record`, preserving field names, aliases, mappings, descriptions, and ECS metadata.
- Rewrite Hit, Event, Case, and their embedded data models, including Case cross-field validators and `howler.id` semantics.
- Rewrite remaining top-level models: action, analytic, provider-specific fields, dossier, overview, template, user, view, and supporting models.
- Rewrite plugin/Clue extension registration and validate every finalized top-level `Document`.
- For each group, require differential validation, serialization, mapping, and round-trip tests before proceeding.

### 6. Replace mapping and index registration — complete (`a293c452`)

- Generate strict mappings, analyzers, normalizers, date formats, dynamic templates, classification fields, field limits, aliases, and composable templates from DSL/model metadata.
- Compare normalized generated mappings with legacy snapshots and a live 8.19 mapping export; investigate every difference rather than accepting DSL defaults.
- Update mapping reconciliation and field introspection to use DSL mappings plus live field capabilities.
- Preserve both existing legacy `_hot` alias and ILM rollover lifecycle paths until stored collections are confirmed migrated; do not rewrite working administration logic solely for DSL style.
- Determine whether any approved mapping change requires a new index/reindex/alias swap. Avoid reindexing 8.x-created indices when mappings remain compatible.

### 7. Migrate persistence, updates, and searches — next

- Convert get/require/multiget/exists/save/delete and object deserialization to Pydantic/DSL documents.
- Convert bulk indexing and field-scoped partial updates, preserving refresh, retry, conflict, error, and optimistic-concurrency behavior.
- Consolidate collection, cross-index, and fuzzy searches with DSL query/search/aggregation builders while preserving emitted query semantics and response shapes.
- Revalidate EQL with explicit partial-result handling because Elasticsearch 9 changes its default.
- Replace private client imports and update retry/error handling for the 9.x exception/response model.
- Rework Lucene explain parsing against Lucene 10 output, or replace string parsing with a stable public representation if available; retain regression cases for all supported query shapes.

### 8. Rewrite consumers and generated surfaces

- Replace all `howler.odm` imports and ODM type assumptions across services, APIs, helpers, cron jobs, tests, and plugins.
- Update datastore operation validation and field metadata consumers to use the new registry.
- Update TypeScript and Markdown generators, regenerate outputs, and fail CI on uncommitted schema-generation differences.
- Update plugin author documentation and release notes for the mandatory extension API migration.
- Remove duplicate/dead ODM-specific schema and mapping modules only after import and generated-output checks prove they are unused.

### 9. Complete unit and integration verification

- Convert differential results into permanent golden fixtures, remove legacy test execution, then delete `api/howler/odm`.
- Run all model/field compatibility tests without Elasticsearch.
- Run datastore, ILM, access-control, search, EQL, Lucene, bulk, reindex, and API contract tests against the exact Elasticsearch 9 target.
- Add an upgrade rehearsal that restores a representative 8.19 snapshot into an 8.19 cluster, runs preflight checks, upgrades it to the target 9.x version, deploys the new application, and verifies existing documents without reindexing.
- Exercise plugin workflows, client integration, MCP integration, generated UI types, and all supported Python versions.
- Compare search result sets and aggregations on a fixed corpus; any relevance/order difference requires explicit approval.

### 10. Prepare and execute the coordinated cutover

- Publish a runbook with preflight commands, write-quiescing/maintenance behavior, snapshots, node order, health gates, Kibana steps, application deployment, smoke tests, and rollback ownership.
- Take a fresh verified snapshot immediately before cutover. Elasticsearch has no in-place downgrade path.
- Upgrade Elasticsearch from the latest 8.19 patch to the selected 9.x patch, using the required rolling node order where applicable; keep the existing 8.x application client during the server upgrade because it can use REST compatibility mode.
- After the cluster is fully healthy on 9.x, stop and upgrade Kibana to the exact same version, then deploy the new Howler application with the 9.x client and Pydantic/DSL models.
- Verify aliases/write indices, ILM rollover, mappings, access control, CRUD, search, bulk/update operations, generated configuration, plugins, and background jobs before reopening writes.
- If server rollback is required, rebuild 8.19 and restore the pre-upgrade snapshot; never attempt an in-place binary downgrade.
- Remove temporary compatibility fixtures that contain implementation code, retain golden contracts, and add the required release/changelog documentation.

## Unit test matrix

| Area                | Required comparisons                                                                                                       |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| Primitive fields    | Accepted/rejected types, coercion, bounds, regex, case normalization, enum values, UUID, dates, IPs, domains, URIs, hashes |
| Containers          | Compound/object, nested/list, typed mapping, flattened reconstruction, optional/null, defaults/default factories           |
| Models              | Unknown fields, masks, aliases, inheritance, registry isolation, immutability, equality, IDs, descriptions                 |
| Serialization       | Primitive JSON, IP/date modes, hidden classification fields, flat/nested round trips, extra/dropped fields                 |
| Validation          | Exact public error paths/envelopes, Case cross-field rules, `construct_safe`, plugin conflicts                             |
| Mappings            | Field types, multifields, analyzers, normalizers, strictness, dynamic templates, `copy_to`, date formats, index settings   |
| Datastore requests  | CRUD metadata, bulk actions, update scripts, concurrency, retry classification, refresh behavior                           |
| Search              | Query/filter/sort, pagination, grouping, facets, histograms, stats, arbitrary aggregations, EQL partial results            |
| Generated contracts | Index field metadata, TypeScript declarations, Markdown tables, plugin-added fields                                        |

## Acceptance criteria

- No runtime imports from `howler.odm`, `elasticsearch_dsl`, or `elasticsearch._sync.*`.
- Every persisted Howler model is represented by a Pydantic/DSL model finalized through the new registry.
- Approved legacy inputs produce identical stored/public primitives and mapping semantics, and invalid inputs produce equivalent public validation failures.
- Existing 8.x-created indices remain readable and writable after the Elasticsearch 9 cutover without reindexing unless a documented mapping change requires it.
- Classification filtering and all four generated access fields are unchanged.
- Plugin model extensions are deterministic, conflict-checked, documented, and covered by tests.
- CRUD, bulk/update, search, aggregation, EQL, ILM, alias, reindex, and optimistic-concurrency suites pass against the exact target 9.x patch.
- Generated TypeScript declarations and documentation have no unapproved changes.
- CI and deployment manifests use consistent, pinned Elasticsearch/Kibana versions and supported Python versions.
- The production runbook includes a tested snapshot-based rollback and does not rely on downgrading Elasticsearch nodes.

## Principal risks and mitigations

- **Pydantic integration is Technical Preview:** isolate `BaseESModel`, `_doc`, `to_doc`, and `from_doc` behind Howler-owned APIs; pin exact dependency versions; cover the wrapper with contract tests.
- **Single-release cutover is large:** develop behind a migration branch with per-model differential gates and require a full snapshot upgrade rehearsal before merge.
- **Dynamic plugin fields do not map directly to static Pydantic models:** finalize derived models once at startup through an explicit extension registry and reject late mutation.
- **DSL defaults can silently alter mappings:** make field mappings explicit and compare normalized full mappings/settings/templates.
- **Validation coercion differs from the ODM:** use strict Pydantic configuration plus explicit before/after validators; test every accepted legacy coercion.
- **Lucene 10 can change explain strings and relevance:** isolate explain normalization, add fixed-corpus result comparisons, and prefer stable public APIs over regex parsing.
- **Elasticsearch 9 behavior changes:** explicitly test EQL partial results, stricter bulk parsing, removed APIs/parameters, analyzers, templates, ILM, and error/status handling.
- **Rollback cannot downgrade the cluster:** require verified snapshots and a practiced rebuild/restore procedure.

## Primary references

- Python client compatibility: https://www.elastic.co/docs/reference/elasticsearch/clients/python/
- DSL migration: https://www.elastic.co/docs/reference/elasticsearch/clients/python/dsl-migrating
- DSL/Pydantic guide: https://www.elastic.co/docs/reference/elasticsearch/clients/python/elasticsearch-dsl
- Python client release notes: https://www.elastic.co/docs/release-notes/elasticsearch/clients/python
- Elasticsearch upgrade path: https://www.elastic.co/docs/deploy-manage/upgrade
- Upgrade preparation and Assistant: https://www.elastic.co/docs/deploy-manage/upgrade/prepare-to-upgrade
- Elasticsearch breaking changes: https://www.elastic.co/docs/release-notes/elasticsearch/breaking-changes
- Elasticsearch known issues: https://www.elastic.co/docs/release-notes/elasticsearch/known-issues
- Snapshot compatibility: https://www.elastic.co/docs/deploy-manage/tools/snapshot-and-restore
