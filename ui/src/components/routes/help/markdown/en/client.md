# Howler Client Documentation

This documentation will outline how to interact with the howler API using the howler client in both Java and python development environments. We will outline the basic process of creating a new hit in each environment as well as searching howler for hits matching your query.

## Getting started

### Installation

In order to use the howler client, you need to list it as a dependency in your project.

#### **Python**

Simply install through pip:

```bash
pip install howler-client
```

You can also add it to your requirements.txt, or whatever dependency management system you use.

### Authentication

As outlined in the [Authentication Documentation](/help/auth), there's a number of ways users can choose to authenticate. In order to interface with the howler client, however, the suggested flow is to use an API key. So before we start, let's generate a key.

1. Open the Howler UI you'd like to interface with.
2. Log in, then click your profile in the top right.
3. Under user menu, click Settings.
4. Under User Security, press the (+) icon on the API Keys row.
5. Name your key, and give it the requisite permissions.
6. Press Create, and copy the supplied string somewhere safe. **You will not see this string again.**

This API Key will be supplied to your code later on.

## Python Client

In order to connect with howler using the python client, there is a fairly simple process to follow:

```python
from howler_client import get_client

USERNAME = 'user' # Obtain this from the user settings page of the Howler UI
APIKEY = 'apikey_name:apikey_data'

apikey = (USERNAME, APIKEY)

howler = get_client("$CURRENT_URL", apikey=apikey)
```

```alert
You can skip generating an API Key and providing it if you're executing this code within HOGWARTS (i.e., on jupyterhub or airflow). OBO will handle authentication for you!
```

That's it! You can now use the `howler` object to interact with the server. So what does that actually look like?

### Creating hits in Python

For the python client, you can create hits using either the `howler.hit.create` or `howler.hit.create_from_map` functions.

#### `create`

This function takes in a single argument - either a single hit, or a list of them, conforming to the [Howler Schema](/help/hit?tab=schema). Here is a simple example:

```python
# Some bogus data in the Howler Schema format
example_hit = {
  "howler": {
    "analytic": "example",
    "score": 10.0
  },
  "event": {
    "reason": "Example hit"
  }
}

howler.hit.create(example_hit)
```

You can also ingest data in a flat format:

```python
example_hit = {
  "howler.analytic": "example",
  "howler.score": 10.0,
  "event.reason": "Example hit"
}

howler.hit.create(example_hit)
```

#### `create_from_map`

This function takes in three arguments:

- `tool name`: The name of the analytic creating the hit
- `map`: A mapping between the raw data you have and the howler schema
  - The format is a dictionary where the keys are the flattened path of the raw data, and the values are a list of flattened paths for Howler's fields where the data will be copied into.
- `documents`: The raw data you want to add to howler

Here is a simple example:

```python
# The mapping from our data to howler's schema
hwl_map = {
  "file.sha256": ["file.hash.sha256", "howler.hash"],
  "file.name": ["file.name"],
  "src_ip": ["source.ip", "related.ip"],
  "dest_ip": ["destination.ip", "related.ip"],
  "time.created": ["event.start"],
}

# Some bogus data in a custom format we want to add to howler
example_hit = {
  "src_ip": "0.0.0.0",
  "dest_ip": "8.8.8.8",
  "file": {
    "name": "hello.exe",
    "sha256": sha256(str("hello.exe").encode()).hexdigest()
  },
  "time": {
    "created": datetime.now().isoformat()
  },
}

# Note that the third argument is of type list!
howler.hit.create_from_map("example_ingestor", hwl_map, [example_hit])
```

### Querying Hits

Querying hits using the howler python client is done using the `howler.search.hit` function. It has a number of required and optional arguments:

- Required:
  - `query`: lucene query (string)
- Optional:
  - `filters`: Additional lucene queries used to filter the data (list of strings)
  - `fl`: List of fields to return (comma separated string of fields)
  - `offset`: Offset at which the query items should start (integer)
  - `rows`: Number of records to return (integer)
  - `sort`: Field used for sorting with direction (string: ex. 'id desc')
  - `timeout`: Max amount of milliseconds the query will run (integer)
  - `use_archive`: Also query the archive
  - `track_total_hits`: Number of hits to track (default: 10k)

Here are some example queries:

```python
# Search for all hits created by assemblyline, show the first 50, and return only their ids
howler.search.hit("howler.analytic:assemblyline", fl="howler.id", rows=50)

# Search for all resolved hits created in the last five days, returning their id and the analytic that created them. Show only ten, offset by 40
howler.search.hit("howler.status:resolved", filters=['event.created:[now-5d TO now]'] fl="howler.id,howler.analytic", rows=10, offset=40)

# Search for all hits, timeout if the query takes more than 100ms
howler.search.hit("howler.id:*", track_total_hits=100000000, timeout=100, use_archive=True)
```

### Updating Hits

In order to update hits, there are a number of supported functions:

- `howler.hit.update(...)`
- `howler.hit.update_by_query(...)`
- `howler.hit.overwrite(...)`

#### `update()`

If you want to update a hit in a transactional way, you can use the following code:

```python
hit_to_update = client.search.hit("howler.id:*", rows=1, sort="event.created desc")["items"][0]

result = client.hit.update(hit_to_update["howler"]["id"], [(UPDATE_SET, "howler.score", hit_to_update["howler"]["score"] + 100)])
```

The following operations can be run to update a hit.

**List Operations:**

- `UPDATE_APPEND`: Used to append a value to a given list
- `UPDATE_APPEND_IF_MISSING`: Used to append a value to a given list if the value isn't already in the list
- `UPDATE_REMOVE`: Will remove a given value from a list

**Numeric Operations:**

- `UPDATE_DEC`: Decrement a numeric value by the specified amount
- `UPDATE_INC`: Increment a numeric value by the specified amount
- `UPDATE_MAX`: Will set a numeric value to the maximum of the existing value and the specified value
- `UPDATE_MIN`: Will set a numeric value to the minimum of the existing value and the specified value

**Multipurpose Operations:**

- `UPDATE_SET`: Set a field's value to the given value
- `UPDATE_DELETE`: Will delete a given field's value

#### `update_by_query()`

This function allows you to update a large number of hits by a query:

```python
client.hit.update_by_query(f'howler.analytic:"Example Alert"', [(UPDATE_INC, "howler.score", 100)])
```

The same operations as in `update()` can be used.

### `overwrite()`

This function allows you to directly overwrite a hit with a partial hit object. This is the most easy to use, but loses some of the validation and additional processing of the update functions.

```python
hit_to_update = client.search.hit("howler.id:*", rows=1, sort="event.created desc")["items"][0]

result = client.hit.overwrite(hit_to_update["howler"]["id"], {"source.ip": "127.0.0.1", "destination.ip": "8.8.8.8"})
```
