<!-- docs/ingestion/bundles.md -->

# Howler Hit Bundles

Hit bundles can be used to easily package together a large number of similar alerts, allowing analysts to easily triage them as a single incident. For example, consider a single computer that repeatedly makes a network call to `baddomain.ru` - while an alert may be generated for every instance of this computer hitting that domain, it makes sense for analysts to treat all these alerts as a single case.

## Creating bundles through the Howler Client

There are a couple of ways to create a bundle through the howler client:

```python
from howler_client import get_client

howler = get_client("https://howler.dev.analysis.cyber.gc.ca")

"""Creating a howler bundle and the hits at the same time"""
howler.bundle.create(
    # First argument is the bundle hit
    {
        "howler.analytic": "example-test",
        "howler.score": 0
    },
    # Second argument is a hit or list of hits to include in the bundle
    [
        {
            "howler.analytic": "example-test",
            "howler.score": 0
        },
        {
            "howler.analytic": "example-test",
            "howler.score": 0
        }
    ]
)

"""Creating a howler bundle from existing hits"""
howler.bundle.create(
    {
        "howler.analytic": "example-test",
        "howler.score": 0,
        "howler.hits": ["YcUsL8QsjmwwIdstieROk", "6s7MztwuSvz6tM0PgGJhvz"]
    },
    # Note: In future releases, you won't need to include this argument
    []
)


"""Creating from a map"""
bundle_hit = {
    "score": 0,
    "bundle": True
}

map = {
    "score": ["howler.score"],
    "bundle": ["howler.is_bundle"]
}

howler.bundle.create_from_map("example-test", bundle_hit, map, [{"score": 0}])
```

## Viewing bundles on the Howler UI

In order to view created bundles on the Howler UI, you can use the query `howler.is_bundle:true`. This will provide a list of created bundles you can look through.

Clicking on a bundle will open up a slightly different search UI to normal. In this case, we automatically filter the search results to include only hits that are included in the bundle. To make this obvious, the header representing the bundle will appear above the search bar.

You can continue to filter through hits using the same queries as usual, and view them as usual. When triaging a bundle, assessing it will apply this assessment to all hits in the bundle, **except those that have already been triaged**. That is, if the bundle is open, all open hits will be assessed when you assess it.

Bundles also have a **Summary** tab not available for regular hits. This summary tab will aid you in aggregating data about all the hits in the bundle. Simply open the tab and click "Create Summary". Note that this may take some time, as a large number of queries are being run to aggregate the data.
