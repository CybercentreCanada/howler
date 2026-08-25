# Elasticsearch 9 preflight

Howler must be running Elasticsearch and Kibana `8.19.11` before upgrading to
Elasticsearch 9. Run this preflight against a production-like cluster and each
production cluster before scheduling the coordinated cutover.

## Collect the automated report

Use an API key:

```bash
cd api
export ELASTICSEARCH_URL="https://elasticsearch.example:9200"
export ELASTIC_API_KEY="<api-key>"
poetry run python -m howler.external.elasticsearch_preflight \
  --output elasticsearch-9-preflight.json
```

For basic authentication, set `ELASTIC_USERNAME` and `ELASTIC_PASSWORD` instead.
Use `--ca-certs <path>` for a private certificate authority. Do not commit the
report because it contains cluster topology and configuration.

The command exits non-zero when the cluster:

- is not running Elasticsearch `8.19.11`;
- has red or unknown health;
- reports a critical migration deprecation;
- has pending system feature migrations; or
- contains an index created before Elasticsearch 8.0.

The report also inventories index creation versions and aliases, composable,
component, and legacy templates, ILM policies, ingest pipelines, analyzers and
node settings, snapshot repositories, remote clusters, and all informational or
warning-level deprecations.

## Complete the operational review

1. Open the Kibana Upgrade Assistant and enable deprecation logging and
   deprecation indexing while representative traffic is running.
2. Resolve every critical item from the Upgrade Assistant,
   `GET /_migration/deprecations`, and the automated report. Classify and assign
   every warning.
3. Run all required system feature migrations until the feature migration
   status is `NO_MIGRATION_NEEDED`.
4. Reindex, delete, or explicitly archive every pre-8.0 index. Verify each
   Howler alias, ILM rollover index, template, policy, pipeline, analyzer,
   security realm, snapshot repository, and remote or monitoring relationship.
5. Rerun the command and retain the clean report with the private upgrade
   records for the cluster.

The preflight is read-only. It does not run system feature migrations, alter
deprecation settings, reindex data, or replace the Kibana Upgrade Assistant.
