# Howler Client Library

The Howler client library facilitates issuing requests to Howler.

## Map raw table rows to hit records

`howler_client.mapping` can apply a reviewed, version-1 YAML mapping to raw table
rows without contacting Howler, persisting records, or generating server-owned
IDs. Both mapping APIs are generators: each input row is consumed only when
requested, and each row yields either `(hit, None)` or `(None, MappingError)` in
source order. A row error is returned rather than raised, so later rows continue.
Configuration errors raise before the source is consumed; exceptions from the
upstream iterator propagate unchanged.

```python
from collections.abc import Iterable, Mapping
from typing import Any

from howler_client import RowMapping, map_rows

mapping = RowMapping.from_file("mapping.yaml")
raw_rows: Iterable[Mapping[str, Any]] = query_result_rows

for hit, error in map_rows(raw_rows, mapping):
    if error is not None:
        handle_mapping_error(error)
        continue
    if hit is not None:
        process_hit(hit)
```

You can also construct a `RowMapping` from an already loaded mapping document or
use `RowMapping.from_yaml(text)`. The top-level `map_rows(rows, mapping)` accepts
a mapping document, a `RowMapping`, or a YAML **file path**; pass YAML text through
`from_yaml` to keep that distinction explicit. An optional saved MCP fields
snapshot may be supplied to `RowMapping` or via `fields_snapshot=...` to check the
endpoint/fingerprint, field names, list shape, and value types. Without a snapshot,
the library checks mapping structure and rendered row safety only; it does not
claim that targets exist or satisfy backend validation. See
[`examples/row_mapping/example_mapping.yaml`](examples/row_mapping/example_mapping.yaml)
for a sanitized AAD-shaped example with synthetic metadata. This feature only
transforms rows into dictionaries; persistence or ingestion is outside its scope.
Mapped values, mapping constants, and supplied snapshot metadata are limited to
128 nested JSON containers. Unmapped source columns are not traversed or copied.

## Requirements

1. Python 3.10 and up

## Running the Tests

### Prepare the API

```bash
sudo mkdir -p /etc/howler/conf
sudo mkdir -p /var/cache/howler
sudo mkdir -p /var/lib/howler
sudo mkdir -p /var/log/howler

sudo chown -R $USER /etc/howler
sudo chown $USER /var/cache/howler
sudo chown $USER /var/lib/howler
sudo chown $USER /var/log/howler

cd api/dev
docker compose up -d --build

cd ..
poetry install --with dev,test,types
cp test/unit/config.yml /etc/howler/conf/config.yml
cp build_scripts/classification.yml /etc/howler/conf/classification.yml
poetry run server

poetry run python howler/odm/random_data.py
```

### Run the Tests

```bash
cd client

poetry run test
```
