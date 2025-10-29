<!-- docs/ingestion/client.md -->
# Howler Client Documentation

The Howler Python client (`howler-client`) is a library that provides a simple and intuitive interface for
programmatically interacting with the Howler API. It allows developers to:

- Create and ingest hits from various data sources
- Search and query hits with Lucene syntax
- Update, modify, and delete hits
- Manage hit comments and metadata
- Integrate Howler into automated workflows and pipelines

The client handles authentication, request formatting, and response parsing, making it easy to build tools and
integrations with Howler.

The package is published on [PyPI](https://pypi.org/project/howler-client/) and the source code is located in the
`client/` folder of the [Howler monorepo](https://github.com/CybercentreCanada/howler).

## Installation

The Howler client requires Python 3.9 or higher. Install it using pip:

```bash
pip install howler-client
```

## Authentication & Connection

### Generating an API Key

To authenticate with the Howler API, you'll need to generate an API key:

1. Open the Howler UI and log in
2. Click your profile icon in the top right corner
3. Select **Settings** from the user menu
4. Under **User Security**, click the **(+)** icon next to API Keys
5. Name your key and assign the appropriate permissions
6. Click **Create** and copy the generated key

**Important:** Store this key securely - you won't be able to see it again!

### Connecting to Howler

The client supports multiple authentication methods:

#### Using an API Key (Recommended)

Once you have your API key, connect to Howler using the `get_client()` function:

```python
from howler_client import get_client

# Your credentials
USERNAME = 'your_username'  # From the Howler UI user settings
APIKEY = 'apikey_name:apikey_data'  # The key you generated

# Create the client
client = get_client("https://your-howler-instance.com", apikey=(USERNAME, APIKEY))
```

#### Using a JWT Token

If you have a JWT token (e.g., from an OAuth flow), you can authenticate by passing it to the `auth` parameter:

```python
from howler_client import get_client

# Your JWT token
JWT_TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'  # Your JWT token

# Create the client
client = get_client("https://your-howler-instance.com", auth=JWT_TOKEN)
```

Now you can use the `client` object to interact with Howler!

## Creating Hits

Creating hits is the primary use case for the Howler client. The client provides two main methods for ingesting data:
`client.hit.create()` for data already in Howler's schema format, and `client.hit.create_from_map()` for custom
data that needs to be mapped to Howler's schema.

### Using `client.hit.create()`

The `create()` method accepts hit data in either nested or flat format. The data must conform to the Howler schema.

#### Nested Format

This is the recommended format as it closely matches the Howler data model:

```python
from hashlib import sha256

# Create a hit with nested structure
hit = {
    "howler": {
        "analytic": "A test for creating a hit",
        "score": 0.8,
        "hash": sha256(b"unique_identifier").hexdigest(),
        "outline": {
            "threat": "10.0.0.1",
            "target": "asdf123",
            "indicators": ["me.ps1"],
            "summary": "This is a summary",
        },
    },
}

# Create the hit
response = client.hit.create(hit)

# Check the response
print(f"Valid hits: {len(response['valid'])}")
print(f"Invalid hits: {len(response['invalid'])}")
```

#### Flat Format

You can also provide hit data in a flat, dot-notation format:

```python
from hashlib import sha256

# Create a hit with flat structure
hit = {
    "howler.analytic": "Test Dupes",
    "howler.score": 0.0,
    "howler.hash": sha256(b"unique_identifier").hexdigest(),
}

# Create the hit
response = client.hit.create(hit)
```

#### Batch Creation

You can create multiple hits at once by passing a list:

```python
hits = [
    {
        "howler.analytic": "Batch Test",
        "howler.score": 0.5,
        "howler.outline.threat": "192.168.1.1",
        "howler.outline.target": "server01",
        "howler.outline.indicators": ["malware.exe"],
        "howler.outline.summary": "First hit",
    },
    {
        "howler.analytic": "Batch Test",
        "howler.score": 0.8,
        "howler.outline.threat": "192.168.1.2",
        "howler.outline.target": "server02",
        "howler.outline.indicators": ["suspicious.dll"],
        "howler.outline.summary": "Second hit",
    },
]

response = client.hit.create(hits)
```

#### Response Structure

The `create()` method returns a dictionary with two keys:

- `valid`: List of successfully created hits with their IDs
- `invalid`: List of hits that failed validation with error messages

```python
response = client.hit.create(hits)

# Process valid hits
for hit in response['valid']:
    print(f"Created hit with ID: {hit['id']}")

# Handle invalid hits
for result in response['invalid']:
    print(f"Failed to create hit: {result['error']}")
    print(f"Hit Data: {json.dumps(result['hit'], indent=2)}")
```

### Using `client.hit.create_from_map()`

When you have data in a custom format, `create_from_map()` allows you to define a mapping from your data structure to
Howler's schema. This is particularly useful for integrating with external systems or ingesting data from various sources.

#### Basic Example

```python
import datetime
from hashlib import sha256

# Define the mapping from your data format to Howler's schema
# Keys are your field paths, values are lists of Howler field paths
mapping = {
    "file.sha256": ["file.hash.sha256", "howler.hash"],
    "file.name": ["file.name"],
    "src_ip": ["source.ip", "related.ip"],
    "dest_ip": ["destination.ip", "related.ip"],
    "time.created": ["event.start"],
    "time.completed": ["event.end"],
}

# Your custom data
hits = [
    {
        "src_ip": "43.228.141.216",
        "dest_ip": "31.46.39.115",
        "file": {
            "name": "cool_file.exe",
            "sha256": sha256(b"cool_file.exe").hexdigest(),
        },
        "time": {
            "created": datetime.datetime(2020, 5, 17).isoformat() + "Z",
            "completed": datetime.datetime(2020, 5, 18).isoformat() + "Z",
        },
    },
]

# Create hits using the mapping
response = client.hit.create_from_map("my_analytic_tool", mapping, hits)

# Check results
for hit in response:
    if hit["error"]:
        print(f"Error: {hit['error']}")
    else:
        print(f"Created hit: {hit['id']}")
        if hit["warn"]:
            print(f"Warnings: {hit['warn']}")
```

#### Response Structure

The `create_from_map()` method returns a list of dictionaries, one for each input hit:

- `id`: The ID of the created hit (if successful)
- `error`: Error message if creation failed (None if successful)
- `warn`: List of warning messages (e.g., deprecated fields used)

### Handling Validation Errors

When creating hits, validation errors may occur. The client provides detailed error messages:

```python
from howler_client.common.utils import ClientError

try:
    hits = [
        {
            "howler.analytic": "Test",
            "howler.score": 0.8,
            # Missing required fields will cause validation to fail
        },
        {
            "howler.analytic": "Test",
            # Missing score field
            "howler.outline.threat": "10.0.0.1",
        },
    ]

    response = client.hit.create(hits)
except ClientError as e:
    print(f"Error: {e}")
    print(f"Valid hits: {len(e.api_response['valid'])}")
    print(f"Invalid hits: {len(e.api_response['invalid'])}")

    for invalid_hit in e.api_response['invalid']:
        print(f"Validation error: {invalid_hit['error']}")
```

### Duplicate Detection

Howler automatically detects duplicate hits based on the `howler.hash` field. If you attempt to create a hit with the
same hash as an existing hit, it will be skipped:

```python
from hashlib import sha256

# Create a unique hash
unique_hash = sha256(b"unique_identifier").hexdigest()

# First creation succeeds
hit1 = {
    "howler.analytic": "Test Dupes",
    "howler.score": 0,
    "howler.hash": unique_hash,
}
client.hit.create(hit1)

# Second creation with same hash is skipped
hit2 = {
    "howler.analytic": "Test Dupes",
    "howler.score": 0,
    "howler.hash": unique_hash,  # Same hash!
}
response = client.hit.create(hit2)
# This hit will not be created as a duplicate
```

## Basic Hit Operations

### Searching for Hits

The `client.search.hit()` method allows you to query hits using Lucene syntax:

```python
# Search for all hits
results = client.search.hit("howler.id:*")

print(f"Total hits: {results['total']}")
print(f"Returned: {len(results['items'])}")

# Access individual hits
for hit in results['items']:
    print(f"Hit ID: {hit['howler']['id']}")
    print(f"Analytic: {hit['howler']['analytic']}")
    print(f"Score: {hit['howler']['score']}")
```

#### Query Parameters

The `search.hit()` method supports several parameters:

```python
# Search with specific parameters
results = client.search.hit(
    "howler.analytic:my_analytic",  # Lucene query
    rows=50,                         # Number of results to return (default: 25)
    offset=0,                        # Starting offset (default: 0)
    sort="event.created desc",       # Sort field and direction
    fl="howler.id,howler.score",    # Fields to return (comma-separated)
    filters=["event.created:[now-7d TO now]"],  # Additional filters
)
```

### Updating Hits

The client provides multiple methods for updating hits, with `overwrite()` being the simplest for most use cases.

#### Overwriting Hit Data (Recommended)

The `client.hit.overwrite()` method is the easiest way to update a hit. Simply provide a partial hit object with the
fields you want to change:

```python
# Get a hit to update
hit = client.search.hit("howler.id:*", rows=1, sort="event.created desc")["items"][0]
hit_id = hit["howler"]["id"]

# Overwrite specific fields
updated_hit = client.hit.overwrite(
    hit_id,
    {
        "source.ip": "127.0.0.1",
        "destination.ip": "8.8.8.8",
        "howler.score": 0.95,
        "howler.status": "resolved",
    }
)

print(f"Updated hit: {updated_hit['howler']['id']}")
```

The overwrite method accepts both nested and flat formats:

```python
# Nested format
client.hit.overwrite(
    hit_id,
    {
        "howler": {
            "score": 0.9,
            "status": "open"
        },
        "source": {
            "ip": "10.0.0.1"
        }
    }
)

# Flat format (dot notation)
client.hit.overwrite(
    hit_id,
    {
        "howler.score": 0.9,
        "howler.status": "open",
        "source.ip": "10.0.0.1"
    }
)
```

#### Transactional Updates (For Bulk Operations)

For more complex scenarios like bulk updates or atomic operations (increment, append, etc.), use `client.hit.update()`:

```python
from howler_client.module.hit import UPDATE_SET, UPDATE_INC

# Get a hit to update
hit = client.search.hit("howler.id:*", rows=1)["items"][0]
hit_id = hit["howler"]["id"]

# Update the hit with operations
updated_hit = client.hit.update(
    hit_id,
    [
        (UPDATE_SET, "howler.score", 0.95),
        (UPDATE_INC, "howler.escalation", 1),
    ]
)

print(f"Updated score: {updated_hit['howler']['score']}")
```

**Available Update Operations:**

**List Operations:**

```python
from howler_client.module.hit import UPDATE_APPEND, UPDATE_APPEND_IF_MISSING, UPDATE_REMOVE

# Append a value to a list
(UPDATE_APPEND, "howler.outline.indicators", "new_indicator.exe")

# Append only if not already present
(UPDATE_APPEND_IF_MISSING, "related.ip", "192.168.1.1")

# Remove a value from a list
(UPDATE_REMOVE, "howler.outline.indicators", "false_positive.exe")
```

**Numeric Operations:**

```python
from howler_client.module.hit import UPDATE_INC, UPDATE_DEC, UPDATE_MAX, UPDATE_MIN

# Increment by amount
(UPDATE_INC, "howler.score", 10)

# Decrement by amount
(UPDATE_DEC, "howler.score", 5)

# Set to maximum of current and specified value
(UPDATE_MAX, "howler.score", 50)

# Set to minimum of current and specified value
(UPDATE_MIN, "howler.score", 20)
```

**General Operations:**

```python
from howler_client.module.hit import UPDATE_SET, UPDATE_DELETE

# Set a field to a specific value
(UPDATE_SET, "howler.status", "resolved")

# Delete a field
(UPDATE_DELETE, "custom_field", None)
```

#### Bulk Update by Query

Use `client.hit.update_by_query()` to update multiple hits matching a query:

```python
from howler_client.module.hit import UPDATE_INC

# Increment score for all hits from a specific analytic
client.hit.update_by_query(
    'howler.analytic:"my_analytic"',
    [
        (UPDATE_INC, "howler.score", 100),
    ]
)

# Note: This operation is asynchronous and may take time to complete
```

### Deleting Hits

Delete one or more hits by their IDs:

```python
# Delete a single hit
client.hit.delete(["hit_id_1"])

# Delete multiple hits
client.hit.delete(["hit_id_1", "hit_id_2", "hit_id_3"])

# Example: Delete all hits from a search
results = client.search.hit("howler.analytic:test_analytic")
hit_ids = [hit["howler"]["id"] for hit in results["items"]]
client.hit.delete(hit_ids)
```
