# Howler Client Library

The Howler client library facilitates issuing requests to Howler.

## Map raw table rows to hit records

`RowMapping` applies a version-1 YAML mapping to raw table rows without
contacting Howler, persisting records, or generating server-owned IDs. Mapping
is lazy: each input row is consumed only when requested, and each row yields
either `(hit, None)` or `(None, MappingError)` in source order. A row error is
returned rather than raised, so later rows continue. Configuration errors raise
as soon as `map_rows` is called; exceptions from the upstream iterator propagate
unchanged. No Howler connection is needed.

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

A mapping document contains `version: 1`, an optional default `on_null`
(`error` or `omit`, default `error`), and `mappings` from dotted Howler field
names to one expression each:

- `column` (optionally with a `path` of keys/indexes into nested values; a
  missing nested key is treated as null),
- `concat` of two or more list-valued columns, or
- a constant `value`.

Expressions may set their own `on_null` and a list of `transforms` (`string`,
`integer`, `number`, `boolean`, `trim`, `lower`, `upper`, `list`, `json`, or
`{op: timestamp, assume_timezone: UTC}`). Mappings are parsed with
`yaml.safe_load`, so quote constants such as `"yes"` or `"2026-01-01"` that must
stay strings.

You can also construct a `RowMapping` from an already loaded mapping document or
use `RowMapping.from_yaml(text)`. `map_rows(rows, mapping)` accepts a mapping
document, a `RowMapping`, or a YAML **file path**; pass YAML text through
`from_yaml` to keep that distinction explicit. Optionally pass Howler field
metadata (for example the result of `client.search.fields.hit()` or the MCP
`get_hit_fields` tool) as `fields=...` to check that targets exist, are not
deprecated, and receive values with the right list shape and basic type. Without
it, backend field validation is left to Howler (see `client.v2.ingest.validate`).
See [`examples/row_mapping/example_mapping.yaml`](examples/row_mapping/example_mapping.yaml)
for a sanitized AAD-shaped example. This feature only transforms rows into
dictionaries; persistence or ingestion is outside its scope.

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
