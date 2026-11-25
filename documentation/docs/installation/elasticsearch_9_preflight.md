# Elasticsearch 9 preflight

Howler must be running Elasticsearch and Kibana `8.19.11` before upgrading to
`9.5.2` (with `elasticsearch-py` `9.5.0` and Pydantic v2; ES `9.5.2` includes
Lucene `10.5.1`). Run this preflight against a rehearsal cluster and each
production cluster before scheduling cutover.

## Run the read-only report

The tool uses raw REST (`GET` only) with plain `application/json` headers because
the pinned 9.x client negotiates REST compatibility version 9, which `8.19`
rejects. Credentials are never written to the report or logs.

```bash
cd api
export ELASTICSEARCH_URL="https://elasticsearch.example:9200"
export ELASTIC_API_KEY="<api-key>"
poetry run python -m howler.external.elasticsearch_preflight \
  --output elasticsearch-9-preflight.json
```

Use `ELASTIC_USERNAME` and `ELASTIC_PASSWORD` for basic auth, `--ca-certs` for a
private CA, `--insecure` only in trusted test environments, and `--timeout` to
override the request timeout. Credentials over plain HTTP are refused unless
`--allow-insecure-http-auth` is passed (isolated local testing only).

During live traffic, run without `--baseline-capture` so active primary
checkpoint lag reports as a warning. Only after writers are quiesced and
Howler indices are flushed, capture the cutover baseline:

```bash
poetry run python -m howler.external.elasticsearch_preflight \
  --baseline-capture --output elasticsearch-9-preflight-baseline.json
```

Only a report with `baseline_capture: true` and `checks.ready: true` is
accepted by the post-cutover verifier as `--baseline`. If `--baseline-capture`
reports incomplete or unsynced statistics, keep writers quiesced, flush the
Howler indices, wait for global checkpoints to catch up, and rerun.

The command exits non-zero when the cluster:

- is not running Elasticsearch `8.19.11`;
- has red or unknown health;
- reports a critical migration deprecation or pending system feature migration;
- contains an index created before Elasticsearch `8.0` (or unknown version);
- has a closed Howler index backing a configured collection; or
- in `--baseline-capture` mode, has any closed Howler-prefixed index, missing
  primary shard IDs (`0..number_of_shards-1`), or `global_checkpoint != max_seq_no`.

## Operational review

1. Enable deprecation logging/indexing in the Kibana Upgrade Assistant under
   representative traffic and resolve all critical items from the Assistant,
   `GET /_migration/deprecations`, and the preflight report.
2. Run required system feature migrations until `GET /_migration/system_features`
   returns `NO_MIGRATION_NEEDED`.
3. Reindex, delete, or archive pre-8.0 indices, and verify aliases, ILM policies,
   templates, pipelines, security realms, snapshot repositories, and remote
   clusters.
4. Retain the clean report in restricted change records (never commit it) and
   follow the [Elasticsearch 9.5.2 cutover runbook](elasticsearch_9_cutover.md).
