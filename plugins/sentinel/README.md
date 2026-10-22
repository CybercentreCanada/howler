# Howler Sentinel Plugin

This plugin ingests Microsoft Sentinel XDR incidents as ordinary Howler hits
organized into native Howler cases. It has no runtime dependency on the Evidence
plugin; enable and install Sentinel alone when Sentinel is the only optional
plugin needed.

## Case and hit hierarchy

Each ingested incident creates one case, including incidents with no alerts:

```text
Sentinel case
├── incident summary hit
└── alerts/
    └── <stable source-alert hit ID>/
        ├── source alert hit
        ├── evidence hit (one per Graph evidence object)
        └── ...
```

The incident summary and source alert remain normal hits. Each former Graph
`alerts[].evidence[]` object is its own normal child hit under the source alert's
folder. Evidence hits retain their original JSON in `howler.data` and include
supported ECS fields when a mapping is available; unknown types and fields from
other plugins are preserved in the raw JSON without requiring those plugins.
Sentinel-owned metadata identifies the incident, tenant, source alert, and
evidence record. The case provides reciprocal hit membership links.
Graph classification values stay in the retained source JSON; ingestion does
not turn them into Howler analyst assessments or the workflow-only
`Escalation.EVIDENCE` disposition.

Replay uses tenant-scoped stable hit IDs. Repeated alerts/evidence do not create
duplicates; newly observed alerts and evidence are added. An omitted collection
does not delete existing case data. Incident status updates propagate only to
Sentinel-owned hits in the case, not analyst-added case hits. Derived evidence
hits are not sent to outbound actions as independent Graph alerts or incidents.

This hierarchy is a breaking change. The plugin does not migrate or backfill
pre-existing Sentinel bundles, evidence-plugin records, or cases. Those records
remain untouched; only incidents ingested after the change use the native case
hierarchy.

## Tenant organization mapping

Sentinel incidents must have a `tenantId` that exactly matches an entry in
`tenant_mapping`. The configured value is the Howler organization name used on
the incident summary, source alert, and evidence hits. Tenant IDs are not
normalized or case-folded. The mapping defaults to empty, so Sentinel ingestion
returns HTTP 400 until at least the sending tenant is configured. A mapping
value must be a non-blank string.

### Standalone configuration

Add tenant IDs and organization names to
`/etc/howler/conf/sentinel.yml`, merging these keys into any existing Sentinel
plugin configuration:

```yaml
name: sentinel
tenant_mapping:
  "<exact-microsoft-tenant-id>": "Example Organization"
  "<another-exact-tenant-id>": "Another Organization"
```

The tenant ID comes from the incident's top-level `tenantId`. All child hits
inherit the parent incident's organization, even if an alert has a different
`tenantId` value.

### Helm configuration

Install the Sentinel plugin package in the API image, enable `sentinel` in
`config.core.plugins`, and provide the mapping in ordinary, nonsecret Helm
values. The chart serializes `plugins.sentinel` to `sentinel.yml` in the
`howler-server-conf` ConfigMap; `tenant_mapping` is not a Kubernetes Secret.

```yaml
config:
  core:
    plugins:
      - sentinel

plugins:
  sentinel:
    name: sentinel
    tenant_mapping:
      "<exact-microsoft-tenant-id>": "Example Organization"
```

### Upgrade

Configure every tenant that should be allowed to ingest before upgrading. The
empty default rejects missing, blank, and unmapped tenant IDs with HTTP 400
before datastore access. This release does not migrate historical Sentinel
hits, evidence, or case memberships; existing records are not backfilled by
re-ingestion. Newly ingested incidents use the hierarchy above.
