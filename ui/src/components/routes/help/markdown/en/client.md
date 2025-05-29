# Howler Client Documentation

This documentation will outline how to interact with the howler API using the howler client in both Java and python development environments. We will outline the basic process of creating a new hit in each environment as well as searching howler for hits matching your query.

## Getting started

### Installation

In order to use the howler client, you need to list it as a dependency in your project.

#### **Python**

Simply install through pip:

```bash
pip install howler_client
```

You can also add it to your requirements.txt, or whatever dependency management system you use.

#### **Java**

You can list the howler client as a dependency in your pom.xml:

```xml
<dependency>
  <groupId>io.github.cybercentrecanada</groupId>
  <artifactId>howler-client</artifactId>
  <version>1.6.0-SNAPSHOT</version>
</dependency>
```

Once this is complete, you should be able to start using the howler client!

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

That's it! You can now use the `howler` object to interact with the server. So what does that actually look like?

### Creating hits in Python

For the python client, you can create hits using the `howler.hit.create_from_map` function. This function takes in three arguments:

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

### Querying hits in Python

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

## Java Client

In order to connect to howler using the Java Client, a similarly simple approach can be used:

```java
String USERNAME = "user";
String APIKEY = "devkey:user";

HowlerClient howlerClient = new HowlerClient();
howlerClient.initializeApiKeyAuthentication(USERNAME, APIKEY);
```

That's it! You can now use the `howlerClient` class to interact with the server.

### Creating hits in Java

The process for creating hits using the Java client is quite different from the python client, due to the strongly typed nature of Java. Instead of specifying a map from raw data to howler's specification, the java implementation of the howler client requires you to create the hit using the build in types:

```java
HowlerModel howler = new HowlerModel();
howler.setAnalytic("test");
howler.setHash("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
HitModel hit = new HitModel();
hit.setHowler(howler);

howlerClient.createHits(List.of(hit));
```

### Querying hits in Java

Similar to creating hits, searching for hits in Java uses a `SearchOptions` class to capture the query specifications:

```java
HitSearchResponse response = howlerClient.searchHits(
  SearchOptions.builder()
    .query("howler.analytic:assemblyline")
    .fields(List.of("howler.id", "howler.analytic"))
    .filters(List.of("event.created:[now-5d TO now]"))
    .rows(10)
    .offset(40)
    .timeout(1000)
    .useArchive(true)
    .build()
);

for (HitModel h : response.getApiResponse().getItems()) {
  System.out.println(h.getHowler().getId());
}
```
