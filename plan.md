# Howler ODM to `elasticsearch.dsl` and Pydantic Migration Plan

## Problem and proposed approach

Replace Howler's home-grown `api/howler/odm` model, validation, mapping, and serialization system with models built on `elasticsearch.dsl.pydantic.BaseESModel` and Pydantic v2, while preserving Howler's stored-document format, mappings, query behavior, API responses, plugin extensions, and generated UI/documentation contracts.

The implementation can be developed in incremental workstreams, but it will ship as one coordinated Elasticsearch 9 and application cutover. The production runtime will not retain a `howler.odm` compatibility facade or a configuration switch between implementations. During development, the legacy and new implementations will coexist only to run differential tests. Before deleting the legacy runtime, approved differential results will be frozen as durable golden fixtures and schema snapshots.

## Confirmed decisions

- Use a single coordinated Elasticsearch 9/Pydantic application cutover.
- Rewrite runtime consumers and remove `api/howler/odm` at cutover.
- Use the Pydantic integration introduced in `elasticsearch-py` 9.2.0 despite its Technical Preview status, but isolate it behind Howler-owned base classes and adapters.
- Preserve current external and persistence behavior. An ECS schema upgrade, API redesign, search relevance changes, and unrelated datastore refactoring are out of scope.
- Keep direct `elasticsearch-py` client calls for cluster administration features that the DSL does not improve, such as ILM policy management, rollover, shrink/split, reindex task handling, and low-level optimistic concurrency.

## Current state

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

### 1. Establish compatibility baselines

- Inventory all ODM models, fields, imports, plugin hooks, generated artifacts, and datastore call sites.
- Extend existing ODM tests rather than replacing them, especially `test_odm.py`, `test_as_primitives.py`, `test_case.py`, `test_clue.py`, `test_datastore_odm.py`, `test_datastore.py`, `test_access_control.py`, `test_bulk.py`, and Lucene service tests.
- Add schema snapshot generation for model metadata, mappings, index settings/templates, and generated UI/documentation outputs.
- Add representative valid/invalid input fixtures and API response fixtures before changing implementation.

### 2. Make the existing 8.19 deployment upgrade-ready

- Align demo, API development/CI, client, MCP, and Kibana on the latest available 8.19 patch before starting the major upgrade.
- Run the latest 8.19 Kibana Upgrade Assistant, `GET /_migration/deprecations`, deprecation logging/indexing, and system-feature checks against representative and production-like clusters.
- Resolve every critical deprecation and classify warnings. Inventory index creation versions, templates, component templates, ILM policies, ingest pipelines, analyzers, security realms, snapshots, and remote/monitoring relationships.
- Reindex, delete, or explicitly archive any pre-8.0 indices; verify all Howler aliases and ILM rollover indices.
- Add automated checks for unsupported 9.x settings/APIs and record a clean pre-upgrade baseline.

### 3. Pin the target Elasticsearch 9 stack

- Select one exact, current, supported Elasticsearch/Kibana/client 9.x patch at implementation time, with `9.2.0` as the minimum client feature level. Do not pin bare `9.2.0`; if remaining on the 9.2 line, use at least a patch containing the 9.2.4 upgrade fix (9.2.5 or newer).
- Pin matching Elasticsearch and Kibana server versions and a compatible `elasticsearch-py` version at or above 9.2.
- Add Pydantic v2 as an explicit direct dependency; it is not installed by an Elasticsearch extra.
- Update Poetry locks, Docker Compose images, Helm/default deployment values, CI services, client/MCP test stacks, and support documentation together.
- Verify Python, OS/JDK, Docker, third-party Sigma/Lucene dependencies, and exact target-patch known issues before locking the release.

### 4. Build the Pydantic/DSL foundation

- Add `HowlerESModel`, embedded model bases, common configuration, stable `to_doc`/`from_doc` wrappers, serializers, aliases, error translation, and Elasticsearch metadata handling.
- Implement reusable annotated types/validators and explicit DSL mapping annotations for all legacy field categories.
- Implement the canonical model/field metadata registry and flat-field traversal.
- Implement classification serialization/access-field generation and `construct_safe` parity.
- Add focused differential unit tests for each primitive/container field and model-level behavior before migrating domain models.

### 5. Rewrite every model

- Migrate shared enums, primitives, and embedded models first.
- Rewrite the ECS field-set models and `Record`, preserving field names, aliases, mappings, descriptions, and ECS metadata.
- Rewrite Hit, Event, Case, and their embedded data models, including Case cross-field validators and `howler.id` semantics.
- Rewrite remaining top-level models: action, analytic, provider-specific fields, dossier, overview, template, user, view, and supporting models.
- Rewrite plugin/Clue extension registration and validate every finalized top-level `Document`.
- For each group, require differential validation, serialization, mapping, and round-trip tests before proceeding.

### 6. Replace mapping and index registration

- Generate strict mappings, analyzers, normalizers, date formats, dynamic templates, classification fields, field limits, aliases, and composable templates from DSL/model metadata.
- Compare normalized generated mappings with legacy snapshots and a live 8.19 mapping export; investigate every difference rather than accepting DSL defaults.
- Update mapping reconciliation and field introspection to use DSL mappings plus live field capabilities.
- Preserve both existing legacy `_hot` alias and ILM rollover lifecycle paths until stored collections are confirmed migrated; do not rewrite working administration logic solely for DSL style.
- Determine whether any approved mapping change requires a new index/reindex/alias swap. Avoid reindexing 8.x-created indices when mappings remain compatible.

### 7. Migrate persistence, updates, and searches

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
