---
status: accepted
---

# Use in-process workers and split Redis instances instead of a task broker

Background work—correlation (`correlation.py`), action execution (`action_queue_worker.py`), AI triage (`ai_triage_worker.py`), and scheduled retention/cleanup—runs inside API processes as APScheduler jobs and daemon threads gated by `HWL_USE_JOB_SYSTEM` and `_should_start_background_services()`, rather than in a separate Celery or external task-broker deployment. Durable job queues (`NamedQueue` in `api/howler/remote/datatypes/queues/named.py`) use a persistent Redis instance, while transient inter-pod WebSocket fan-out (`comms_service.py`) uses a separate nonpersistent Redis pubsub instance.

## Considered Options

- **Celery or standalone worker framework**: Rejected to avoid operating another worker/broker stack and separate deployment manifests for moderate background workloads.

## Consequences

- Background throughput scales with `HWL_USE_JOB_SYSTEM`-enabled API pods rather than independently autoscaled worker pools.
- Process guards in `api/howler/app.py` (`_should_start_background_services`) are required so Werkzeug's reloader parent process and pytest imports do not spawn competing worker threads.
