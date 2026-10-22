# Howler Client Library

`howler-client` is the Python client for the Howler API. Use it to:

- create, search, update, and delete hits
- manage comments, actions, users, and cases
- turn raw table rows into hit records offline, before you ingest them

It handles authentication, request formatting, retries, and response parsing.

- **Package:** [howler-client on PyPI](https://pypi.org/project/howler-client/)
- **User guide:** [Howler client documentation](https://cybercentrecanada.github.io/howler/ingestion/client/)
- **Contributor guide:** [Client development](https://cybercentrecanada.github.io/howler/developer/client/)

## Installation

The client requires Python 3.10 or newer.

```bash
pip install howler-client
```

## Connecting to Howler

`get_client()` returns a `Client` connected to a Howler server. It checks that the server supports the v1 API when
it connects, so the server must be reachable.

```python
from howler_client import get_client

# API key (recommended): create one in the Howler UI under Settings -> User Security -> API Keys
client = get_client("https://howler.example.com", apikey=("my_username", "my_key_name:my_key_secret"))

# JWT, for example one obtained through an OAuth flow
client = get_client("https://howler.example.com", auth="eyJhbGciOi...")

# Username and password (only if the server allows internal authentication)
client = get_client("https://howler.example.com", auth=("my_username", "my_password"))
```

Other useful `get_client()` options:

- `verify`: whether to verify TLS certificates.
- `cert`: a client certificate.
- `timeout`: the request timeout.
- `retries`: how many times to retry a request. The default `0` retries forever.
- `throw_on_bad_request` and `throw_on_max_retries`: whether to raise `ClientError` on failures.
- `authenticate`: a callback that returns a bearer token.

## What the client covers

| Attribute          | Purpose                                                                                                                                                                                                 |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `client.hit`       | Create hits (`create`), fetch one by ID (`client.hit(hit_id)`), `overwrite`, `update`, `update_by_query`, `delete`, `generate_hash`. Comments are under `client.hit.comment` (`add`, `edit`, `delete`). |
| `client.search`    | Lucene search over hits (`hit`) and actions (`action`), plus `facet`, `fields`, `grouped`, `histogram`, `stats`, and `stream` helpers, each with a `.hit(...)` method.                                  |
| `client.action`    | List, create, and execute saved actions.                                                                                                                                                                |
| `client.user`      | Add, delete, list, and update users; `whoami`.                                                                                                                                                          |
| `client.help`      | Server metadata such as `classification_definition()`.                                                                                                                                                  |
| `client.v2.ingest` | v2 ingestion for the `hit` and `event` indexes: `create`, `validate` (check records without storing them), `overwrite`, `update_by_query`, `delete`.                                                    |
| `client.v2.search` | Search across several indexes at once (`client.v2.search("hit,event", query)`), plus `count`, `facet`, and `explain`.                                                                                   |
| `client.v2.case`   | Fetch, create, update, hide, and delete cases; manage case items and correlation rules.                                                                                                                 |
| `client.mapping`   | `map_rows(...)`, the same as the top-level `howler_client.map_rows`. See below.                                                                                                                         |

For example:

```python
results = client.search.hit("howler.status:open", rows=10, sort="event.created desc")
for hit in results["items"]:
    print(hit["howler"]["id"], hit["howler"]["analytic"])

client.hit.create({"howler": {"analytic": "My Analytic", "score": 0.5}})
```

Failed requests raise `howler_client.common.utils.ClientError`. It has `status_code` and `api_response` attributes. See
the [user guide](https://cybercentrecanada.github.io/howler/ingestion/client/) for more examples.

## Mapping raw table rows to hit records

`RowMapping` turns raw rows into Howler hit dictionaries using a YAML mapping file. It runs entirely offline:

- It does not need a Howler connection.
- It never stores or ingests records.
- It never sets server-owned IDs such as `howler.id`.

To store the results, pass them to `client.hit.create` or `client.v2.ingest.create`.

```python
from howler_client import RowMapping, map_rows

mapping = RowMapping.from_file("mapping.yaml")

for hit, error in map_rows(query_result_rows, mapping):
    if error is not None:
        handle_mapping_error(error)  # a MappingError naming the row number and target field
        continue
    process_hit(hit)
```

How `map_rows` behaves:

- It is lazy: it reads each source row only when you ask for the next result.
- For each row, in order, it yields either `(hit, None)` or `(None, MappingError)`.
- A bad row produces an error result, and the following rows are still processed.
- A bad mapping raises as soon as you call `map_rows`, before any row is read.
- Exceptions raised by your row iterator are passed through unchanged.

To map a single row, `mapping.map_row(row)` returns the hit or raises `MappingError`.

### Mapping file format

```yaml
version: 1
on_null: error # default for every target: error (default) or omit
mappings:
  howler.analytic:
    value: Directory User Inventory # constant
  user.id:
    column: user_identifier # copy a column
  user.name:
    column: account_name
    transforms: [trim, lower]
  user.email:
    column: primary_email
    on_null: omit # leave the field out when the value is null
  organization.name:
    column: profile
    path: [organization, name] # read a value nested inside the column
  user.roles:
    concat: [directory_role_names, elevated_role_names] # join list columns
```

Each key under `mappings` is a dotted Howler field name. Each target needs exactly one source:

| Expression                       | Result                                                                                                                     |
| -------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `column: name`                   | The value of that column. A missing column is a row error.                                                                 |
| `column` + `path: [key, 0, ...]` | A value nested inside the column, found by dictionary keys and list indexes. A missing nested key or index counts as null. |
| `concat: [a, b, ...]`            | Two or more list columns joined into one list.                                                                             |
| `value: ...`                     | A constant, computed once when the mapping is loaded.                                                                      |

A target can also set:

- `on_null`, which overrides the document-wide setting. With `error`, a null value fails the row. With `omit`, the
  field is left out.
- `transforms`, which are applied in order:

| Transform                      | Effect                                                                                            |
| ------------------------------ | ------------------------------------------------------------------------------------------------- |
| `string`                       | Converts a scalar to a string. Use `json` for objects and lists.                                  |
| `integer`, `number`, `boolean` | Strict conversions. `boolean` accepts only booleans or `"true"`/`"false"`.                        |
| `trim`, `lower`, `upper`       | String clean-up.                                                                                  |
| `list`                         | Wraps a scalar in a list.                                                                         |
| `json`                         | Converts the value to compact JSON text with sorted keys.                                         |
| `{op: timestamp}`              | Converts an ISO-8601 string to UTC. Add `assume_timezone: UTC` to accept values with no timezone. |

Mapping files are parsed with `yaml.safe_load`. Quote constants that must stay strings, such as `"yes"`, `"off"`, or
`"2026-01-01"`.

Mapping documents must contain JSON-compatible values: object keys must be strings, and YAML-only values such as dates,
sets, and binary data (as well as non-finite numbers and cyclic structures) are rejected. The client validates mappings
offline with its bundled [Draft 2020-12 schema](howler_client/schemas/row_mapping_v1.schema.json), which is included in
the wheel and source distribution.

You can also build a mapping from YAML text with `RowMapping.from_yaml(text)`, or from an already-loaded dictionary
with `RowMapping(document)`. `map_rows` accepts a `RowMapping`, a dictionary, or a path to a YAML file. To use YAML
text, go through `from_yaml` so it isn't mistaken for a path.
[`examples/row_mapping/example_mapping.yaml`](examples/row_mapping/example_mapping.yaml) is a complete example.

### Checking targets against Howler's fields

You can pass Howler's field metadata to check targets before you ingest anything. Use the output of
`client.search.fields.hit()`:

```python
fields = client.search.fields.hit()
mapping = RowMapping.from_file("mapping.yaml", fields=fields)
```

With field metadata, `RowMapping` checks that:

- every target exists and is not deprecated
- every `concat` target is a list field

`RowMapping` does not validate mapped values against target field types or list shape. Validate records with
`client.v2.ingest.validate("hit", hits)` or let Howler validate them during ingestion.

## Development

The client lives in the `client/` folder of the Howler monorepo. It uses its own [Poetry](https://python-poetry.org/)
environment, so run every command below from `client/`.

### Setup

```bash
cd client
poetry install --with dev,test,types
```

The repository's pre-commit hooks run Ruff and check commit messages. From the repository root, install them with
`pre-commit install`.

### Code quality

These are the checks CI runs:

```bash
poetry run ruff format howler_client --diff
poetry run ruff check howler_client --output-format=github
poetry run type_check # mypy over howler_client
```

### Unit tests

Unit tests in `test/unit/` run offline: they need no Howler server, Elasticsearch, or Redis.

```bash
poetry run test test/unit                                   # all unit tests
poetry run test test/unit/test_row_mapping.py -k timestamp  # focused run; arguments are passed to pytest
```

### Integration tests

Integration tests in `test/integration/` call a running Howler API at `http://localhost:5000`. Set `UI_HOST` to use a
different address. The API needs Elasticsearch, Redis, and seeded test data. To set this up the same way CI does,
starting from the repository root:

```bash
# 1. Prepare the API configuration
sudo mkdir -p /etc/howler/conf /etc/howler/lookups /var/log/howler
sudo chown -R "$USER" /etc/howler /var/log/howler
cp api/build_scripts/classification.yml /etc/howler/conf/classification.yml
cp api/build_scripts/mappings.yml /etc/howler/conf/mappings.yml
cp client/test/config/config.ci.yml /etc/howler/conf/config.yml

# 2. Start Elasticsearch and Redis
docker compose -f client/test/docker-compose.yml up -d

# 3. Install and start the API (leave it running in its own terminal)
cd api
poetry install --with test,dev
poetry run mitre /etc/howler/lookups
poetry run sigma
TESTING=true poetry run flask --app howler.app run --no-reload

# 4. In another terminal, seed users and random data (this creates the admin API key the tests use)
cd api
poetry run python -m howler.odm.random_data

# 5. Run the full client test suite with coverage
cd ../client
poetry run test
```

`poetry run test` with no arguments runs everything under `test/` with branch coverage. Integration tests need the
running services. To run only part of the suite, pass paths or pytest options.

### Releases

Releases are automated with Release Please using Conventional Commits. Use the `client` scope, for example
`feat(client): ...`. `CHANGELOG.md` is generated, so don't edit it by hand.
