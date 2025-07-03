# Hit Links

In order to facilitate the addition of additional tools one can use to triage a hit, Howler allows users to specify a set of links, along with a title and icon to show. This documentation will walk you through how to use these links.

## Specification

In order to add links, you can use the `howler.links` field. This field takes in a list of objects with three keys:

```python
hit = {
  "howler.links": [
    {
      "title": "Link Title with Internal Image",
      "href": "https://example.com",
      # Note that this specifies another application, not an image link
      "icon": "superset",
    },
    {
      "title": "Link Title with External Image",
      "href": "https://www.britannica.com/animal/goose-bird",
      # Note that this specifies an image link. We don't provide hosting, so you'll need to host it somewhere else!
      "icon": "https://cdn.britannica.com/76/76076-050-39DDCBA1/goose-Canada-North-America.jpg",
    },
  ]
}
```

Note the icon can either be:

1. A name identifying a linked application (from the app switcher), to use its icon
2. An external URL

If you'd like to use a linked app, the following values are currently supported:

$APP_LIST

Using any of these values will automatically use the corresponding icon. No need to host your own!
