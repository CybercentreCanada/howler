# Elasticsearch 9.5.2 production cutover runbook

This is the coordinated production procedure for moving Howler from Elasticsearch
and Kibana `8.19.11` to `9.5.2`, alongside the Pydantic/DSL-backed Howler
application release. It is an operator checklist, not a substitute for the
representative production rehearsal. **Do not schedule the production change
until every hard gate below has passed.**

The deployment sequence and restrictions follow Elastic's documentation:

- [Prepare to upgrade Elasticsearch](https://www.elastic.co/docs/deploy-manage/upgrade/prepare-to-upgrade)
- [Upgrade Elasticsearch on a self-managed cluster (rolling upgrade)](https://www.elastic.co/docs/deploy-manage/upgrade/deployment-or-cluster/elasticsearch)
- [Snapshot and restore](https://www.elastic.co/docs/deploy-manage/tools/snapshot-and-restore)

## Roles and change controls

Assign named people before the change begins; a person may hold more than one
role, but the rollback owner must be able to stop the cutover independently.

| Role | Responsibility |
| --- | --- |
| Cutover lead | Owns the timeline, go/no-go gates, change record, and final decision to reopen writes. |
| Elasticsearch lead | Owns 8.19 preflight, snapshot verification, each node upgrade, cluster health, and restoration. |
| Howler application lead | Owns the ingress-level write freeze, release/image consistency, collection initialization, verifier, API smoke checks, and application rollback. |
| Rollback owner | Has authority and access to rebuild 8.19.11 and restore the pre-upgrade repository; confirms the recovery path before the first node is upgraded. |
| Plugin / operations owners | Pause and validate Evidence, Sentinel, Sync, MCP, ingestion, schedulers, and background workers. |
| Communications lead | Announces maintenance, records decisions/evidence, and communicates reopening or rollback. |

Record the target versions, cluster/repository identifiers, node order, report
locations, test identities, rollback decision deadline, and contact details in
the change record. Store reports and credentials only in approved restricted
locations; never commit them to the repository or paste secrets into a ticket.

## Hard gate 0 — representative production-snapshot rehearsal

Before production is scheduled, the Elasticsearch and application leads must
complete and attach evidence for a representative, approved **production
snapshot restored to a multi-node Elasticsearch 8.19 cluster**. The rehearsal
must use production-representative topology, settings, plugins, index volumes,
and configured Howler extensions. It must:

1. Restore the approved snapshot onto the isolated multi-node 8.19 cluster and
    verify all nodes report `8.19.11` and cluster health is green.
2. Run the automated preflight, Kibana Upgrade Assistant, `GET
    /_migration/deprecations`, system feature status, ILM review, and deployment
    configuration review described below. Resolve every 9.x operational
    blocker. Track any Elasticsearch 10 readiness work separately; do not run it
    during this 8.19-to-9.5.2 cutover.
3. Upgrade nodes using the documented rolling order and health gates, then
    upgrade Kibana only after Elasticsearch is fully healthy on 9.x. Shut down
    all Kibana instances before upgrading; this is not a rolling upgrade.
4. Deploy the candidate Howler release and run the post-cutover verifier against
    a quiesced pre-upgrade baseline. Complete application authentication/ACL,
    CRUD, ETag, bulk/update, and plugin checks with background jobs disabled
    until writes are explicitly reopened.
5. Rehearse snapshot-based rollback: stop the candidate application, rebuild an
    8.19.11 cluster, restore the pre-upgrade snapshot, redeploy the prior Howler
    release, and verify it. Register the rehearsal/rebuild's repository as
    read-only; never let two clusters write to one repository. Do not attempt an
    in-place Elasticsearch downgrade.

Any failed or unverified step is **NO-GO**.

## Production execution environment for the tools

Run both checks as short-lived Jobs/pods, not from a workstation or a source
checkout. Before creating a Job, capture the immutable 9.x API image reference
from the candidate deployment, for example:

```bash
kubectl get deployment "$HOWLER_API_DEPLOYMENT" \
  -o jsonpath='{.spec.template.spec.containers[?(@.name=="api")].image}'
```

Set `HOWLER_API_IMAGE` to that exact repository **and tag or digest**. Do not
use `latest`, a developer image, or a different release image. The preflight
must run inside this 9.x image while targeting the still-8.19.11 cluster; that
is specifically why it uses raw REST instead of the pinned 9.x client. The
verifier uses the same 9.x image as the deployed candidate.

Use an operator-created Job based on the REST deployment's rendered pod spec:

```yaml
containers:
  - name: es-check
    image: "<exact-candidate-9.x-API-image-tag-or-digest>"
    imagePullPolicy: IfNotPresent
    command: ["python", "-m", "howler.external.elasticsearch_preflight"]
    args: ["--output", "/reports/es-preflight-8.19.json"]
    env: # Copy the REST deployment's matching env, Secret refs, and prefix.
      - name: ELASTICSEARCH_URL
        value: "https://elasticsearch.example:9200"
      - name: HWL_DATASTORE_INDEX_PREFIX
        value: "<same-prefix-as-the-API>"
      # Use one of these authentication options, sourced from a Secret:
      - name: ELASTIC_API_KEY
        valueFrom: {secretKeyRef: {name: es-check-auth, key: api-key}}
    volumeMounts: # Copy the same ConfigMap, CA, and enabled plugin mounts.
      - name: howler-conf
        mountPath: /etc/howler/conf
        readOnly: true
      - name: howler-plugins
        mountPath: /etc/howler/plugins
        readOnly: true
      - name: reports
        mountPath: /reports
```

Render this fragment as a complete Job using the API deployment's service
account, network policies, Secrets, `backoffLimit: 0`, and `restartPolicy: Never`.
For the verifier, use:

```yaml
command: ["python", "-m", "howler.external.elasticsearch_cutover_verify"]
args: ["--baseline", "/reports/es-baseline-8.19.json", "--output", "/reports/es-cutover-9.5.2.json"]
```

Copy every relevant environment variable and Secret reference from the API
deployment: Elasticsearch host/auth/TLS settings, `HWL_CONF_FOLDER`,
`HWL_DATASTORE_INDEX_PREFIX`, `HWL_PLUGIN_DIRECTORY`, and any plugin-specific
configuration. The verifier imports the Howler configuration and plugin
registry; provide the same Redis config and network reachability as the API as
well as classification/config files and plugin packages. Mount the preflight
JSON from approved restricted storage read-only at `/reports` for verifier
baseline use, and write the generated report to restricted storage. Do not put
credentials in Job YAML literals or logs.

For these two REST tools, authentication variables are `ELASTIC_API_KEY` **or**
the pair `ELASTIC_USERNAME` and `ELASTIC_PASSWORD`. These are distinct from the
API datastore's host credentials (for example, `<HOST>_HOST_USERNAME` and
`<HOST>_HOST_PASSWORD`); explicitly map the appropriate approved Secret into
the Job instead of assuming the API's datastore credentials are read directly.
The tools accept `ELASTICSEARCH_URL` but refuse credentials embedded in URL
user-info; keep authentication in the named environment variables.

The verifier and the initializer share plugin-path setup that mirrors
`howler/app.py`: prepend only `HWL_PLUGIN_DIRECTORY`, and in debug mode append
the per-plugin virtual-environment site-package paths. They deliberately do not
prepend each plugin subdirectory, which could shadow the package selected by the
API or standard-library modules. Both fail closed with the configured plugin
name if a plugin cannot be loaded.

Operator invocation in the Job is `python -m howler.external.elasticsearch_preflight`
or `python -m howler.external.elasticsearch_cutover_verify`; `poetry run` in the
examples below is for developer validation only. Retain the Job image reference,
rendered configuration/mount list, logs, and reports with the change record.

## Gate 1 — preflight and operational readiness

Complete these checks against the target production cluster while it is still on
`8.19.11`:

1. Confirm all Elasticsearch nodes and Kibana are on the supported source patch
    `8.19.11`. Confirm the planned target packages/images are exactly `9.5.2`.
2. In Kibana's Upgrade Assistant, resolve every critical issue. Review warnings
    and deprecation logs while representative traffic is running.
3. In a separate pre-cutover 8.19 maintenance window, inspect the migration
    runner in the **currently deployed** API image. Confirm that
    `howler-migrate --list` (or `python -m howler.external.run_migrations --list`)
    exists in that image, then list the
    registered migration IDs. Inspect the `<prefix>-migration` collection for a
    record with `status: applied` for every registered ID. A missing record is
    not proof that a migration is unnecessary. The runner is present in the
    release only if that image supports this command; do not assume a future
    release's runner is available in an older image. The current registered IDs
    are `action-owner-id-to-owner` and `metadata-case-insensitive-search`; the
    latter reindexes `view`, `action`, `dossier`, `template`, and `overview` and
    changes those index UUIDs/normalizers.

    Verify individual records with read requests such as
    `GET /<prefix>-migration/_doc/metadata-case-insensitive-search`; the
    response must contain `status: applied` for each listed migration.

    Preferred path: if any registered migration is unapplied and the deployed
    8.19 release contains the runner, schedule a distinct migration window,
    quiesce datastore writers, run `howler-migrate --all` as the one-off Job
    using the deployed 8.19 image, verify all migration records are `applied`,
    and restore the ordinary 8.19 service. Complete this **before** the final
    write freeze, baseline, and fresh cutover snapshot. Migrations can reindex
    collections and change UUIDs, so do not apply them after capturing the
    baseline if they can be run beforehand. See
    [`documentation/docs/migration.md`](../migration.md).

    If the currently deployed release has no migration runner or cannot complete
    these migrations before the cutover window, follow the ordered fallback in
    Gate 4; do not skip migrations or treat their expected mapping/UUID changes
    as ordinary verifier failures.

4. Run the read-only Howler preflight Job specified above with an account
    limited to the necessary monitoring/read privileges. See the
    [preflight guide](elasticsearch_9_preflight.md) for CLI options, report
    fields, and the complete operational review. It sends only GET requests with
    plain `application/json` headers. The report includes cluster/index
    inventory, UUIDs, counts, aliases and write
    flags, and ILM explain state for Howler-prefixed indices. A non-zero exit is
    **NO-GO**; retain the complete report and resolve every blocker.

5. Review `GET /_migration/deprecations` and
    `GET /_migration/system_features`; there must be no critical deprecations and
    no pending system feature migrations. Review all warnings with the owners.

6. Review every Howler ILM policy and `GET /<howler-index>/_ilm/explain` result;
    confirm rollover alias, latest write index, rollover policy, lifecycle
    settings, and all backing-index mappings. Review deployment settings, node
    roles, JVM/OS settings, Elasticsearch plugins, remote clusters, templates,
    pipelines, security configuration, disk capacity, shard allocation, and
    snapshot repository access on the rebuilt 8.19 nodes.

7. Confirm the 9.x application packages and all plugin images/packages are from
    the same approved release. Check plugin compatibility and migration notes.
    The Pydantic-backed release no longer accepts plugins that rely only on
    legacy `modify_odm` mutation: such plugins fail application startup unless
    they provide typed `modules.models.declare_extensions` hooks. See
    [Howler plugin development](../developer/backend.md) and
    [`docs/api/plugins.md`](https://github.com/CybercentreCanada/howler/blob/main/docs/api/plugins.md).

8. Confirm rollback staffing, access, repository credentials, rebuild capacity,
    and recovery duration. The rollback owner must demonstrate that the planned
    8.19.11 rebuild can read the repository. Agree a rollback decision deadline
    before starting; after the first node upgrade, the existing cluster cannot
    be downgraded and the rolling upgrade must be completed or rolled back by
    rebuild-and-restore.

Retain the clean preflight and review evidence with restricted change records.
Do not put credentials, private topology reports, or snapshots in source
control.

## Gate 2 — quiesce all writers and capture the baseline

Howler has no built-in maintenance/read-only mode. The cutover lead begins the
write freeze only after the rehearsal and preflight are approved, using the
organization's ingress/API gateway policy and explicit writer shutdowns.

1. Announce the write freeze. At ingress, deny mutating API methods and use a
    reviewed route allowlist; do not assume that blocking `POST` alone makes
    Howler read-only. UI search may use `POST` and will therefore be unavailable
    while that method is blocked. Some authentication/login GET routes, including
    OAuth auto-sync, can create or update user records: block those routes at
    ingress unless auto-sync has been disabled. Confirm no
    remaining allowed GET route performs writes. Stop or pause client/SDK
    ingestion, partner feeds, and every external producer.
2. Pause the Evidence, Sentinel, and Sync plugin writers; scheduled imports;
    cron jobs; correlation/action queues; retention and other background jobs;
    MCP tools or integrations that can write; and any administrative scripts.
    Keep the previous 8.x application available only behind the reviewed
    read-only allowlist during the Elasticsearch rolling upgrade; do not deploy
    the 9.x app yet. The 8.x client can use Elasticsearch REST compatibility
    against 9.x, but compatibility is only a bridge, not permission to write
    during the freeze.
3. Each owner confirms queues are drained or safely paused, no in-flight writes
    remain, and the freeze is visible in logs/metrics. The cutover lead records
    the confirmed freeze time. If any writer cannot be accounted for, stop.
4. After all writes are quiesced, flush the Howler indices before recording
    statistics. This is cluster maintenance, not an application write:

    ```http
    POST /<prefix>-*/_flush
    ```

    Wait for the flush to complete and confirm cluster health. This prevents
    search-idle shards from reporting stale Lucene document counts. Both tools
    capture primary document counts, `max_seq_no`, and `global_checkpoint` from
    the same shard-level stats API.

5. Rerun the preflight one-off Job in baseline-capture mode and save the JSON
    report as the **baseline**. Use these Job arguments:

    ```yaml
    command: ["python", "-m", "howler.external.elasticsearch_preflight"]
    args: ["--baseline-capture", "--output", "/reports/es-baseline-8.19.json"]
    ```

    Confirm its `baseline_capture` field is `true`, its source is `8.19.11`, and
    `checks.ready` is `true`; retain it at the restricted location recorded in
    the change plan. Follow the [preflight guide](elasticsearch_9_preflight.md)
    for the checkpoint synchronization gate and the required recapture procedure
    if statistics are incomplete or unsynced.

6. Immediately before the first Elasticsearch node is upgraded, take a fresh
    full snapshot in the approved repository. Include the required cluster
    state/feature states and Howler indices. Wait for completion and independently
    verify snapshot `state` is `SUCCESS` and that its listed indices include all
    expected Howler and required system indices. Record repository, snapshot name,
    start/end time, and verification output. The active source cluster is the
    only cluster allowed to write to that repository. Use a separate
    rehearsal-owned repository if the rehearsal must create its own snapshot.

7. Any rehearsal, restored, or rebuild cluster mounting the same repository
    must register it with `settings.readonly: true` (alongside the repository
    type's normal settings). Verify the repository is readable by the planned **8.19.11
    rebuild**. Do not begin unless the snapshot and restore path are both
    verified. Snapshots created after an Elasticsearch upgrade on 9.x cannot be
    restored to an 8.19 cluster; they are not a rollback substitute.

Example operator-side snapshot calls (replace the repository and snapshot with
approved names; these are write operations and are intentionally not used by
the verifier):

```http
PUT /_snapshot/<approved-repository>/<change-id>-pre-es9?wait_for_completion=true
{"include_global_state": true, "indices": "*", "ignore_unavailable": false, "partial": false}

GET /_snapshot/<approved-repository>/<change-id>-pre-es9
```

The GET result must report `SUCCESS` and the expected index list. Follow the
organization's snapshot policy for feature states and exclusions; explicitly
document any deliberately excluded index/feature and its recovery source.

## Gate 3 — rolling Elasticsearch upgrade

The Elasticsearch lead upgrades **one node at a time** to `9.5.2`; the cutover
lead records each node's pre/post version and health gate. Do not begin if the
team cannot complete the full rolling upgrade. Mixed versions are supported
only during the active rolling upgrade.

Upgrade nodes in this order, applying the first matching role to multi-role
nodes:

1. Data tiers: `data_frozen`, then `data_cold`, then `data_warm`, then
    `data_hot`, then any remaining data nodes.
2. All remaining nodes that are neither data nor master-eligible (for example,
    ingest, ML, transform, remote-cluster-client, and coordinating-only nodes).
3. Master-eligible and voting-only master nodes **last**.

Before the first node, optionally place active Machine Learning jobs in upgrade
mode or close jobs/datafeeds under the ML owner's procedure to reduce load. If
upgrade mode is used, record the enabling action and disable it after the
cluster upgrade so jobs resume. Do not improvise ML state changes during the
rolling operation.

For each data node, use the Elastic rolling-upgrade procedure:

1. Disable replica allocation (keep primaries allocated), then flush as directed
    by the Elasticsearch lead. Example cluster setting:

    ```http
    PUT /_cluster/settings
    {"persistent": {"cluster.routing.allocation.enable": "primaries"}}

    POST /_flush
    ```

2. Stop only the selected node, upgrade its Elasticsearch package/image and
    plugins to `9.5.2`, preserve its data path and required node configuration,
    then start it. Do not set `cluster.initial_master_nodes` for a rolling
    upgrade.
3. Confirm the node rejoins, reports the expected target version, and has no
    startup/plugin errors. Re-enable allocation immediately after the node has
    joined:

    ```http
    PUT /_cluster/settings
    {"persistent": {"cluster.routing.allocation.enable": null}}
    ```

4. Wait for shard recovery and the agreed health gate (green) before proceeding
    to the next node. Check cluster health, pending tasks, shard allocation, and
    logs. Do not treat a node that has joined but has not recovered as a passed
    gate. Repeat per node in the order above.

Keep Howler writes quiesced for the entire server upgrade. The existing 8.x app
may serve approved read-only requests using REST compatibility. Escalate any
red health, failed node join, allocation error, or unexpected index/system
feature migration to the cutover lead; do not improvise a downgrade.

After all nodes are on 9.5.2 and before relying on future ILM rollovers, review
archived settings on cluster, index, and composable-template state. Remove
unsupported/archived settings using the approved operator procedure; archived
settings left in index templates can make a later rollover fail. For clusters
originally created before 9.5, review Elastic's [cluster-state encryption after
upgrade guidance](https://www.elastic.co/docs/reference/elasticsearch/cluster-state-encryption-key#cluster-state-encryption-upgrades)
and configure the password on every node if required for the features Howler
uses.

### Gate 3a — cluster and Kibana

After every Elasticsearch node is upgraded, require **all** nodes to report
`9.5.2`, cluster health green, and no unresolved shard allocation/pending task
issues. `MIGRATION_NEEDED` from `GET /_migration/system_features` on 9.x is
Elasticsearch 10 preparation, not a blocker for this 9.5.2 cutover. The verifier
reports it as an `es10_readiness_system_features` warning. Do not run the
system-feature migration POST during this cutover; schedule and rehearse it as
separate Elasticsearch 10 preparation. Similarly, `reindex_required` critical
deprecations for old 8.x indices/data streams are reported as
`es10_readiness` warnings because this cutover preserves their UUIDs; every
other critical 9.x operational deprecation remains a blocker.

Only after Elasticsearch is healthy on 9.5.2 may the Kibana lead upgrade
Kibana. Shut down **all** Kibana instances first; Kibana does not support a
rolling upgrade, and Kibana 8.19 is degraded while connected to Elasticsearch
9.x. Start Kibana 9.5.2 and wait for its saved-object migrations to complete
and startup to stabilize before continuing. Do not gate on a 9.x Upgrade
Assistant completion message; the Upgrade Assistant review was performed on
8.19 before the server upgrade.

## Gate 4 — deploy and verify the 9.x application

1. Keep external writers, queues, schedules, and general user writes paused.
    Deploy the approved 9.x Howler API/UI release and the mutually compatible
    Evidence, Sentinel, Sync, and MCP packages/images. Confirm deployed release
    identifiers and configuration (including datastore prefix, ILM choices,
    enabled plugins, and extension hooks) match the rehearsal. Until writes
    reopen, deploy with `HWL_USE_JOB_SYSTEM=false` and debug disabled; do not
    start retention, view-cleanup, correlation, or action-queue jobs.
2. If the preferred Gate 1 migration path completed, confirm every registered
    migration record is `applied` and continue. Otherwise, use this fallback in
    exactly this order while ordinary writers remain paused:
    1. Deploy the 9.x API with jobs disabled and debug off.
    2. Run the verifier Job with `--integrity-only --baseline
        /reports/es-baseline-8.19.json`; this checks cluster/version/health and
        tolerated baseline integrity but deliberately skips schema checks that
        the migration will change. Example Job args:

        ```yaml
        command: ["python", "-m", "howler.external.elasticsearch_cutover_verify"]
        args: ["--integrity-only", "--baseline", "/reports/es-baseline-8.19.json"]
        ```

    3. Run `howler-migrate --all` as the approved one-off Job from the candidate
        API image. Check every registered migration record is `applied`.

    4. Continue with the collection initialization and full verification steps
        below, running the full verifier **without** `--baseline` because
        migrations intentionally reindex collections and create migration records.

    5. Complete the application smoke tests below.

    Migration writes/reindexes performed after the pre-upgrade snapshot will be
    lost if rollback restores that snapshot. The rollback owner must explicitly
    accept this additional data-loss window before using the fallback.

3. Initialize every collection before contract verification using the separate
    operator command below, from the exact candidate API image and deployed
    configuration:

    ```bash
    python -m howler.external.elasticsearch_initialize_collections --confirm-reconciliation
    ```

    **This initializer is not read-only.** It obtains the normal datastore and
    touches only each registered `datastore.<collection>` attribute, which
    invokes the application's own lazy `_ensure_collection` behavior and may
    create/reconcile indices, mappings, ILM policies, and templates. Keep jobs
    and ordinary writers disabled. Inspect application logs for
    `HowlerValueError`, schema reconciliation refusals, or ILM/template errors;
    any refusal is **NO-GO**. The following verifier itself remains GET-only.

4. Run the full verifier from a one-off Job/pod using the production 9.x API
    image/config/plugin/Redis setup documented above. For the preferred
    pre-migration baseline path, use the verifier Job spec above with the
    quiesced preflight report. Omit `--baseline` only in the migration fallback,
    after migrations and initialization have completed and their records/evidence
    are retained.

    The verifier issues only GET requests. It checks exact node versions,
    cluster health (green by default; yellow is accepted only with the explicit
    `--allow-yellow` flag and is reported), active system-feature migration
    (`IN_PROGRESS`/`ERROR`), and 9.x operational critical deprecations. Track
    Elasticsearch 10 readiness warnings separately as described in Gate 3a.
    Compare the report's `expected_collections` (collection names, aliases, ILM
    choices, and field
    limits) with the approved rehearsal report; an unexpected difference is
    **NO-GO** until explained and rehearsed. Baseline comparison tolerates one
    empty, unwritten ILM generation rollover and empty post-baseline
    initialization of configured collections. It blocks missing/replaced
    baseline indices, UUID or alias metadata changes, and per-shard document
    count or `max_seq_no` changes. Baseline and current primary checkpoints must
    be synchronized; if not, keep the cluster quiesced and follow the preflight
    guide's checkpoint recovery procedure before rerunning. There is no implicit
    sequence-number tolerance. A cutover lead may explicitly accept drift on a
    named physical index with repeatable `--accept-sequence-drift <index>` flags, for example
    `<prefix>-user_hot` or `<prefix>-user_avatar_hot`. Acceptance is a warning,
    includes per-shard baseline/current counts and sequence numbers, never accepts
    a `max_seq_no` decrease, and does not waive UUID, alias, or synchronization
    checks. Recording the decision and rationale in the change record is
    mandatory. Prevent OAuth auto-sync writes as described in Gate 2, step 1.

    It loads the deployed configuration and finalized models without
    constructing a datastore or reconciling Elasticsearch. It checks each
    initialized collection's configured `_hot` or ILM layout, one write index,
    ILM explain plus the future rollover index template and hot rollover policy,
    expected property definitions and ordered active templates, field limits,
    and `field_caps` conflicts. Schema-less `user_avatar` property/template drift
    is reported as a warning to mirror application startup behavior. The source
    default-template list has a duplicate `date` name: Elasticsearch keeps the
    last definition (`*_dts`) at the first name position, so the shadowed `*_dt`
    rule is reported as informational readiness debt; do not fix it in this
    cutover. `collection_not_initialized` blockers must not remain after the
    explicit initializer step; if one appears, investigate and repeat
    initialization/reconciliation before sign-off.

5. The verifier must exit `0` with no blockers. Review every warning and repair
    or explicitly disposition it before reopening. For older backing indices
    whose field limit is below the current schema limit but still at least the
    number of mapped fields, record a warning and assess future extension risk.
    If the write index is below the computed limit, or any index is below its
    actual mapped field count, the result is a blocker. An Elasticsearch lead
    may remediate a reviewed index with a recorded operator change such as:

    ```http
    PUT /<physical-index>/_settings
    {"index.mapping.total_fields.limit": <max-of-current-schema-limit-and-actual-mapped-fields>}
    ```

    Re-run initialization/reconciliation as needed, then rerun the verifier.

6. The application lead performs controlled smoke tests against Howler while
    ordinary user/producer writes remain paused. Use approved test principals
    and unique synthetic IDs, never real incident data. Remove test records and
    verify cleanup before general reopening. Route all smoke writes through the
    application, not directly to Elasticsearch.

    Example requests (set `HOWLER_API` to the deployed API root such as
    `https://howler.example/api`, and `HOWLER_AUTH` to a protected valid
    `Authorization` header; do not put credentials in shell history):

    ```bash
    # Unauthenticated access must be denied (normally 401).
    curl -i "$HOWLER_API/v1/user/whoami"

    # Authenticated identity/access smoke check.
    curl -fsS -H "$HOWLER_AUTH" "$HOWLER_API/v1/user/whoami"

    # Read a known, approved smoke hit and capture its ETag.
    curl -i -H "$HOWLER_AUTH" "$HOWLER_API/v1/hit/$SMOKE_HIT_ID"

    # A conditional GET may return 304 for the matching ETag.
    curl -i -H "$HOWLER_AUTH" -H "If-Match: $SMOKE_ETAG" \
      "$HOWLER_API/v1/hit/$SMOKE_HIT_ID"

    # Search/read and count through the API under two test principals with
    # different ACLs; compare returned IDs, counts, and facets to the rehearsal.
    curl -fsS -H "$HOWLER_AUTH" "$HOWLER_API/v1/search/hit?query=$SMOKE_QUERY"
    curl -fsS -H "$HOWLER_AUTH" "$HOWLER_API/v1/search/count/hit?query=$SMOKE_QUERY"
    ```

    Using documented payloads and disposable IDs, verify create (`POST
    /v1/hit/`), read (`GET /v1/hit/<id>`), update (`PUT /v1/hit/<id>/update`,
    whose decorator does **not** enforce `If-Match`), and delete (`DELETE
    /v1/hit/`). Test stale-version `If-Match` behavior on the transition route
    (`POST /v1/hit/<id>/transition`), which is the write path that honors it;
    do not claim the update route enforces that precondition. Update-by-query
    (`PUT /v1/hit/update`) must use a query restricted to the disposable smoke
    ID(s), never a broad query. For example, supply
    `"query":"howler.id:\"<unique-smoke-id>\""` and a harmless operation on
    that test hit only. Also verify bulk ingestion/update, ETag behavior, ACL
    denial for restricted data and access for authorized users. Check
    plugin-specific ingest/output paths, scheduled job/queue health, ownership,
    logs, and that no paused job unexpectedly resumed. Capture request IDs,
    response codes, ETags, returned counts, and cleanup results in the change
    record.


7. The cutover lead and all owners sign off the verifier and smoke-test evidence.
    If every check passes, the cutover lead authorizes reopening writes.

## Gate 5 — reopen and monitor

Re-enable write access in a controlled order: core API/approved ingestion first,
then Evidence/Sentinel/Sync and external producers, then scheduled/background
jobs and MCP write tools, then general UI traffic. Confirm the first writes are
visible through the application and that queues, plugin processing, and jobs are
healthy. Monitor cluster health, allocation, disk, indexing/search latency,
rejections, application errors, ACL outcomes, ILM steps/rollovers, and plugin
queues for the agreed observation window. Stop reopening and page the rollback
owner if a critical gate regresses.

Before resuming scheduled/background jobs, redeploy the API with the job system
enabled (`HWL_USE_JOB_SYSTEM=true`) and debug set to its approved production
configuration.

After writes reopen, the snapshot remains the rollback point. **Any writes made
after reopening will be lost if rollback restores that snapshot.** Record the
time of the first production write and the rollback decision deadline; the
cutover lead explicitly accepts this data-loss window before reopening.

## Rollback — rebuild and restore only

The rollback owner controls the decision together with the cutover lead. Trigger
rollback for an unrecoverable cluster/application gate, data integrity or ACL
failure, critical plugin/job failure, or inability to meet the agreed decision
deadline. The rollback owner must state whether post-reopen writes will be lost
and obtain the incident/change authority's decision before restoration.

1. Reapply the ingress-level write freeze and stop the 9.x application, all write APIs,
    ingestion, plugin writers, background jobs, MCP write tools, and external
    producers. Preserve logs/reports for diagnosis.
2. Stop snapshot activity on the 9.x cluster. Disable/suspend SLM and in-flight
    snapshot jobs, then deregister the shared repository from 9.x (or otherwise
    remove its write access) before registering it elsewhere. Never allow both
    clusters to write to the same snapshot repository.
3. **Never downgrade the upgraded nodes in place.** Build a clean Elasticsearch
    `8.19.11` cluster and matching Kibana from approved packages/configuration.
    Do not point the old version at 9.x data paths.
4. Register the pre-upgrade repository on the rebuilt cluster with
    `readonly: true`. Restore the immediately pre-upgrade snapshot (including the
    agreed cluster/feature state and Howler indices), wait for completion, and
    verify node versions, health, aliases/write indices, mappings, and counts.
5. Repoint Elasticsearch endpoints/configuration for Howler API, Kibana,
    Evidence, Sentinel, Sync, MCP, ingestion clients, and background services to
    the rebuilt cluster. Deploy the prior Howler application and compatible
    plugins. Verify authentication, ACL/search, key CRUD/ETag and ingestion
    reads, plus background-job state, before relaxing the ingress freeze.
6. The cutover lead authorizes reopening, accounting explicitly for writes after
    the snapshot that are not present in the restored cluster. Document the
    incident, recovery point, data-loss window, and follow-up rehearsal fixes.

Do not try to restore a snapshot created on 9.x to 8.19; Elasticsearch does not
support restoring a newer-version snapshot into an earlier cluster. Rollback is
always a rebuild of the old version plus restoration of the verified
pre-upgrade snapshot.

## Follow-up

Archive the approved baseline, verifier, and snapshot evidence in the restricted
change record, and close the change only after the observation window and owner
sign-offs.
