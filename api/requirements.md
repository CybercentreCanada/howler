# Correlation System Requirements

1. We need to check over every single alert that is ingested into Howler. This can be tens of thousands of alerts per hour, for a sense of scale.
2. For each of these alerts, we need to check them against every single rule every case has specified, comparing the alert object to the lucene query as specified.
  a. Only enabled rules that have not yet expired are valid.
3. If the rule matches, we need to add the alert to the correct spot based on the path the rule specifies.

---

## Architecture Overview

The correlation system is split into two independent phases:

1. **Event service refactor** — replace the single-pod HTTP relay with Redis pubsub so
   every API pod can serve WebSocket clients and receive events directly.
2. **Correlation pipeline** — a queue-driven, debounced batch worker that matches
   newly ingested alerts against active case rules using inverted Elasticsearch queries.

### Why inverted bulk search?

Rather than checking each alert against every rule in Python
(O(alerts × rules) `lucene_service.match()` calls), we flip the problem:

- Collect a batch of new alert IDs.
- For each active rule, run **one** Elasticsearch query:
  `(rule.query) AND howler.id:(id1 OR id2 …)`.
- ES returns only the IDs that actually match — typically a tiny subset.

Elasticsearch is purpose-built for Lucene query evaluation at scale. Running
1 000 rule queries against a batch of 50 IDs is far more efficient than
50 000 in-Python match calls. ES also caches filters internally.

### Why debounced batching?

Tens of thousands of alerts per hour ≈ 3–10 ingestions per second.
Processing one-at-a-time would create unsustainable per-alert overhead.
Batching up to 50 alerts **or** flushing every 5 seconds (whichever comes
first) amortizes the rule-load and ES query cost across many alerts.

---

## Phase 1 — Event Service Refactor

### Current state

`event_service.emit()` works in two modes:

| Mode | Behaviour |
|---|---|
| `DEBUG` / `HWL_USE_WEBSOCKET_API` | Calls in-process handlers directly (single-process only) |
| Production | HTTP POST to a single dedicated websocket pod via `config.ui.websocket_url` |

The production path is a bottleneck — all WebSocket clients must connect to
that one pod, and if it's down events are silently lost.

### Target state

Replace both paths with **Redis pubsub** using the existing
`EventSender` / `EventWatcher` wrappers in
`howler/remote/datatypes/events.py`.

- `event_service.emit("hits", data)` publishes to the Redis channel
  `howler.events.hits` via `EventSender`.
- On startup every pod creates an `EventWatcher` subscribed to
  `howler.events.*` in a daemon thread.  Received messages call all
  locally registered handlers (the `on()` / `off()` API stays unchanged).
- The nonpersistent Redis instance is used — these are fire-and-forget
  messages and a missed event is acceptable.
- `/socket/v1/emit/<event>` HTTP endpoint is **deprecated** (kept for
  backward compat but no longer called by the event service).
- `config.ui.websocket_url` is **deprecated**.

### Files changed

| File | Change |
|---|---|
| `howler/services/event_service.py` | `emit()` → `EventSender.send()` ; startup watcher binds pubsub → local handlers |
| `howler/api/socket.py` | `/emit/<event>` marked deprecated; `connect()` unchanged (still uses `on`/`off`) |

---

## Phase 2 — Correlation Pipeline

### Step A — Ingestion queue hook

**File:** `howler/api/v2/ingest.py`

After `hit_service.create_hit()` succeeds, push the new alert ID to a
**Redis `NamedQueue("howler.ingestion_queue")`**.

This queue is backed by the **persistent** Redis instance (reliable delivery —
a missed alert means a missed correlation).

```python
from howler.remote.datatypes.queues.named import NamedQueue
from howler.config import redis_persistent

ingestion_queue: NamedQueue[str] = NamedQueue("howler.ingestion_queue",
                                               host=..., port=...,
                                               private=False)
# after create_hit:
ingestion_queue.push(odm.howler.id)
```

### Step B — Correlation service

**New file:** `howler/services/correlation_service.py`

Public API:

| Function | Purpose |
|---|---|
| `get_active_rules() → list[tuple[str, CaseRule]]` | Load all cases that have rules, return `(case_id, rule)` pairs where `rule.enabled` and `rule.timeframe` has not passed |
| `process_batch(hit_ids: list[str])` | For each active rule, run `ds.hit.search(rule.query, filters=[f"howler.id:({' OR '.join(ids)})"])`. For each match, render the destination via `chevron.render(rule.destination, hit_primitives)`, then call `case_service.append_case_item(case_id, "hit", hit_id, rendered_path)`. Catch `InvalidDataException` (duplicate) and log at DEBUG. |
| `run_worker()` | Main loop: block-pops from `ingestion_queue` with `timeout=BATCH_TIMEOUT`, accumulates IDs up to `BATCH_SIZE`, then calls `process_batch()`. Runs in a daemon thread. |

### Step C — Correlation worker startup

**New file:** `howler/cronjobs/correlation.py`

Implements `setup_job(scheduler)` (auto-discovered by the cronjob system).
Starts a `threading.Thread(target=run_worker, daemon=True)` — the worker
is queue-driven, not time-driven, so a long-running thread fits better than
a periodic APScheduler trigger.

### Step D — Configuration

**File:** `howler/odm/models/config.py`

New model under `System`:

```python
class Correlation(BaseModel):
    enabled: bool = Field(default=True, description="Enable the correlation worker?")
    batch_size: int = Field(default=50, description="Max alerts per batch.")
    batch_timeout: int = Field(default=5, description="Seconds to wait before flushing a partial batch.")
```

Accessed as `config.system.correlation.enabled`, etc.

### Mustache destination templating

`CaseRule.destination` supports Mustache templates via `chevron.render()`.
The full hit dictionary (`hit.as_primitives()`) is the template context.

| Template | Rendered example |
|---|---|
| `alerts/{{howler.analytic}}` | `alerts/My Detection` |
| `threats/{{threat.technique.id}}/alerts` | `threats/T1059/alerts` |
| `related` | `related` (static) |

### Duplicate handling

If a hit already exists in the case (`InvalidDataException` from
`append_case_item`), it is silently skipped with a `DEBUG`-level log
message. No error is raised.

### Rule filtering logic

A rule is **active** if and only if:

1. `rule.enabled == True`
2. `rule.timeframe is None` **OR** `datetime.fromisoformat(rule.timeframe) > utcnow()`

---

## Scale Analysis

| Scenario | Queries/batch | Notes |
|---|---|---|
| 100 rules, batch = 50 | 100 ES queries | Trivial |
| 10 000 rules, batch = 50 | 10 000 ES queries | ~1–2 s on a healthy cluster |
| 100 000 rules, batch = 50 | Too many | See mitigation below |

**Mitigation (future work):** The Elasticsearch `_msearch` API allows
bundling all rule queries into a single HTTP request, reducing network
overhead by ~100×. This is a natural follow-up if rule counts grow to
tens of thousands.

---

## Testing

### Unit tests (`test/unit/services/test_correlation_service.py`)

- `test_get_active_rules_filters_disabled` — disabled rules excluded
- `test_get_active_rules_filters_expired` — expired timeframe rules excluded
- `test_get_active_rules_includes_valid` — enabled + non-expired rules included
- `test_process_batch_adds_matching_hits` — mock DS search, verify `append_case_item` called
- `test_process_batch_skips_duplicates` — `InvalidDataException` caught, no crash
- `test_process_batch_renders_destination_template` — Mustache rendered correctly

### Integration tests (`test/integration/api/test_correlation.py`)

1. Create a case.
2. Add a rule (`query="event.kind:alert"`, `destination="alerts/{{howler.analytic}}"`).
3. Enable the rule.
4. Ingest a hit matching the rule's query.
5. Call `process_batch([hit_id])` directly (bypasses background thread for determinism).
6. Assert the hit appears in `case.items` at the expected rendered path.

---

## File Index

| File | Status | Purpose |
|---|---|---|
| `howler/services/event_service.py` | Modified | Redis pubsub emit + watcher startup |
| `howler/api/socket.py` | Modified | Deprecate `/emit/<event>` |
| `howler/api/v2/ingest.py` | Modified | Push ID to ingestion queue |
| `howler/services/correlation_service.py` | **New** | `get_active_rules`, `process_batch`, `run_worker` |
| `howler/cronjobs/correlation.py` | **New** | `setup_job` → starts worker thread |
| `howler/odm/models/config.py` | Modified | `Correlation` config model |
| `test/unit/services/test_correlation_service.py` | **New** | Unit tests |
| `test/integration/api/test_correlation.py` | **New** | Integration tests |
