# Detection Engineers

You have just written an analytic that detects some suspicious activity and you would like your Security Operations
Center (SOC) to benefit from it. In Howler, an event of interest is called a hit. The term alert is reserved for
hits that require triage.

To create a new hit, produce a JSON object in which you have normalized the event data to Elastic Common Schema (ECS).
We do this so that triage analysts have a single schema to learn regardless of the source of alerts - this will make
their job much easier.

## Howler-Specific Fields

Next, you need to populate some fields specific to Howler:

### Required Fields

| Field | Description | Notes |
|-------|-------------|-------|
| `howler.analytic` | The actual product doing detection. Some analytics will run many distinct detections. | Must contain only letters and spaces for best practices |

### Auto-Generated Fields

These fields are automatically populated by Howler if not provided:

| Field | Description | Default Behavior |
|-------|-------------|------------------|
| `howler.id` | A unique identifier for the hit | Automatically generated UUID |
| `howler.hash` | A hash used for deduplicating hits | Auto-generated from analytic, detection, and raw data if not provided |
| `event.created` | Timestamp when the event was created | Set to current time if not provided |

### Recommended Fields

While not strictly required, these fields are strongly recommended for effective triage:

| Field | Description | Default | Notes |
|-------|-------------|---------|-------|
| `howler.detection` | A short, unique identifier for the specific detection | None | Should contain only letters and spaces for best practices |
| `howler.outline.threat` | The identifier that best represents the attacker | None | Could be an IP, email address, etc. |
| `howler.outline.target` | The identifier that best represents the victim | None | An IP, domain, email address, etc. |
| `howler.outline.indicators` | A free-form list of indicators of compromise (IoC) | Empty list | Typically IPs, domains, and hashes |
| `howler.outline.summary` | An executive summary explaining the detected activity | None | Describe the event assuming the detection is correct |
| `howler.data` | A list of raw event data before normalization | Empty list | Makes it easier for analysts to investigate outside of Howler |
| `howler.escalation` | The escalation level of the hit | `hit` | Valid values: `miss`, `hit`, `alert`, `evidence` |
| `howler.status` | The current status of the hit | `open` | Valid values: `open`, `in-progress`, `on-hold`, `resolved` |
| `howler.scrutiny` | Level of scrutiny applied to the hit | `unseen` | Valid values: `unseen`, `surveyed`, `scanned`, `inspected`, `investigated` |

### Escalation Levels

Howler uses escalation levels (`howler.escalation`) to categorise hits:

- `miss` - The event is assessed to not be related to detection (false-positive).
- `hit` - (default) The event might not be very reliable without additional context.
- `alert` - The event should be assessed by a triage analyst.
- `evidence` - The event was assessed as related to the detection (true-positive).

You may promote some hits to alert immediately at creation time if the expectation is that all hits will be worth triaging.

Once you have completed the JSON object, use the [Howler client](/howler/developer/client/) to create a new hit.
That hit will be immediately available to triage analysts from the Howler UI.

## Example: Creating a Hit

First, ensure you have the Howler client installed and some way to authenticate with Howler (see
[Authentication & Connection](/howler/developer/client/#authentication--connection) for details).

```python
from howler_client import get_client
from hashlib import sha256

# Connect to Howler
client = get_client("https://your-howler-instance.com", apikey=(USERNAME, APIKEY))

# Create a hit
hit = {
    "howler": {
        "analytic": "Suspicious Login Detector",
        "detection": "Spike in Failed Logins",
        "hash": sha256(b"user123-2024-10-22-failed-logins").hexdigest(),
        "escalation": "alert",  # Promote to alert for triage
        "outline": {
            "threat": "203.0.113.42",
            "target": "user123@example.com",
            "indicators": ["203.0.113.42"],
            "summary": "User account experienced 15 failed login attempts from a single IP in 5 minutes",
        },
        "data": [{"raw_event": "original_log_data_here"}],
    },
    "source": {"ip": "203.0.113.42"},
    "user": {"email": "user123@example.com"},
    "event": {"category": ["authentication"], "outcome": "failure"},
}

response = client.hit.create(hit)
print(f"Created hit: {response['valid'][0]['id']}")
```

For more examples and detailed usage, see the [Client Development Guide](/howler/developer/client/#creating-hits).

## Bundles

A bundle is a logical grouping of hits that should be assessed together. For example, if a series of multiple hits
happen on the same host within a short window of time, a triage analyst should perform a single investigation that
takes them all into account. The Howler UI provides a workflow for intuitively working with these bundles.

Bundles are implemented as special hits that have the `howler.is_bundle` field set to true, and `howler.hits` contains
a list of `howler.id` values from the child hits. This means that analytics can be created to look for related hits
and bundle them together.

??? warning "Creating Bundles"
    **Do not manually set `howler.is_bundle` or `howler.hits` fields when creating hits.** Bundles must be created
    through the bundle API endpoint to ensure proper validation and relationship management. Attempting to create a
    bundle by directly setting these fields may result in inconsistent state or validation errors.

### Creating a Bundle Programmatically

Detection engineers should create bundles through the Howler client's bundle API rather than relying on automatic
creation. This gives you explicit control over which hits are grouped together.

#### Example 1: Create a Bundle with New Hits

This example creates a bundle and its child hits in a single operation:

```python
from howler_client import get_client

client = get_client("https://your-howler-instance.com", apikey=(USERNAME, APIKEY))

# Define the bundle hit
bundle_hit = {
    "howler": {
        "analytic": "Multi-Stage Attack Detector",
        "detection": "Credential Access Chain",
        "outline": {
            "threat": "192.168.1.100",
            "target": "corporate-server-01",
            "summary": "Multiple related suspicious activities detected on the same host",
        },
    },
}

# Define child hits
child_hits = [
    {
        "howler": {
            "analytic": "Multi-Stage Attack Detector",
            "detection": "Unusual Process",
            "outline": {
                "threat": "192.168.1.100",
                "target": "corporate-server-01",
                "indicators": ["suspicious.exe"],
                "summary": "Suspicious process execution detected",
            },
        },
    },
    {
        "howler": {
            "analytic": "Multi-Stage Attack Detector",
            "detection": "Registry Modification",
            "outline": {
                "threat": "192.168.1.100",
                "target": "corporate-server-01",
                "indicators": ["HKLM\\Software\\Persistence"],
                "summary": "Persistence mechanism added to registry",
            },
        },
    },
]

# Create the bundle with its children
response = client.bundle.create(bundle_hit, child_hits)
print(f"Created bundle: {response['howler']['id']}")
print(f"Contains {len(response['howler']['hits'])} child hits")
```

#### Example 2: Create a Bundle from Existing Hits

If you've already created individual hits and want to group them later:

```python
# Search for related hits
related_hits = client.search.hit('source.ip:"192.168.1.100" AND event.created:[now-1h TO now]')

# Extract the hit IDs
hit_ids = [hit["howler"]["id"] for hit in related_hits["items"]]

# Create a bundle from existing hits
bundle_hit = {
    "howler": {
        "analytic": "Correlation Engine",
        "detection": "Related Activity",
        "hits": hit_ids,  # Reference existing hit IDs
        "outline": {
            "threat": "192.168.1.100",
            "summary": f"Bundle of {len(hit_ids)} related events from the same source",
        },
    },
}

response = client.bundle.create(bundle_hit)
print(f"Created bundle with {len(response['howler']['hits'])} existing hits")
```

#### Example 3: Add or Remove Hits from a Bundle

You can modify bundles after creation:

```python
bundle_id = "existing-bundle-id"

# Add hits to an existing bundle
new_hit_ids = ["hit-id-1", "hit-id-2"]
client.bundle.add(bundle_id, new_hit_ids)

# Remove hits from a bundle
client.bundle.remove(bundle_id, ["hit-id-to-remove"])

# Remove all hits from a bundle
client.bundle.remove(bundle_id, "*")
```

### When to Create Bundles

Detection engineers should create bundles when:

- **Multiple detections are part of the same attack chain** - e.g., initial access, persistence, and data exfiltration
  from the same actor
- **Events occur in temporal proximity** - Related events happening on the same host within a short time window
- **Correlated indicators** - Multiple hits sharing common indicators (IPs, file hashes, etc.)
- **Kill chain analysis** - Mapping multiple detections to stages of an attack framework

Bundles help triage analysts see the full picture and make more informed decisions about the overall threat.

## Analytics Page

The Analytics section of the Howler UI provides a support page for analytics and individual detections. It contains
useful information for both the author of a analytic or detection as well as the triage analysts who are investigating
the hits.

### Overview

Here, you are encouraged to provide documentation of your analytic in Markdown. This should provide more details about
how the analytic or detection works, what it's looking for and how to validate the hits.

Metrics are automatically generated to give insights on the performance. A very high false-positive rate might be a
sign that detection needs improvement. On the other hand, a high true-positive rate might warrant that hits be
automatically promoted to alerts.

### Comments

In this tab, users can leave feedback about an analytic or detection. Consider this your end-user's line of
communication with you.

### Hit Comments

From here, you can review all of the comments left on specific hits to better understand what triage analysts are
signaling to each other.

### Notebooks

If your triage analysts are frequently needing to investigate alerts outside of Howler, you can link to a Jupyter
Notebook. That means a button will appear in the Howler UI. When a user clicks the button, they will be taken to
JupyterHub with the specified Notebook open and the specific hit loaded, allowing the queries to be pre-populated
with relevant values.

### Triage Settings

Configure which assessment options are valid for your analytic. For example, if your analytic only detects malicious
activity, you might limit assessments to `compromise`, `attempt`, or `mitigated` - excluding options like
`false-positive` or `legitimate` that don't make sense for your detection logic.

This helps guide analysts toward appropriate assessments and maintains consistency in how hits are triaged.

## Related Documentation

- **[Client Development Guide](/howler/developer/client/)** - Comprehensive guide on using the Howler Python
  client, including installation, authentication, and advanced hit operations
- **[Elastic Common Schema (ECS)](https://www.elastic.co/guide/en/ecs/current/index.html)** - Official Elastic
  documentation for the ECS field reference and guidelines
- **Hit Schema Reference** - View the complete Howler hit schema in your Howler instance under Help → Hit Schema
- **[API Documentation](https://your-howler-instance.com/api/doc)** - Interactive API documentation for your Howler
  instance (replace with your actual URL)
