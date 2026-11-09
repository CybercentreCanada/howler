---
name: howler-alert-ingestion
description: Ingest an already prepared JSONL file of Howler alerts into a user-confirmed Howler environment and index through the Howler client.
---

# Ingest a prepared alert file

Use this skill only when the user already has a JSONL file whose every line is a
valid Howler alert. Do not inspect, rewrite, validate, or transform the alert
payload. The client loads the complete file for one bulk ingest call; its
configured retry behavior applies to that request.

The helper requires Python 3.12+ and `uv`; its PEP 723 metadata pins
`howler-client==3.4.0`. Set `SKILL` to this directory. Configure the trusted API
URL with `HOWLER_API_URL` or `--api-url`. Authenticate with a private token file
named by `HOWLER_TOKEN_FILE`, or set `HOWLER_JWT` in the environment (the token
file takes precedence). Never pass a secret as a command-line argument or print
it.

The input defaults to `alerts.jsonl`. `--index` is required and accepts `hit` or
`event`; the SDK otherwise defaults to `hit`, but this helper requires the
destination to be explicit. `--report` defaults to `ingest-report.json`.

First preview the exact destination, index, and resolved input path:

```bash
uv run --script "$SKILL/scripts/ingest.py" --index hit
```

This exits without making a request and reports the values to confirm. Ask the
user to explicitly approve that API URL, index, and file. Only after approval,
rerun the same command, passing the exact `confirmation` string from the preview
as `--confirm` and keeping the same `--api-url`, `--input`, and `--report`
values. The helper rejects a missing or mismatched confirmation. It reserves a
new, private report file before it creates the client or calls the ingest API.
It refuses to overwrite an existing report or replace the input/credential file.

The private report labels IDs and count as `server_returned_ids` and
`server_returned_count`: these are IDs returned by the API, not verification
that every datastore bulk item persisted. Ingestion is not atomic or
all-or-nothing. Terminal output contains only the server-returned count; alert
payloads, IDs, tokens, and SDK error details are not printed. Keep both the
source file and report private.

The client uses HTTPS with certificate verification, a 120-second timeout per
attempt, `retries=1`, and errors on bad requests or exhausted retries. In this
client, `retries=1` means up to two attempts, not exactly-once delivery. A
timeout or failure can leave the write outcome uncertain. The helper never
reruns the ingest automatically. Both indexes can trigger asynchronous
correlation. The helper suppresses SDK logs for privacy; API warnings are not
included in returned IDs, so successful output does not verify correlation. If
the report shows an unknown or pending outcome, check the selected Howler
environment before any manually initiated retry.
