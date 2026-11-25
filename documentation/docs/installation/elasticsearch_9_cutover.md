# Elasticsearch 9.5.2 production cutover runbook

Coordinated procedure to upgrade Howler from Elasticsearch/Kibana `8.19.11` to
`9.5.2` alongside the Pydantic/DSL Howler release. **Do not schedule production
until every hard gate passes.** Follow Elastic's official guides:

- [Prepare to upgrade Elasticsearch](https://www.elastic.co/docs/deploy-manage/upgrade/prepare-to-upgrade)
- [Upgrade Elasticsearch (rolling upgrade)](https://www.elastic.co/docs/deploy-manage/upgrade/deployment-or-cluster/elasticsearch)
- [Snapshot and restore](https://www.elastic.co/docs/deploy-manage/tools/snapshot-and-restore)

## Roles

| Role | Responsibility |
| --- | --- |
| Cutover lead | Owns timeline, go/no-go gates, change record, and reopening writes. |
| Elasticsearch lead | Owns 8.19 preflight, snapshots, rolling node upgrades, and cluster health. |
| Howler application lead | Owns ingress freeze, image consistency, collection init, verifier, smoke checks, and app rollback. |
| Rollback owner | Independent stop authority; owns 8.19.11 rebuild and snapshot restore. |
| Plugin / ops owners | Pause and validate Evidence, Sentinel, Sync, MCP, ingestion, and jobs. |
| Communications lead | Announces maintenance, logs decisions/evidence, communicates status. |

Store reports, change records, and credentials only in approved restricted
locations—never in git or ticket text.

## Hard gate 0 — production-snapshot rehearsal

Before scheduling production, restore an approved **production snapshot onto an
isolated multi-node `8.19.11` cluster** with representative topology/plugins and
complete end-to-end:

1. Verify `8.19.11` health, run the automated preflight, Kibana Upgrade
   Assistant, and Gate 1 checks; resolve every 9.x blocker (defer ES 10 work).
2. Perform the rolling ES upgrade to `9.5.2`, then non-rolling Kibana upgrade.
3. Deploy the candidate 9.x Howler release with jobs disabled, initialize
   collections, run the post-cutover verifier against a quiesced baseline, and
   run auth/ACL, CRUD, ETag, bulk, and plugin smoke checks.
4. Rehearse rollback: stop the 9.x app, build a clean `8.19.11` cluster, mount
   the snapshot repository with `settings.readonly: true`, restore the
   pre-upgrade snapshot, and verify the prior Howler release. **Never downgrade
   nodes in place or let two clusters write to the same repository.**

## Production Job execution

Run preflight, collection initialization, and cutover verification as short-lived
Jobs from the exact immutable 9.x API image (`HOWLER_API_IMAGE`), not from a
workstation:

```bash
kubectl get deployment "$HOWLER_API_DEPLOYMENT" \
  -o jsonpath='{.spec.template.spec.containers[?(@.name=="api")].image}'
```

Use a one-off Job (`backoffLimit: 0`, `restartPolicy: Never`) mirroring the API
deployment's env, Secrets, `/etc/howler/conf`, `/etc/howler/plugins`, and Redis
network access:

```yaml
containers:
  - name: es-check
    image: "<exact-candidate-9.x-API-image-tag-or-digest>"
    command: ["python", "-m", "howler.external.elasticsearch_preflight"]
    args: ["--output", "/reports/es-preflight-8.19.json"]
    env:
      - name: ELASTICSEARCH_URL
        value: "https://elasticsearch.example:9200"
      - name: HWL_DATASTORE_INDEX_PREFIX
        value: "<same-prefix-as-the-API>"
      - name: ELASTIC_API_KEY
        valueFrom: {secretKeyRef: {name: es-check-auth, key: api-key}}
    volumeMounts:
      - {name: howler-conf, mountPath: /etc/howler/conf, readOnly: true}
      - {name: howler-plugins, mountPath: /etc/howler/plugins, readOnly: true}
      - {name: reports, mountPath: /reports}
```

- Auth uses `ELASTIC_API_KEY` or `ELASTIC_USERNAME` + `ELASTIC_PASSWORD` (not
  `<HOST>_HOST_*` or URL user-info).
- For the verifier, run `python -m howler.external.elasticsearch_cutover_verify`
  with `--baseline /reports/es-baseline-8.19.json --output /reports/es-cutover-9.5.2.json`.
- Both verifier and initializer mirror `howler/app.py` plugin loading
  (`HWL_PLUGIN_DIRECTORY`) and fail closed if any configured plugin fails to load.

## Gate 1 — preflight and readiness (on `8.19.11`)

1. Confirm all ES nodes and Kibana are `8.19.11` and target artifacts are `9.5.2`.
2. Resolve critical items in Kibana Upgrade Assistant and deprecation logs.
3. In a prior `8.19` maintenance window, check `howler-migrate --list` in the
   **currently deployed** image and confirm every registered ID (currently
   `action-owner-id-to-owner`, `metadata-case-insensitive-search`) has
   `status: applied` in `<prefix>-migration` (e.g.
   `GET /<prefix>-migration/_doc/metadata-case-insensitive-search`). If unapplied
   and the deployed image has the runner, quiesce writers, run
   `howler-migrate --all`, verify `applied`, and resume service **before** the
   cutover freeze/baseline (migrations reindex collections and change UUIDs).
   Otherwise use the Gate 4 fallback. See [migration guide](../migration.md).
4. Run the read-only preflight Job (`elasticsearch_9_preflight.md`); non-zero is
   **NO-GO**. Verify `GET /_migration/deprecations`,
   `GET /_migration/system_features` (`NO_MIGRATION_NEEDED`), ILM policies/explain,
   settings, disk, and snapshot access.
5. Confirm all 9.x plugins implement `modules.models.declare_extensions`
   (legacy `modify_odm`-only plugins fail startup). See
   [backend docs](../developer/backend.md).
6. Confirm rollback staffing, `8.19.11` rebuild readiness, and decision deadline.

## Gate 2 — quiesce writers and capture baseline

1. Enforce an ingress write freeze using a reviewed read-only route allowlist
   (block `POST` and login/OAuth auto-sync GET routes that write user records).
   Stop SDK/partner ingestion.
2. Pause Evidence, Sentinel, Sync, MCP write tools, cron/correlation/action/retention
   jobs, and scripts. Keep the 8.x app read-only behind the allowlist during
   the ES rolling upgrade. Confirm drained queues and record the freeze time.
3. Flush Howler indices and wait for completion:

   ```http
   POST /<prefix>-*/_flush
   ```

4. Run preflight in baseline-capture mode (`--baseline-capture --output /reports/es-baseline-8.19.json`)
   and verify `baseline_capture: true`, `source_stack_version: 8.19.11`, and
   `checks.ready: true`. If unsynced, flush and rerun.
5. Take a fresh full snapshot and wait for `state: SUCCESS`:

   ```http
   PUT /_snapshot/<approved-repository>/<change-id>-pre-es9?wait_for_completion=true
   {"include_global_state": true, "indices": "*", "ignore_unavailable": false, "partial": false}
   ```

   Only the active source cluster may write to this repository; any rebuild
   cluster must register it with `settings.readonly: true`.

## Gate 3 — rolling Elasticsearch & Kibana upgrade

Upgrade **one ES node at a time** to `9.5.2` in order:
`data_frozen` -> `data_cold` -> `data_warm` -> `data_hot` -> other data ->
non-data/non-master -> master/voting-only **last**. (Optionally place ML jobs in
upgrade mode beforehand and disable afterward.)

For each node:
1. Disable replica allocation (`PUT /_cluster/settings` ->
   `{"persistent": {"cluster.routing.allocation.enable": "primaries"}}`) and
   `POST /_flush`.
2. Stop the node, upgrade ES + plugins to `9.5.2` preserving the data path (do
   not set `cluster.initial_master_nodes`), and start it.
3. Confirm it joins at `9.5.2`, then re-enable allocation (`null`) and wait for
   **green** shard recovery before advancing.

After all nodes reach `9.5.2`, remove any archived cluster/index/template
settings before future ILM rollovers, and review Elastic's
[cluster-state encryption guidance](https://www.elastic.co/docs/reference/elasticsearch/cluster-state-encryption-key#cluster-state-encryption-upgrades)
for pre-9.5 clusters.

### Gate 3a — cluster & Kibana

Confirm all nodes report `9.5.2` and green health. On 9.x, `MIGRATION_NEEDED`
from `/_migration/system_features` and `reindex_required` deprecations for 8.x
indices are reported as `es10_readiness*` warnings—do **not** run system-feature
migration POST during cutover. Next, shut down **all** Kibana instances (no
rolling upgrade), start Kibana `9.5.2`, and wait for saved-object migrations.

## Gate 4 — deploy and verify 9.x application

1. Deploy the 9.x API/UI and compatible plugins with `HWL_USE_JOB_SYSTEM=false`
   and debug disabled; keep writers paused.
2. **If Gate 1 could not run migrations**: run the verifier with
   `--integrity-only --baseline /reports/es-baseline-8.19.json`, then run
   `howler-migrate --all` and confirm `applied`, then continue below running the
   full verifier **without** `--baseline` (rollback owner must accept the added
   post-snapshot data-loss window).
3. Initialize collections from the candidate API image (**not read-only**;
   triggers lazy `_ensure_collection`):

   ```bash
   python -m howler.external.elasticsearch_initialize_collections --confirm-reconciliation
   ```

   Any `HowlerValueError` or reconciliation refusal is **NO-GO**.
4. Run the full GET-only verifier Job (`--baseline /reports/es-baseline-8.19.json`
   on the preferred path). It verifies `9.5.2` node/cluster versions, green
   health (or `--allow-yellow`), 9.x critical deprecations, `expected_collections`,
   `_hot`/ILM layout, explicit `is_write_index: true` on latest ILM generation,
   ILM policy/template/explain, `_source`, mappings, dynamic templates (blocking
   shadowed active templates, warning on harmless obsolete ones and the legacy
   duplicate `date` template), `total_fields.limit`, `field_caps`, and baseline
   UUID/alias/per-shard sequence parity (tolerating 1 empty new collection or
   empty ILM rollover). A cutover lead may accept positive drift on a named
   index with repeatable `--accept-sequence-drift <index>` (never decreases) and
   record the rationale. Remediate older index field caps if needed via
   `PUT /<index>/_settings`. Exit `0` with no blockers is required.
5. Run controlled smoke tests using synthetic IDs and clean up afterward:
   - Unauthenticated `GET $HOWLER_API/v1/user/whoami` -> 401; authenticated -> 200.
   - `GET /v1/hit/$SMOKE_HIT_ID` + conditional `If-Match` -> 304.
   - Search/count under two ACL test principals vs rehearsal.
   - Disposable hit `POST /v1/hit/`, `GET`, `PUT /v1/hit/<id>/update`, `DELETE /v1/hit/`.
     Test stale `If-Match` on `POST /v1/hit/<id>/transition` (`update` does not
     enforce `If-Match`). Restrict `PUT /v1/hit/update` to `"howler.id:\"<id>\""`.
   - Verify bulk ingest/update, ACL denial, and plugin/job pause state.
6. Sign off evidence and authorize reopening.

## Gate 5 — reopen and monitor

Reopen in order: core API/ingestion -> Evidence/Sentinel/Sync -> redeploy API
with `HWL_USE_JOB_SYSTEM=true` -> general UI. Monitor health, latency, errors,
ACLs, ILM, and queues. Any writes after reopening are lost if snapshot rollback
is triggered.

## Rollback — rebuild and restore only

1. Reapply ingress freeze and stop the 9.x app, ingestion, plugins, and jobs.
2. Suspend SLM/snapshots on 9.x and deregister the shared repository.
3. **Never downgrade nodes in place.** Build a clean `8.19.11` ES + Kibana
   cluster on clean data paths.
4. Register the pre-upgrade repository with `readonly: true`, restore the
   pre-upgrade snapshot, and verify versions, health, aliases, and counts.
5. Repoint all services/plugins to the rebuilt `8.19.11` cluster, deploy the
   prior Howler release, run auth/ACL/CRUD/read checks, and reopen (documenting
   lost post-snapshot writes).
