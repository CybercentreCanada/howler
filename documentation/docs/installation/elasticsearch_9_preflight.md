# Elasticsearch 9 preflight

Howler must be running Elasticsearch and Kibana `8.19.11` before upgrading to
Elasticsearch 9. Run this preflight against a production-like cluster and each
production cluster before scheduling the coordinated cutover.

The coordinated cutover targets Elasticsearch and Kibana `9.5.2` with
`elasticsearch-py` `9.5.0` and Pydantic v2. The server patch includes Lucene
`10.5.1`, which fixes the query correctness issue documented for Elasticsearch
9.5.1.

## Collect the automated report

The tool uses raw REST with plain `application/json` headers. This is required
because the pinned 9.x Python client negotiates REST compatibility version 9,
which Elasticsearch 8.19 rejects. Requests are limited in code to `GET`; no
credentials are written to the report or logs.

Use an API key:

```bash
cd api
export ELASTICSEARCH_URL="https://elasticsearch.example:9200"
export ELASTIC_API_KEY="<api-key>"
poetry run python -m howler.external.elasticsearch_preflight \
  --output elasticsearch-9-preflight.json
```

During live traffic, run without `--baseline-capture`; unsynced or incomplete
primary checkpoint statistics are reported as warnings so ordinary traffic does
not make the preflight flap. Only after writers are quiesced, use the explicit
baseline-capture mode, which blocks unless the checkpoint stats are complete and
synchronized:

```bash
poetry run python -m howler.external.elasticsearch_preflight \
  --baseline-capture --output elasticsearch-9-preflight-baseline.json
```

That report has `baseline_capture: true` and is the only kind accepted by the
post-cutover verifier as a baseline.

For basic authentication, set `ELASTIC_USERNAME` and `ELASTIC_PASSWORD` instead.
Use `--ca-certs <path>` for a private certificate authority, or `--insecure`
only for a trusted temporary environment with self-signed TLS. Set `--timeout`
to change the per-request timeout. The tools refuse credentials over plain
HTTP unless `--allow-insecure-http-auth` is explicitly supplied; use that only
for an isolated local test. Do not commit the report because it contains cluster
topology and configuration.

The command exits non-zero when the cluster:

- is not running Elasticsearch `8.19.11`;
- has red or unknown health;
- reports a critical migration deprecation;
- has pending system feature migrations;
- has a closed Howler index that backs a configured collection;
- in `--baseline-capture` mode, contains any closed Howler-prefixed index;
- in `--baseline-capture` mode, has incomplete primary-shard statistics or a Howler global checkpoint that does not
  equal `max_seq_no`; or
- contains an index created before Elasticsearch 8.0.

The report also inventories each index's UUID, health, open/closed status,
creation version, settings, and alias `is_write_index` values. For each open
Howler-prefixed index it collects primary-shard document counts, `max_seq_no`,
and `global_checkpoint` from `_stats?level=shards`. Both tools require every
primary ID from `0` through `index.number_of_shards - 1`. If a primary is
missing, the report leaves the index document count `null` rather than reporting
a partial total. It also records ILM explain state for Howler-prefixed indices;
composable, component,
and legacy templates; ILM policies; ingest pipelines; node settings; snapshot
repositories; remote clusters; and all informational or warning-level
deprecations. Use only a report with `baseline_capture: true` as the pre-upgrade
comparison baseline after quiescing all writes.

If baseline-capture reports incomplete or unsynchronized statistics, keep writers
quiesced, flush the Howler indices, wait for primary checkpoints to catch up, and
rerun. Do not use an unsynchronized report as the cutover baseline.

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
For the coordinated upgrade and post-cutover checks, follow the
[Elasticsearch 9.5.2 cutover runbook](elasticsearch_9_cutover.md).
