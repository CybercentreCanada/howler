# External scripts

## reindex_data.py

Reindex one or more Elasticsearch indexes used by Howler.

### Usage

```bash
# Reindex specific indexes (confirms each one before proceeding)
python reindex_data.py hit user

# Reindex all indexes
python reindex_data.py --all

# Skip confirmation prompts and countdown
python reindex_data.py hit --force

# Print index schema before reindexing
python reindex_data.py hit --verbose
```

### Options

| Argument    | Description                                  |
|-------------|----------------------------------------------|
| `indexes`   | One or more index names to reindex.          |
| `--all`     | Reindex all indexes.                         |
| `--force`   | Skip confirmation prompts and countdown.     |
| `--verbose` | Print the index schema before reindexing.    |

## run_migrations.py

Run Howler datastore migrations explicitly. Datastore construction and API application imports do not run migrations.
Use the exact same API image and configuration as the deployment that owns the data.

### Usage

```bash
# List the migrations without opening Elasticsearch
poetry run howler-migrate --list

# Run every registered migration
poetry run howler-migrate --all

# Run one or more selected migrations
poetry run howler-migrate --migration-id action-owner-id-to-owner
poetry run howler-migrate \
  --migration-id action-owner-id-to-owner \
  --migration-id action-owner-id-legacy-field-cleanup

# Override the Elasticsearch transport timeout before datastore imports
poetry run howler-migrate --all --timeout 3600
# --transport-timeout is an equivalent explicit alias
poetry run howler-migrate --all --transport-timeout 3600
```

There is intentionally no generic `--force` option. Migration records provide the claim protection used by concurrent
operators. An applied migration is skipped; an active claim is polled; and a claim older than
`HWL_MIGRATION_STALE_CLAIM_TIMEOUT` is replaced with an optimistic-concurrency check.

### Configuration

The command uses the normal Howler configuration files, index prefix, Elasticsearch credentials, and certificate
handling. The command must receive the same values as the API, including:

- `HWL_CONF_FOLDER` or the mounted `/etc/howler/conf/config.yml` and `mappings.yml` files.
- `HWL_DATASTORE_INDEX_PREFIX`, which must match the API deployment exactly.
- `HWL_DATASTORE_TRANSPORT_TIMEOUT`, or the command-line `--timeout` override.
- The configured host credential variables, such as `<HOST>_HOST_APIKEY_ID` and `<HOST>_HOST_APIKEY_SECRET`, or the
  corresponding username/password variables.
- `HWL_CERT_DIRECTORY` and the certificate files required by the configured Elasticsearch hosts.
- `HWL_MIGRATION_STALE_CLAIM_TIMEOUT`, `HWL_MIGRATION_WAIT_TIMEOUT`, and `HWL_MIGRATION_POLL_INTERVAL` when the
  deployment needs values other than the defaults.
- `HWL_DATASTORE_TASK_POLL_TIMEOUT` and `HWL_DATASTORE_TASK_POLL_INTERVAL` when asynchronous Elasticsearch tasks
  need different polling bounds.

The process exits with status `0` on success, `1` for a migration, Elasticsearch, or datastore-close failure, and `2`
for invalid command-line arguments or unknown migration IDs. A failed migration claim is removed only when its claim
ID still belongs to the failing process. Elasticsearch task timeouts, task errors, non-empty `failures`, and exhausted
version-conflict retries fail the command and are not recorded as applied.

The command can also be invoked in a container with:

```bash
python -m howler.external.run_migrations --all
```
