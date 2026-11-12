# Step 9 application-v2 provenance scripts

These are the exact scripts used to capture `../application-v2.json`. They are stored byte-for-byte, so ruff excludes them: their SHA-256 values are pinned in the fixture's `metadata.stored_document_capture.provenance`.

- `capture-legacy-sources.py` (`cd5358160015e0e640a57fdb84e4cb844eb05242ef64a0b9af506cb32667ca2b`) runs inside a read-only checkout of `origin/main` at `2da444e40820f3fed8732705d1b378482f4a1218`, which still contains the legacy ODM. It sends the frozen Hit, Case and User inputs through the legacy `ESCollection.save()` path and intercepts the exact `client.index(document=...)` body. It never connects to Elasticsearch.
- `build-application-v2-fixture.py` (`34614a424e71fee6e61014630ec4684d34d18036bbf208c9e2439746da3378d3`) combines that capture with the frozen ODM contract inventory to produce `application-v2.json`.

The recorded commands contain the original `/tmp/opencode` paths. To reproduce a capture, check out `origin/main` at the commit above, install its API environment, and adjust those paths.
