"""Persistent Redis queue, run records, leases, acknowledgements, and permits."""

import hashlib
import json
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, NamedTuple

from redis.exceptions import WatchError

from howler.common.logging import get_logger
from howler.config import config
from howler.remote.datatypes import get_client

logger = get_logger(__file__)

_KEY_PREFIX = "howler.ai_triage:{jobs}"
RUN_SCAN_BATCH = 128
QUEUE_LOCK_TTL = 15
QUEUE_LOCK_ACQUIRE_TIMEOUT = 5.0
_LOCK_RELEASE_SCRIPT = """
local token = redis.call('get', KEYS[1])
if not token or token ~= ARGV[1] then
    return 0
end
return redis.call('del', KEYS[1])
"""


class _LockFence:
    def __init__(self: Any, key: str, token: bytes):
        self.key = key
        self.token = token


_LOCK_FENCES: ContextVar[tuple[_LockFence, ...]] = ContextVar("ai_triage_lock_fences", default=())


class OwnerRunScan(NamedTuple):
    """Raw owner-index pagination progress, independent of retained matches."""

    fetched_count: int
    next_offset: int
    exhausted: bool


def _now() -> float:
    return time.time()


def _timestamp(value: float | None = None) -> str:
    return (
        datetime.fromtimestamp(value if value is not None else _now(), timezone.utc).isoformat().replace("+00:00", "Z")
    )


def redis_client():
    """Return the shared persistent Redis client."""
    return get_client(config.core.redis.persistent.host, config.core.redis.persistent.port, private=False)


def _run_key(run_id: str) -> str:
    return f"{_KEY_PREFIX}:run:{run_id}"


def _owner_key(owner: str) -> str:
    digest = hashlib.sha256(owner.encode("utf-8")).hexdigest()
    return f"{_KEY_PREFIX}:owner:{digest}"


def _queue_key() -> str:
    return f"{_KEY_PREFIX}:pending"


def _lease_key() -> str:
    return f"{_KEY_PREFIX}:leases"


def _active_key() -> str:
    return f"{_KEY_PREFIX}:active"


def _global_lock_key() -> str:
    return f"{_KEY_PREFIX}:lock"


def _run_lock_key(run_id: str) -> str:
    return f"{_KEY_PREFIX}:run-lock:{run_id}"


@contextmanager
def _locked(client: Any, key: str) -> Iterator[None]:
    """Acquire a Redis nonce lock and fence any transaction made under it."""
    token = uuid.uuid4().hex.encode("utf-8")
    deadline = time.monotonic() + QUEUE_LOCK_ACQUIRE_TIMEOUT
    acquired = False
    fence_context = None
    try:
        while time.monotonic() < deadline:
            if client.set(key, token, nx=True, ex=QUEUE_LOCK_TTL):
                acquired = True
                break
            time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))
        if not acquired:
            raise TimeoutError("Could not acquire AI triage queue lock")
        fence_context = _LOCK_FENCES.set((*_LOCK_FENCES.get(), _LockFence(key, token)))
        yield
    finally:
        if fence_context is not None:
            _LOCK_FENCES.reset(fence_context)
        client.eval(_LOCK_RELEASE_SCRIPT, 1, key, token)


@contextmanager
def _fenced_pipeline(client: Any) -> Iterator[Any]:
    """Create a watched Redis transaction fenced by every held lock token.

    Redis locks are leases and may expire while a process is paused. Watching
    their nonce makes Redis abort the transaction if a newer lock owner has
    acquired the lock (or the lock expired) before these writes commit.
    """
    fences = _LOCK_FENCES.get()
    if not fences:
        raise RuntimeError("AI triage Redis writes require a fenced queue lock")

    pipeline = client.pipeline(transaction=True)
    try:
        pipeline.watch(*(fence.key for fence in fences))
        for fence in fences:
            current = pipeline.get(fence.key)
            if isinstance(current, str):
                current = current.encode("utf-8")
            if current != fence.token:
                raise WatchError("AI triage queue lock fence was lost")  # noqa: TRY301
        pipeline.multi()
        yield pipeline
    except Exception:
        pipeline.reset()
        raise
    finally:
        pipeline.reset()


def _parse_run(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        logger.error("Ignoring malformed persisted AI triage run record")  # noqa: TRY400
        return None
    return parsed if isinstance(parsed, dict) else None


def _load_run(client: Any, run_id: str) -> dict[str, Any] | None:
    return _parse_run(client.get(_run_key(run_id)))


def _load_indexed_run(client: Any, run_id: str) -> tuple[dict[str, Any] | None, bool]:
    """Return the run and whether Redis confirmed its document is missing.

    A failed GET propagates; malformed records and transport errors must not be
    mistaken for an expired document and removed from the owner's history.
    """
    raw = client.get(_run_key(run_id))
    return _parse_run(raw), raw is None


def _save_run(client: Any, run: dict[str, Any], pipeline: Any = None) -> None:
    target = pipeline if pipeline is not None else client
    serialized = json.dumps(run, ensure_ascii=False, separators=(",", ":"))
    expires_at = run.get("_expires_at")
    if run.get("state") != "completed" or expires_at is None:
        target.set(_run_key(run["run_id"]), serialized)
    else:
        ttl = max(1, int(float(expires_at) - _now()))
        target.set(_run_key(run["run_id"]), serialized, ex=ttl)


def _persist_run(client: Any, run: dict[str, Any], pipeline: Any) -> None:
    """Persist a run and maintain its active and owner indexes atomically."""
    run_id = run["run_id"]
    created_at = float(run.get("_created_at_epoch", _now()))
    _save_run(client, run, pipeline)
    if run.get("state") == "completed":
        pipeline.zrem(_active_key(), run_id)
    else:
        pipeline.zadd(_active_key(), {run_id: created_at})
    owner = run.get("_owner")
    if isinstance(owner, str):
        pipeline.zadd(_owner_key(owner), {run_id: created_at})


def _update_counts_and_state(run: dict[str, Any]) -> None:
    results = run.get("results", [])
    states = [entry.get("state") for entry in results]
    run["counts"] = {
        "total": len(states),
        "queued": states.count("queued"),
        "running": states.count("running"),
        "succeeded": states.count("succeeded"),
        "failed": states.count("failed"),
        "skipped": states.count("skipped"),
    }
    if run["counts"]["queued"] or run["counts"]["running"]:
        run["state"] = "running" if run.get("started_at") else "queued"
    else:
        run["state"] = "completed"
        if run.get("finished_at") is None:
            run["finished_at"] = _timestamp()
        if run.get("_expires_at") is None:
            expires_at = _now() + config.core.ai.retention_seconds
            run["expires_at"] = _timestamp(expires_at)
            run["_expires_at"] = expires_at
        # Provider credentials and per-run prompt data are unnecessary after
        # terminal completion; minimize the time they remain in Redis.
        run.pop("_encrypted_bearer_token", None)
        run.pop("_prompt", None)
        for item in results:
            item.pop("_candidate", None)
    run["updated_at"] = _timestamp()
    run["revision"] = int(run.get("revision", 0)) + 1


def _lease_member(run_id: str, index: int, nonce: str) -> str:
    return f"{run_id}|{index}|{nonce}"


def _owned_item(
    client: Any, run_id: str, index: int, nonce: str, now: float | None = None
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Return a running item only while this worker still owns its live lease."""
    run = _load_run(client, run_id)
    if not run or index >= len(run.get("results", [])):
        return None

    item = run["results"][index]
    if item.get("state") != "running" or item.get("_lease_nonce") != nonce:
        return None

    now = _now() if now is None else now
    lease_score = client.zscore(_lease_key(), _lease_member(run_id, index, nonce))
    if now >= float(item.get("_deadline_at", now)) or lease_score is None or float(lease_score) <= now:
        return None
    return run, item


def _parse_lease_member(member: str) -> tuple[str, int, str] | None:
    try:
        run_id, index, nonce = member.split("|", maxsplit=2)
        return run_id, int(index), nonce
    except (ValueError, TypeError):
        return None


def _recover_expired_locked(client: Any, now: float, *, unavailable: bool = False) -> list[dict[str, Any]]:
    """Requeue jobs whose worker lease expired, or fail them at hard limits."""
    expired = client.zrangebyscore(_lease_key(), "-inf", now)
    changed: list[dict[str, Any]] = []
    for raw_member in expired:
        member = raw_member.decode("utf-8") if isinstance(raw_member, bytes) else str(raw_member)
        parsed = _parse_lease_member(member)
        if not parsed:
            with _fenced_pipeline(client) as pipeline:
                pipeline.zrem(_lease_key(), member)
                pipeline.execute()
            continue
        run_id, index, nonce = parsed
        with _locked(client, _run_lock_key(run_id)):
            run = _load_run(client, run_id)
            if not run or index >= len(run.get("results", [])):
                with _fenced_pipeline(client) as pipeline:
                    pipeline.zrem(_lease_key(), member)
                    pipeline.execute()
                continue
            item = run["results"][index]
            if item.get("state") == "queued":
                # A process can die after reserving a permit but before saving
                # the running state. Requeue defensively; duplicate queue entries
                # are harmless because claim verifies item state under lock.
                with _fenced_pipeline(client) as pipeline:
                    pipeline.rpush(_queue_key(), json.dumps([run_id, index]))
                    pipeline.zrem(_lease_key(), member)
                    pipeline.execute()
                continue
            if item.get("state") != "running" or item.get("_lease_nonce") != nonce:
                with _fenced_pipeline(client) as pipeline:
                    pipeline.zrem(_lease_key(), member)
                    pipeline.execute()
                continue
            item.pop("_lease_nonce", None)
            item.pop("_lease_expires_at", None)
            deadline = float(item.get("_deadline_at", 0))
            if unavailable:
                item.update(
                    state="failed",
                    reason="configuration_unavailable",
                    message="AI triage is disabled or not locally configured",
                    finished_at=_timestamp(now),
                )
            elif now >= deadline:
                item.update(
                    state="failed",
                    reason="run_deadline_exceeded",
                    message="AI triage exceeded its time limit",
                    finished_at=_timestamp(now),
                )
            elif (
                item.get("_candidate") is not None
                or int(item.get("attempts", 0)) < config.core.ai.max_attempts
                or item.get("_a2a_task_id") is not None
            ):
                item.update(state="queued", reason="worker_lease_expired", message=None)
            else:
                item.update(
                    state="failed",
                    reason="worker_lease_expired",
                    message="AI triage worker did not acknowledge the task",
                    finished_at=_timestamp(now),
                )
            _update_counts_and_state(run)
            with _fenced_pipeline(client) as pipeline:
                if item.get("state") == "queued":
                    pipeline.rpush(_queue_key(), json.dumps([run_id, index]))
                _persist_run(client, run, pipeline)
                pipeline.zrem(_lease_key(), member)
                pipeline.execute()
            changed.append(run)
    return changed


def create_run(run: dict[str, Any]) -> dict[str, Any]:
    """Persist a run and queue each target as an independently acknowledged job."""
    client = redis_client()
    results = run.get("results", [])
    with _locked(client, _global_lock_key()):
        _update_counts_and_state(run)
        with _fenced_pipeline(client) as pipeline:
            _persist_run(client, run, pipeline)
            for index in range(len(results)):
                pipeline.rpush(_queue_key(), json.dumps([run["run_id"], index]))
            pipeline.execute()
    return run


def read_run(run_id: str) -> dict[str, Any] | None:
    """Read a persisted run record, including private worker metadata."""
    return _load_run(redis_client(), run_id)


def list_runs(owner: str, offset: int = 0, rows: int = RUN_SCAN_BATCH) -> tuple[list[dict[str, Any]], OwnerRunScan]:
    """Return a bounded page from an owner's creation-time sorted index."""
    client = redis_client()
    owner_key = _owner_key(owner)
    offset = max(0, offset)
    rows = max(1, min(rows, RUN_SCAN_BATCH))
    now = _now()
    run_ids = client.zrevrange(owner_key, offset, offset + rows - 1)
    results: list[dict[str, Any]] = []
    stale: list[str] = []
    for raw_id in run_ids:
        run_id = raw_id.decode("utf-8") if isinstance(raw_id, bytes) else str(raw_id)
        run, missing = _load_indexed_run(client, run_id)
        expired = bool(
            run
            and run.get("state") == "completed"
            and run.get("_expires_at") is not None
            and float(run["_expires_at"]) <= now
        )
        if missing or expired:
            stale.append(run_id)
        elif run is not None:
            results.append(run)
    if stale:
        client.zrem(owner_key, *stale)
        client.zrem(_active_key(), *stale)
    fetched_count = len(run_ids)
    return results, OwnerRunScan(
        fetched_count=fetched_count,
        next_offset=max(0, offset + fetched_count - len(stale)),
        exhausted=fetched_count < rows,
    )


def _recover_deadline_for_run(run: dict[str, Any], now: float) -> None:
    for item in run.get("results", []):
        deadline = item.get("_deadline_at")
        if item.get("state") == "queued" and deadline is not None and now >= float(deadline):
            item.update(
                state="failed",
                reason="run_deadline_exceeded",
                message="AI triage exceeded its time limit",
                finished_at=_timestamp(now),
            )


def claim_next() -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:  # noqa: C901
    """Claim one pending item while respecting deployment-wide active permits."""
    client = redis_client()
    recovered: list[dict[str, Any]] = []
    with _locked(client, _global_lock_key()):
        now = _now()
        recovered.extend(_recover_expired_locked(client, now))
        max_active = config.core.ai.max_concurrent_jobs
        while int(client.zcard(_lease_key())) < max_active:
            # Peek first. The queue entry is removed in the same Redis
            # transaction that persists the claim and its lease, so a process
            # crash cannot lose a job between dequeue and acknowledgement.
            raw_job = client.lindex(_queue_key(), 0)
            if raw_job is None:
                return None, recovered
            if isinstance(raw_job, bytes):
                raw_job = raw_job.decode("utf-8")
            try:
                run_id, index = json.loads(raw_job)
                index = int(index)
            except (json.JSONDecodeError, ValueError, TypeError):
                logger.error("Ignoring malformed AI triage queue entry")  # noqa: TRY400
                with _fenced_pipeline(client) as pipeline:
                    pipeline.lpop(_queue_key())
                    pipeline.execute()
                continue

            with _locked(client, _run_lock_key(run_id)):
                run = _load_run(client, run_id)
                if not run or index >= len(run.get("results", [])):
                    with _fenced_pipeline(client) as pipeline:
                        pipeline.lpop(_queue_key())
                        pipeline.execute()
                    continue
                item = run["results"][index]
                if item.get("state") != "queued":
                    with _fenced_pipeline(client) as pipeline:
                        pipeline.lpop(_queue_key())
                        pipeline.execute()
                    continue

                if not item.get("_deadline_at"):
                    item["_deadline_at"] = now + config.core.ai.deadline_seconds
                deadline = float(item["_deadline_at"])
                if now >= deadline:
                    _recover_deadline_for_run(run, now)
                    _update_counts_and_state(run)
                    with _fenced_pipeline(client) as pipeline:
                        pipeline.lrem(_queue_key(), 1, raw_job)
                        _persist_run(client, run, pipeline)
                        pipeline.execute()
                    recovered.append(run)
                    continue

                nonce = uuid.uuid4().hex
                lease_expiry = min(deadline, now + config.core.ai.lease_seconds)
                item["state"] = "running"
                item["reason"] = None
                item["message"] = None
                if not item.get("started_at"):
                    item["started_at"] = _timestamp(now)
                item["_lease_nonce"] = nonce
                item["_lease_expires_at"] = lease_expiry
                if not run.get("started_at"):
                    run["started_at"] = _timestamp(now)
                _update_counts_and_state(run)
                with _fenced_pipeline(client) as pipeline:
                    pipeline.lrem(_queue_key(), 1, raw_job)
                    pipeline.zadd(_lease_key(), {_lease_member(run_id, index, nonce): lease_expiry})
                    _persist_run(client, run, pipeline)
                    pipeline.execute()

                return {
                    "run_id": run_id,
                    "index": index,
                    "hit_id": item["hit_id"],
                    "nonce": nonce,
                    "deadline_at": deadline,
                    "lease_expiry": lease_expiry,
                    "attempts": item["attempts"],
                    "run": run,
                }, recovered
    return None, recovered


def heartbeat(run_id: str, index: int, nonce: str) -> float | None:
    """Extend a worker's lease without extending its immutable run deadline."""
    client = redis_client()
    now = _now()
    with _locked(client, _global_lock_key()):
        with _locked(client, _run_lock_key(run_id)):
            owned = _owned_item(client, run_id, index, nonce, now)
            if owned is None:
                return None
            run, item = owned
            deadline = float(item.get("_deadline_at", now))
            expiry = min(deadline, now + config.core.ai.lease_seconds)
            item["_lease_expires_at"] = expiry
            with _fenced_pipeline(client) as pipeline:
                pipeline.zadd(_lease_key(), {_lease_member(run_id, index, nonce): expiry})
                _persist_run(client, run, pipeline)
                pipeline.execute()
            return expiry


def lease_is_current(run_id: str, index: int, nonce: str) -> bool:
    """Fence a worker before provider input and before committing a result."""
    client = redis_client()
    with _locked(client, _run_lock_key(run_id)):
        return _owned_item(client, run_id, index, nonce) is not None


def checkpoint(run_id: str, index: int, nonce: str, task_id: str | None, context_id: str | None) -> bool:
    """Durably save A2A task/context identifiers immediately after observing them."""
    client = redis_client()
    with _locked(client, _run_lock_key(run_id)):
        owned = _owned_item(client, run_id, index, nonce)
        if owned is None:
            return False
        run, item = owned
        if task_id:
            item["_a2a_task_id"] = task_id
        if context_id:
            item["_a2a_context_id"] = context_id
        with _fenced_pipeline(client) as pipeline:
            _save_run(client, run, pipeline)
            pipeline.execute()
        return True


def begin_provider_attempt(run_id: str, index: int, nonce: str) -> dict[str, Any] | None:
    """Count one actual new inference request, not claims or candidate retries."""
    client = redis_client()
    with _locked(client, _run_lock_key(run_id)):
        owned = _owned_item(client, run_id, index, nonce)
        if owned is None:
            return None
        run, item = owned
        if item.get("_candidate") is not None or item.get("_a2a_task_id") is not None:
            return None
        if int(item.get("attempts", 0)) >= config.core.ai.max_attempts:
            return None
        item["attempts"] = int(item.get("attempts", 0)) + 1
        _update_counts_and_state(run)
        with _fenced_pipeline(client) as pipeline:
            _save_run(client, run, pipeline)
            pipeline.execute()
        return {"attempts": item["attempts"], "run": run}


def store_candidate(run_id: str, index: int, nonce: str, candidate: dict[str, Any]) -> bool:
    """Persist a complete, validated provider candidate before dossier commit."""
    client = redis_client()
    with _locked(client, _run_lock_key(run_id)):
        owned = _owned_item(client, run_id, index, nonce)
        if owned is None:
            return False
        run, item = owned
        if item.get("_candidate") is not None:
            return item.get("_candidate") == candidate
        item["_candidate"] = candidate
        with _fenced_pipeline(client) as pipeline:
            _save_run(client, run, pipeline)
            pipeline.execute()
        return True


def finish_item(
    run_id: str,
    index: int,
    nonce: str,
    *,
    state: str,
    reason: str | None = None,
    message: str | None = None,
    transient: bool = False,
) -> dict[str, Any] | None:
    """Acknowledge an item, retry transient failures, and release its permit."""
    client = redis_client()
    now = _now()
    with _locked(client, _global_lock_key()):
        member = _lease_member(run_id, index, nonce)
        with _locked(client, _run_lock_key(run_id)):
            run = _load_run(client, run_id)
            if not run or index >= len(run.get("results", [])):
                with _fenced_pipeline(client) as pipeline:
                    pipeline.zrem(_lease_key(), member)
                    pipeline.execute()
                return None
            item = run["results"][index]
            if item.get("state") != "running" or item.get("_lease_nonce") != nonce:
                with _fenced_pipeline(client) as pipeline:
                    pipeline.zrem(_lease_key(), member)
                    pipeline.execute()
                return None

            deadline = float(item.get("_deadline_at", now))
            lease_score = client.zscore(_lease_key(), member)
            if lease_score is None or float(lease_score) <= now:
                return None
            transient_failures = int(item.get("_transient_failures", 0)) + int(transient)
            can_resume = item.get("_a2a_task_id") is not None
            can_retry = (
                transient
                and now < deadline
                and (
                    item.get("_candidate") is not None
                    or (
                        transient_failures < config.core.ai.max_attempts
                        and (int(item.get("attempts", 0)) < config.core.ai.max_attempts or can_resume)
                    )
                )
            )
            item.pop("_lease_nonce", None)
            item.pop("_lease_expires_at", None)
            with _fenced_pipeline(client) as pipeline:
                if can_retry:
                    item["_transient_failures"] = transient_failures
                    item.update(state="queued", reason=reason or "provider_transient_error", message=None)
                    pipeline.rpush(_queue_key(), json.dumps([run_id, index]))
                else:
                    final_state = "failed" if state not in {"succeeded", "skipped"} else state
                    if now >= deadline:
                        final_state = "failed"
                        reason = "run_deadline_exceeded"
                        message = "AI triage exceeded its time limit"
                    item.update(
                        state=final_state,
                        reason=reason,
                        message=message,
                        finished_at=_timestamp(now),
                    )
                _update_counts_and_state(run)
                _persist_run(client, run, pipeline)
                pipeline.zrem(_lease_key(), member)
                pipeline.execute()
            return run


def _fail_expired_unavailable_item(
    client: Any, run_id: str, index: int, item: dict[str, Any], now: float
) -> tuple[bool, str | None]:
    if item.get("state") != "running":
        return False, None
    nonce = item.get("_lease_nonce")
    member = _lease_member(run_id, index, nonce) if isinstance(nonce, str) else None
    score = client.zscore(_lease_key(), member) if member else None
    if score is not None and float(score) > now:
        return False, None
    item.update(
        state="failed",
        reason="configuration_unavailable",
        message="AI triage is disabled or not locally configured",
        finished_at=_timestamp(now),
    )
    item.pop("_lease_nonce", None)
    item.pop("_lease_expires_at", None)
    return True, member


def fail_pending_when_unavailable() -> tuple[list[dict[str, Any]], bool]:
    """Fail queued and expired work without provider calls when config is unavailable."""
    client = redis_client()
    now = _now()
    with _locked(client, _global_lock_key()):
        changed = _recover_expired_locked(client, now, unavailable=True)
        for raw_id in client.zrange(_active_key(), 0, -1):
            run_id = raw_id.decode("utf-8") if isinstance(raw_id, bytes) else str(raw_id)
            with _locked(client, _run_lock_key(run_id)):
                run = _load_run(client, run_id)
                if run is None:
                    with _fenced_pipeline(client) as pipeline:
                        pipeline.zrem(_active_key(), run_id)
                        pipeline.execute()
                    continue

                queued_indices: list[int] = []
                expired_leases: list[str] = []
                for index, item in enumerate(run.get("results", [])):
                    if item.get("state") == "queued":
                        item.update(
                            state="failed",
                            reason="configuration_unavailable",
                            message="AI triage is disabled or not locally configured",
                            finished_at=_timestamp(now),
                        )
                        queued_indices.append(index)
                    else:
                        failed, member = _fail_expired_unavailable_item(client, run_id, index, item, now)
                        if failed and member:
                            expired_leases.append(member)

                if queued_indices or expired_leases:
                    _update_counts_and_state(run)
                    with _fenced_pipeline(client) as pipeline:
                        for index in queued_indices:
                            pipeline.lrem(_queue_key(), 0, json.dumps([run_id, index]))
                        if expired_leases:
                            pipeline.zrem(_lease_key(), *expired_leases)
                        _persist_run(client, run, pipeline)
                        pipeline.execute()
                    changed.append(run)

        return changed, bool(client.zcard(_active_key()))
