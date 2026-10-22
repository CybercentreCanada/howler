# Howler Sentinel Plugin

This plugin contains modules for Microsoft Sentinel integration in Howler.

## Tenant organization mapping

Sentinel incidents must have a `tenantId` that exactly matches an entry in
`tenant_mapping`. The configured value is the Howler organization name used on
the incident root hit and every child alert. Tenant IDs are not normalized or
case-folded. The mapping defaults to empty, so Sentinel ingestion returns HTTP
400 until at least the sending tenant is configured. A mapping value must be a
non-blank string. An explicitly configured organization named `Unknown Customer`
is valid.

### Standalone configuration

Add the tenant IDs and organization names to `/etc/howler/conf/sentinel.yml`,
merging these keys into any existing Sentinel plugin configuration:

```yaml
name: sentinel
tenant_mapping:
  "<exact-microsoft-tenant-id>": "Example Organization"
  "<another-exact-tenant-id>": "Another Organization"
```

The tenant ID comes from the incident's top-level `tenantId`. Child alerts are
assigned the same organization as their parent incident, even if an alert has a
different `tenantId` value.

### Helm configuration

With the Howler Helm chart, enable both the evidence and Sentinel plugins and
provide the mapping in ordinary, nonsecret Helm values. The chart serializes
`plugins.sentinel` to `sentinel.yml` in the `howler-server-conf` ConfigMap;
`tenant_mapping` is not a Kubernetes Secret. Keep any other currently enabled
plugin names in `config.core.plugins` as well.

```yaml
config:
  core:
    plugins:
      - evidence
      - sentinel

plugins:
  sentinel:
    name: sentinel
    tenant_mapping:
      "<exact-microsoft-tenant-id>": "Example Organization"
      "<another-exact-tenant-id>": "Another Organization"
```

### Upgrade migration

Older deployments may have relied on an in-code example mapping. That mapping
has been removed. Before upgrading, add every tenant that should be allowed to
ingest to `tenant_mapping`; with the empty default, all incoming incidents are
rejected until their exact tenant IDs are present. Use the actual top-level
`tenantId` values from Sentinel and map each one to the desired organization
name.

This configuration change does not relabel existing hits. Re-ingesting an
existing incident only applies the existing status-update behavior; its root
and child organization fields are not backfilled or changed. New incidents use
the configured organization name and exact tenant ID on the root and child
hits.
