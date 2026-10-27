"""Persistent Redis queue, run records, leases, acknowledgements, and permits."""

import hashlib
import json
import math
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, NamedTuple

import gevent
from gevent import Greenlet, monkey
from redis.exceptions import WatchError

from howler.common.logging import get_logger
from howler.config import config
from howler.remote.datatypes import get_client

logger = get_logger(__file__)

_KEY_PREFIX = "howler.ai_triage:{jobs}"
RUN_SCAN_BATCH = 128
QUEUE_LOCK_TTL = 15
QUEUE_LOCK_ACQUIRE_TIMEOUT = 5.0
QUEUE_LOCK_CLEANUP_TIMEOUT = 2.0
OWNER_HISTORY_CLEANUP_BATCH = 128
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
_LOCK_HELPERS: set[Greenlet] = set()
_LOCK_HELPER_OWNERS: dict[Greenlet, "LockCleanupOwner | None"] = {}
_LOCK_HELPER_DEFERRED: set[Greenlet] = set()
_UNOWNED_LOCK_CLEANUP_FAILURE: str | None = None
_OWNED_LOCK_CLEANUP_FAILURES: list[str] = []


class LockCleanupOwner:
    """Opaque owner for one worker/root cleanup tree, separate from lock fences."""

    __slots__ = ("helpers", "failure", "parent", "children", "cleanup_deadline", "cancelled")

    def __init__(self: Any, parent: "LockCleanupOwner | None" = None) -> None:
        self.helpers: set[Greenlet] = set()
        self.failure: str | None = None
        self.parent = parent
        self.children: set[LockCleanupOwner] = set()
        self.cleanup_deadline: float | None = None
        self.cancelled = False
        if parent is not None:
            parent.children.add(self)


_LOCK_CLEANUP_OWNER: ContextVar[LockCleanupOwner | None] = ContextVar("ai_triage_lock_cleanup_owner", default=None)


class LockCleanupError(RuntimeError):
    """A lock nonce may still be live; callers must stop rather than retry work."""


class _LockAcquireDeadline(TimeoutError):
    """One Redis SET-NX attempt did not settle inside its acquisition budget."""


class _LockCleanupDeadline(TimeoutError):
    """Nonce compare-delete did not settle inside its cleanup budget."""


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


def _owner_active_key(owner: str) -> str:
    digest = hashlib.sha256(owner.encode("utf-8")).hexdigest()
    return f"{_KEY_PREFIX}:owner-active:{digest}"


def _owner_expiry_key(owner: str) -> str:
    digest = hashlib.sha256(owner.encode("utf-8")).hexdigest()
    return f"{_KEY_PREFIX}:owner-expiry:{digest}"


def _owner_index_initialized_key(owner: str) -> str:
    digest = hashlib.sha256(owner.encode("utf-8")).hexdigest()
    return f"{_KEY_PREFIX}:owner-index-initialized:{digest}"


def _queue_key() -> str:
    return f"{_KEY_PREFIX}:pending"


def _lease_key() -> str:
    return f"{_KEY_PREFIX}:leases"


def _active_key() -> str:
    return f"{_KEY_PREFIX}:active"


def _reconcile_due_key() -> str:
    return f"{_KEY_PREFIX}:reconcile-due"


def _reconcile_lease_key() -> str:
    return f"{_KEY_PREFIX}:reconcile-leases"


def _global_lock_key() -> str:
    return f"{_KEY_PREFIX}:lock"


def _run_lock_key(run_id: str) -> str:
    return f"{_KEY_PREFIX}:run-lock:{run_id}"


@contextmanager
def _locked(client: Any, key: str, *, timeout: float | None = None) -> Iterator[None]:  # noqa: C901
    owner = _LOCK_CLEANUP_OWNER.get()
    if (owner is not None and pending_lock_cleanup_failure(owner) is not None) or (
        owner is None and _UNOWNED_LOCK_CLEANUP_FAILURE is not None
    ):
        raise LockCleanupError("Previous AI triage lock cleanup is incomplete; restart is required")
    lock_timeout = QUEUE_LOCK_TTL if timeout is None else timeout
    # This nonce is created before the first Redis operation and is independent
    # of redis-py's greenlet/thread-local token. If cancellation lands after SET
    # succeeds but before acquire() returns, cleanup still knows exactly what it
    # may compare-and-delete.
    token = uuid.uuid4().hex
    token_bytes = token.encode("utf-8")
    lock = client.lock(key, timeout=lock_timeout, blocking_timeout=QUEUE_LOCK_ACQUIRE_TIMEOUT)
    acquire_deadline = time.monotonic() + QUEUE_LOCK_ACQUIRE_TIMEOUT
    acquired = False
    acquire_helper: Greenlet | None = None
    acquire_incomplete = False
    fence_context = None
    pending_exception: BaseException | None = None
    try:
        while time.monotonic() < acquire_deadline:
            if monkey.is_module_patched("socket"):
                acquire_helper = _start_lock_helper(lambda: _acquire_nonce_once(lock, token, acquire_deadline), owner)
                settled, result, error, cancellation = _wait_for_lock_helper(
                    acquire_helper, deadline=acquire_deadline + 0.1
                )
                if not settled:
                    acquire_incomplete = True
                    pending_exception = LockCleanupError("Redis lock acquisition did not settle before its deadline")
                    break
                if cancellation is not None:
                    pending_exception = cancellation
                if error is not None:
                    if pending_exception is None:
                        pending_exception = error
                elif result:
                    acquired = True
                if pending_exception is not None or acquired:
                    break
            else:
                # Import-only/native callers stay synchronous; never late-patch
                # sockets or move Redis work onto an unsafe native provider thread.
                try:
                    acquired = bool(lock.acquire(blocking=False, token=token))
                except BaseException as exc:
                    pending_exception = exc
                    break
                if acquired:
                    break

            remaining = acquire_deadline - time.monotonic()
            if remaining <= 0:
                break
            if monkey.is_module_patched("socket"):
                gevent.sleep(min(0.05, remaining))
            else:
                time.sleep(min(0.05, remaining))

        if pending_exception is None and not acquired:
            pending_exception = TimeoutError("Could not acquire AI triage queue lock")
        if pending_exception is None and acquired:
            fence_context = _LOCK_FENCES.set((*_LOCK_FENCES.get(), _LockFence(key, token_bytes)))
            yield
    except BaseException as exc:
        if pending_exception is None:
            pending_exception = exc
    finally:
        if fence_context is not None:
            _LOCK_FENCES.reset(fence_context)

        cleanup_deadline = time.monotonic() + QUEUE_LOCK_CLEANUP_TIMEOUT
        if acquire_incomplete and acquire_helper is not None:
            _defer_nonce_cleanup_until_acquire_settles(
                acquire_helper, client, key, token_bytes, owner, cleanup_deadline
            )
            cleanup_error: BaseException | None = LockCleanupError(
                "Redis lock acquisition is still pending; queue work is stopped until its nonce is cleaned"
            )
            cleanup_cancellation = None
        else:
            cleanup_error, cleanup_cancellation = _release_nonce_owned(
                client, key, token_bytes, owner, cleanup_deadline
            )

        if cleanup_error is not None:
            _record_lock_cleanup_failure(str(cleanup_error), owner)
            raise LockCleanupError("AI triage queue lock cleanup did not complete") from cleanup_error
        if cleanup_cancellation is not None:
            if pending_exception is not None:
                cleanup_cancellation.__context__ = pending_exception
            pending_exception = cleanup_cancellation

    if pending_exception is not None:
        raise pending_exception


def _register_lock_helper(helper: Greenlet, owner: LockCleanupOwner | None) -> None:
    _LOCK_HELPERS.add(helper)
    _LOCK_HELPER_OWNERS[helper] = owner
    if owner is not None:
        owner.helpers.add(helper)
    helper.rawlink(lambda completed, bound_owner=owner: _forget_lock_helper(completed, bound_owner))


def _forget_lock_helper(helper: Greenlet, owner: LockCleanupOwner | None) -> None:
    # A deferred acquire owns its release callback until the compare-delete
    # helper is registered. Keep the parent visible across that transfer.
    if helper in _LOCK_HELPER_DEFERRED:
        return
    _LOCK_HELPERS.discard(helper)
    _LOCK_HELPER_OWNERS.pop(helper, None)
    if owner is not None:
        owner.helpers.discard(helper)


def _start_lock_helper(operation: Any, owner: LockCleanupOwner | None) -> Greenlet:
    """Start and retain an owned gevent helper before it can perform I/O."""
    helper = Greenlet(operation)
    _register_lock_helper(helper, owner)
    try:
        helper.start()
    except BaseException:
        if helper.started:
            # A host/start hook can fail after scheduling. Keep the explicit
            # owner registration and let the caller observe this same handle.
            return helper
        _forget_lock_helper(helper, owner)
        raise
    return helper


def _wait_for_lock_helper(
    helper: Greenlet, *, deadline: float
) -> tuple[bool, Any, BaseException | None, BaseException | None]:
    """Wait for the same operation to settle, deferring caller cancellation."""
    cancellation: BaseException | None = None
    while not helper.ready():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            # Give an already-expired child Timeout one hub turn to unwind its
            # Redis call. Never create a replacement attempt or reset deadline.
            try:
                gevent.sleep(0)
            except BaseException as exc:
                if cancellation is None:
                    cancellation = exc
            if not helper.ready():
                return False, None, None, cancellation
            break
        try:
            gevent.sleep(min(0.01, remaining))
        except BaseException as exc:
            if cancellation is None:
                cancellation = exc

    return True, helper.value, helper.exception, cancellation


def _acquire_nonce_once(lock: Any, token: str, deadline: float) -> bool:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise _LockAcquireDeadline("Redis lock acquisition deadline elapsed")
    with gevent.Timeout(remaining, _LockAcquireDeadline("Redis lock acquisition deadline elapsed")):
        return bool(lock.acquire(blocking=False, token=token))


def _compare_delete_nonce(client: Any, key: str, token: bytes, deadline: float) -> int:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise _LockCleanupDeadline("Redis lock cleanup deadline elapsed")
    with gevent.Timeout(remaining, _LockCleanupDeadline("Redis lock cleanup deadline elapsed")):
        return int(client.eval(_LOCK_RELEASE_SCRIPT, 1, key, token))


def _release_nonce_owned(
    client: Any, key: str, token: bytes, owner: LockCleanupOwner | None, cleanup_deadline: float
) -> tuple[BaseException | None, BaseException | None]:
    """Compare-delete a nonce; never clear a replacement owner's lock."""
    if not monkey.is_module_patched("socket"):
        try:
            client.eval(_LOCK_RELEASE_SCRIPT, 1, key, token)
        except BaseException as exc:
            return exc, None
        return None, None

    try:
        helper = _start_lock_helper(lambda: _compare_delete_nonce(client, key, token, cleanup_deadline), owner)
    except BaseException as exc:
        # A nonce may already be live even though its compare-delete helper
        # could not be created. Surface this through _locked's owner-scoped
        # fail-closed path rather than allowing cleanup startup to escape.
        return exc, None
    settled, _result, error, cancellation = _wait_for_lock_helper(helper, deadline=cleanup_deadline + 0.1)
    if not settled:
        return LockCleanupError("Redis nonce compare-delete helper did not settle"), cancellation
    if error is not None:
        return error, cancellation
    return None, cancellation


def _defer_nonce_cleanup_until_acquire_settles(
    acquire_helper: Greenlet,
    client: Any,
    key: str,
    token: bytes,
    owner: LockCleanupOwner | None,
    cleanup_deadline: float,
) -> None:
    """Retain an incomplete acquire and clean its nonce as soon as it settles."""
    # Keep the acquire visible while its deferred cleanup is being registered;
    # rawlink callback context is not used to infer ownership.
    _LOCK_HELPERS.add(acquire_helper)
    _LOCK_HELPER_OWNERS[acquire_helper] = owner
    if owner is not None:
        owner.helpers.add(acquire_helper)
    _LOCK_HELPER_DEFERRED.add(acquire_helper)

    def cleanup_after_acquire(_completed: Greenlet) -> None:
        try:
            cleanup = _start_lock_helper(lambda: _compare_delete_nonce(client, key, token, cleanup_deadline), owner)
            _LOCK_HELPER_DEFERRED.discard(acquire_helper)
            _forget_lock_helper(acquire_helper, owner)

            def record_cleanup_failure(helper: Greenlet) -> None:
                if helper.exception is not None:
                    _record_lock_cleanup_failure("deferred Redis nonce compare-delete failed", owner)

            cleanup.rawlink(record_cleanup_failure)
        except BaseException:
            _record_lock_cleanup_failure("deferred Redis nonce compare-delete could not start", owner)

    acquire_helper.rawlink(cleanup_after_acquire)


def _record_lock_cleanup_failure(message: str, owner: LockCleanupOwner | None) -> None:
    global _UNOWNED_LOCK_CLEANUP_FAILURE
    if owner is None:
        _UNOWNED_LOCK_CLEANUP_FAILURE = message
    else:
        owner.failure = message
        _OWNED_LOCK_CLEANUP_FAILURES.append(message)
    logger.critical("AI triage queue lock cleanup incomplete: %s", message)


def pending_lock_helpers(owner: LockCleanupOwner | None = None) -> tuple[Greenlet, ...]:
    """Return any lock I/O helpers that have not yet settled."""
    for helper in tuple(_LOCK_HELPERS):
        if helper.ready() and helper not in _LOCK_HELPER_DEFERRED:
            helper_owner = _LOCK_HELPER_OWNERS.get(helper)
            _forget_lock_helper(helper, helper_owner)
    if owner is not None:
        owners = _cleanup_owner_tree(owner)
        return tuple({helper for scope in owners for helper in scope.helpers})
    return tuple(_LOCK_HELPERS)


def wait_for_lock_cleanup_owner(owner: LockCleanupOwner, deadline: float) -> tuple[bool, BaseException | None]:
    """Drain only one owner tree's lock helpers to its fixed absolute deadline."""
    cancellation: BaseException | None = None
    while pending_lock_helpers(owner):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False, cancellation
        try:
            gevent.sleep(min(0.01, remaining))
        except BaseException as exc:
            if cancellation is None:
                cancellation = exc
    return True, cancellation


def _cleanup_owner_tree(owner: LockCleanupOwner) -> tuple[LockCleanupOwner, ...]:
    scopes = [owner]
    for child in tuple(owner.children):
        scopes.extend(_cleanup_owner_tree(child))
    return tuple(scopes)


def finish_lock_cleanup_owner(owner: LockCleanupOwner) -> bool:
    """Detach a fully drained successful child scope from its worker root."""
    if owner.children or pending_lock_helpers(owner) or pending_lock_cleanup_failure(owner) is not None:
        return False
    if owner.parent is not None:
        owner.parent.children.discard(owner)
        owner.parent = None
    return True


def pending_lock_cleanup_failure(owner: LockCleanupOwner | None = None) -> str | None:
    """Return a fail-closed cleanup diagnostic, if any helper failed."""
    if owner is not None:
        return next((scope.failure for scope in _cleanup_owner_tree(owner) if scope.failure), None)
    if _UNOWNED_LOCK_CLEANUP_FAILURE is not None:
        return _UNOWNED_LOCK_CLEANUP_FAILURE
    return _OWNED_LOCK_CLEANUP_FAILURES[0] if _OWNED_LOCK_CLEANUP_FAILURES else None


def new_lock_cleanup_owner(parent: LockCleanupOwner | None = None) -> LockCleanupOwner:
    """Create an opaque owner for an independently drainable worker operation."""
    return LockCleanupOwner(parent)


def current_lock_cleanup_owner() -> LockCleanupOwner | None:
    """Return the explicitly bound cleanup scope, if this greenlet has one."""
    return _LOCK_CLEANUP_OWNER.get()


def set_lock_cleanup_deadline(owner: LockCleanupOwner, deadline: float) -> None:
    """Set one absolute deadline on this scope without extending its parent."""
    if owner.cleanup_deadline is None or deadline < owner.cleanup_deadline:
        owner.cleanup_deadline = deadline


def lock_cleanup_deadline(owner: LockCleanupOwner) -> float | None:
    """Return the earliest absolute cleanup deadline in this owner tree."""
    deadlines = [scope.cleanup_deadline for scope in _cleanup_owner_tree(owner) if scope.cleanup_deadline is not None]
    return min(deadlines) if deadlines else None


@contextmanager
def bind_lock_cleanup_owner(owner: LockCleanupOwner | None) -> Iterator[None]:
    """Bind cleanup attribution without changing Redis nonce fence authority."""
    token = _LOCK_CLEANUP_OWNER.set(owner)
    try:
        yield
    finally:
        _LOCK_CLEANUP_OWNER.reset(token)


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
    """Persist a run and maintain bounded owner indexes atomically."""
    now = _now()
    run_id = run["run_id"]
    owner = run.get("_owner")
    _save_run(client, run, pipeline)

    if run.get("state") == "completed":
        pipeline.zrem(_active_key(), run_id)
    else:
        created_at = float(run.get("_created_at_epoch", now))
        pipeline.zadd(_active_key(), {run_id: created_at})

    if not isinstance(owner, str):
        return

    owner_key = _owner_key(owner)
    active_key = _owner_active_key(owner)
    expiry_key = _owner_expiry_key(owner)
    initialized_key = _owner_index_initialized_key(owner)

    initialized, migrated_active, migrated_expiries = _initialize_owner_history(client, owner, run, pipeline, now)
    created_at = float(run.get("_created_at_epoch", now))
    pipeline.zadd(owner_key, {run_id: created_at})

    expired_ids = client.zrangebyscore(expiry_key, "-inf", now, start=0, num=OWNER_HISTORY_CLEANUP_BATCH)
    if expired_ids:
        pipeline.zrem(expiry_key, *expired_ids)
        pipeline.zrem(owner_key, *expired_ids)

    if run.get("state") != "completed":
        pipeline.zadd(active_key, {run_id: created_at})
        # A live run must remain discoverable regardless of how long it waits
        # in the queue. Terminal members are bounded separately by their run
        # expiration scores and the owner index's eventual TTL.
        pipeline.persist(owner_key)
        pipeline.persist(expiry_key)
        pipeline.persist(initialized_key)
        return

    pipeline.zrem(active_key, run_id)
    expires_at = run.get("_expires_at")
    if expires_at is None:
        # Completed runs normally receive an expiry in _update_counts_and_state.
        # Do not let an incomplete/corrupt terminal record shorten owner history.
        pipeline.persist(owner_key)
        pipeline.persist(expiry_key)
        pipeline.persist(initialized_key)
        return
    expires_at = float(expires_at)
    pipeline.zadd(expiry_key, {run_id: expires_at})

    if not initialized:
        # A malformed legacy document prevents safe migration. Keep the owner
        # index available rather than risk expiring another live run's history.
        pipeline.persist(owner_key)
        pipeline.persist(expiry_key)
        pipeline.persist(initialized_key)
        return

    active_ids = set(migrated_active)
    active_members = client.zrange(active_key, 0, -1)
    active_ids.update(member.decode("utf-8") if isinstance(member, bytes) else str(member) for member in active_members)
    if any(active_id != run_id for active_id in active_ids):
        pipeline.persist(owner_key)
        pipeline.persist(expiry_key)
        pipeline.persist(initialized_key)
        return

    expiry_members = client.zrange(expiry_key, 0, -1, withscores=True)
    latest_expiry = max(
        [
            expires_at,
            *(float(score) for _member, score in expiry_members if float(score) > now),
            *migrated_expiries.values(),
        ]
    )
    history_ttl = max(1, math.ceil(latest_expiry - now))
    # Expiring the whole owner index only after its last live run finishes keeps
    # all queued/running records reachable while bounding terminal history to
    # the latest retained run document.
    pipeline.delete(active_key)
    pipeline.expire(owner_key, history_ttl)
    pipeline.expire(expiry_key, history_ttl)
    pipeline.expire(initialized_key, history_ttl)


def _initialize_owner_history(  # noqa: C901
    client: Any,
    owner: str,
    current_run: dict[str, Any] | None,
    pipeline: Any,
    now: float,
) -> tuple[bool, set[str], dict[str, float]]:
    """Backfill live/terminal owner indexes once without expiring uncertain data."""
    owner_key = _owner_key(owner)
    active_key = _owner_active_key(owner)
    expiry_key = _owner_expiry_key(owner)
    initialized_key = _owner_index_initialized_key(owner)
    if client.get(initialized_key) is not None:
        return True, set(), {}

    active: dict[str, float] = {}
    expiries: dict[str, float] = {}
    unknown_document = False
    current_id = current_run.get("run_id") if current_run is not None else None
    for raw_id in client.zrange(owner_key, 0, -1):
        run_id = raw_id.decode("utf-8") if isinstance(raw_id, bytes) else str(raw_id)
        run: dict[str, Any] | None
        if current_run is not None and run_id == current_id:
            run = current_run
        else:
            run, missing = _load_indexed_run(client, run_id)
            if missing:
                if client.zscore(_active_key(), run_id) is not None:
                    active[run_id] = now
                else:
                    pipeline.zrem(owner_key, run_id)
                    pipeline.zrem(active_key, run_id)
                    pipeline.zrem(expiry_key, run_id)
                continue
            if run is None:
                unknown_document = True
                continue

        globally_active = client.zscore(_active_key(), run_id) is not None
        if (current_run is None or run_id != current_id) and globally_active:
            active[run_id] = float(run.get("_created_at_epoch", now))
            continue

        if run.get("state") != "completed":
            if run.get("state") not in {"queued", "running"}:
                unknown_document = True
                continue
            active[run_id] = float(run.get("_created_at_epoch", now))
            if not globally_active:
                pipeline.zadd(_active_key(), {run_id: active[run_id]})
            continue

        raw_expiry = run.get("_expires_at")
        if raw_expiry is None:
            unknown_document = True
            continue
        expires_at = float(raw_expiry)
        if expires_at <= now:
            pipeline.zrem(owner_key, run_id)
            pipeline.zrem(expiry_key, run_id)
            pipeline.zrem(active_key, run_id)
        else:
            expiries[run_id] = expires_at

    if active:
        pipeline.zadd(active_key, active)
    if expiries:
        pipeline.zadd(expiry_key, expiries)
    if not unknown_document:
        pipeline.set(initialized_key, "1")

    return not unknown_document, set(active), expiries


def _ensure_owner_history_initialized(client: Any, owner: str, now: float) -> None:
    """Migrate legacy owner indexes when history is first read after rollout."""
    owner_key = _owner_key(owner)
    initialized_key = _owner_index_initialized_key(owner)
    if client.get(initialized_key) is not None or not client.zcard(owner_key):
        return

    with _locked(client, _global_lock_key()):
        if client.get(initialized_key) is not None or not client.zcard(owner_key):
            return
        active_key = _owner_active_key(owner)
        expiry_key = _owner_expiry_key(owner)
        with _fenced_pipeline(client) as pipeline:
            initialized, active, expiries = _initialize_owner_history(client, owner, None, pipeline, now)
            if not initialized:
                pipeline.persist(owner_key)
                pipeline.persist(active_key)
                pipeline.persist(expiry_key)
                pipeline.persist(initialized_key)
            elif active:
                pipeline.persist(owner_key)
                pipeline.persist(active_key)
                pipeline.persist(expiry_key)
                pipeline.persist(initialized_key)
            elif expiries:
                expiry_members = client.zrange(expiry_key, 0, -1, withscores=True)
                latest_expiry = max([*expiries.values(), *(float(score) for _member, score in expiry_members)])
                history_ttl = max(1, math.ceil(latest_expiry - now))
                pipeline.expire(owner_key, history_ttl)
                pipeline.expire(expiry_key, history_ttl)
                pipeline.expire(initialized_key, history_ttl)
            else:
                # All old owner members were confirmed missing or expired.
                pipeline.delete(owner_key)
                pipeline.delete(active_key)
                pipeline.delete(expiry_key)
                pipeline.delete(initialized_key)
            pipeline.execute()


def _terminalize_reconciliation_horizon(item: dict[str, Any], now: float) -> None:
    if item.get("_write_intent"):
        reason = "write_outcome_unknown"
        message = "Write outcome could not be confirmed; the previous lead may have been replaced"
    else:
        reason = "write_not_submitted"
        message = "AI triage candidate was not submitted before reconciliation expired"
    item.update(state="failed", reason=reason, message=message, finished_at=_timestamp(now))


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
        run.pop("_auth_scheme", None)
        run.pop("_prompt", None)
        for item in results:
            item.pop("_candidate", None)
            item.pop("_candidate_source_version", None)
            item.pop("_write_intent", None)
            item.pop("_commit_phase", None)
            item.pop("_reconcile_at", None)
            item.pop("_reconcile_horizon_at", None)
            item.pop("_reconcile_attempts", None)
            item.pop("_reconcile_nonce", None)
            item.pop("_reconcile_lease_expires_at", None)
    run["updated_at"] = _timestamp()
    run["revision"] = int(run.get("revision", 0)) + 1


def _lease_member(run_id: str, index: int, nonce: str) -> str:
    return f"{run_id}|{index}|{nonce}"


def _reconcile_member(run_id: str, index: int) -> str:
    return f"{run_id}|{index}"


def _parse_reconcile_member(member: str) -> tuple[str, int] | None:
    try:
        run_id, index = member.rsplit("|", maxsplit=1)
        return run_id, int(index)
    except (ValueError, TypeError):
        return None


def _parse_lease_member(member: str) -> tuple[str, int, str] | None:
    try:
        run_id, index, nonce = member.split("|", maxsplit=2)
        return run_id, int(index), nonce
    except (ValueError, TypeError):
        return None


def _recover_expired_locked(client: Any, now: float) -> list[dict[str, Any]]:
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
            if item.get("_candidate") is not None:
                item["_commit_phase"] = "reconciling"
                item.setdefault("_reconcile_horizon_at", now + config.core.ai.retention_seconds)
                item["_reconcile_at"] = now
                item["reason"] = "write_reconciliation_pending"
                item["message"] = "Save outcome is being reconciled"
                _update_counts_and_state(run)
                with _fenced_pipeline(client) as pipeline:
                    pipeline.zrem(_lease_key(), member)
                    pipeline.zadd(_reconcile_due_key(), {_reconcile_member(run_id, index): now})
                    _persist_run(client, run, pipeline)
                    pipeline.execute()
                changed.append(run)
                continue
            if now >= deadline:
                item.update(
                    state="failed",
                    reason="run_deadline_exceeded",
                    message="AI triage exceeded its time limit",
                    finished_at=_timestamp(now),
                )
            elif (
                int(item.get("attempts", 0)) < config.core.ai.max_attempts
                or item.get("_candidate") is not None
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
    """Return one bounded owner-index page and explicit raw-index progress.

    Missing or terminally expired run documents are removed from every owner
    index. GET failures and malformed-but-present records are not treated as
    proof of expiration, so they remain indexed for a later successful read.
    ``exhausted`` reflects the raw Redis page length, not how many records were
    retained or matched application filters.
    """
    client = redis_client()
    owner_key = _owner_key(owner)
    rows = max(1, min(rows, RUN_SCAN_BATCH))
    now = _now()
    _ensure_owner_history_initialized(client, owner, now)
    with _locked(client, _global_lock_key()):
        run_ids = client.zrevrange(owner_key, offset, offset + rows - 1)
        results: list[dict[str, Any]] = []
        stale: list[str] = []
        for raw_id in run_ids:
            run_id = raw_id.decode("utf-8") if isinstance(raw_id, bytes) else str(raw_id)
            run, confirmed_missing = _load_indexed_run(client, run_id)
            active = client.zscore(_active_key(), run_id) is not None
            expired = bool(
                run
                and run.get("state") == "completed"
                and run.get("_expires_at") is not None
                and float(run["_expires_at"]) <= now
                and not active
            )
            if confirmed_missing or expired:
                stale.append(run_id)
            elif run:
                results.append(run)

        removed = _prune_owner_history_locked(client, owner, stale, now) if stale else []
        fetched_count = len(run_ids)
        boundary = offset + fetched_count
        removed_before_boundary = sum(1 for _run_id, rank in removed if rank < boundary)
        return results, OwnerRunScan(
            fetched_count=fetched_count,
            next_offset=max(0, boundary - removed_before_boundary),
            exhausted=fetched_count < rows,
        )


def _prune_owner_history_locked(  # noqa: C901
    client: Any, owner: str, run_ids: list[str], now: float
) -> list[tuple[str, int]]:
    """Prune confirmed stale owner IDs and return their pre-delete reverse ranks.

    The caller holds the global queue lock. Ranks are captured before the
    fenced transaction removes members so pagination can adjust only for
    actual deletions before the page boundary.
    """
    owner_key = _owner_key(owner)
    active_key = _owner_active_key(owner)
    expiry_key = _owner_expiry_key(owner)
    initialized_key = _owner_index_initialized_key(owner)
    expired_ids = client.zrangebyscore(expiry_key, "-inf", now, start=0, num=OWNER_HISTORY_CLEANUP_BATCH)
    run_ids = list(
        dict.fromkeys([*run_ids, *(raw.decode("utf-8") if isinstance(raw, bytes) else str(raw) for raw in expired_ids)])
    )
    removed: list[str] = []
    removed_ranks: list[tuple[str, int]] = []
    for run_id in run_ids:
        run, confirmed_missing = _load_indexed_run(client, run_id)
        active = client.zscore(_active_key(), run_id) is not None
        expired = bool(
            run
            and run.get("state") == "completed"
            and run.get("_expires_at") is not None
            and float(run["_expires_at"]) <= now
            and not active
        )
        if confirmed_missing or expired:
            removed.append(run_id)
            rank = client.zrevrank(owner_key, run_id)
            if rank is not None:
                removed_ranks.append((run_id, int(rank)))

    if removed:
        with _fenced_pipeline(client) as pipeline:
            pipeline.zrem(owner_key, *removed)
            pipeline.zrem(active_key, *removed)
            pipeline.zrem(expiry_key, *removed)
            pipeline.zrem(_active_key(), *removed)

            removed_set = set(removed)
            remaining_owner = {
                raw.decode("utf-8") if isinstance(raw, bytes) else str(raw) for raw in client.zrange(owner_key, 0, -1)
            } - removed_set
            remaining_active = {
                raw.decode("utf-8") if isinstance(raw, bytes) else str(raw) for raw in client.zrange(active_key, 0, -1)
            } - removed_set
            if not remaining_active:
                expiry_members = client.zrange(expiry_key, 0, -1, withscores=True)
                retained_expiries = {
                    raw.decode("utf-8") if isinstance(raw, bytes) else str(raw): float(score)
                    for raw, score in expiry_members
                    if float(score) > now
                    and (raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)) not in removed_set
                }
                if not remaining_owner:
                    pipeline.delete(owner_key)
                    pipeline.delete(expiry_key)
                    pipeline.delete(active_key)
                    pipeline.delete(initialized_key)
                elif remaining_owner <= retained_expiries.keys():
                    history_ttl = max(1, math.ceil(max(retained_expiries[run_id] for run_id in remaining_owner) - now))
                    pipeline.expire(owner_key, history_ttl)
                    pipeline.expire(expiry_key, history_ttl)
                    pipeline.expire(initialized_key, history_ttl)
            pipeline.execute()
    return removed_ranks
    with _locked(client, _global_lock_key()):
        for run_id in run_ids:
            run, confirmed_missing = _load_indexed_run(client, run_id)
            active = client.zscore(_active_key(), run_id) is not None
            expired = bool(
                run
                and run.get("state") == "completed"
                and run.get("_expires_at") is not None
                and float(run["_expires_at"]) <= now
                and not active
            )
            if confirmed_missing or expired:
                removed.append(run_id)

        if removed:
            with _fenced_pipeline(client) as pipeline:
                pipeline.zrem(owner_key, *removed)
                pipeline.zrem(active_key, *removed)
                pipeline.zrem(expiry_key, *removed)
                pipeline.zrem(_active_key(), *removed)

                removed_set = set(removed)
                remaining_owner = {
                    raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
                    for raw in client.zrange(owner_key, 0, -1)
                } - removed_set
                remaining_active = {
                    raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
                    for raw in client.zrange(active_key, 0, -1)
                } - removed_set
                if not remaining_active:
                    expiry_members = client.zrange(expiry_key, 0, -1, withscores=True)
                    retained_expiries = {
                        raw.decode("utf-8") if isinstance(raw, bytes) else str(raw): float(score)
                        for raw, score in expiry_members
                        if float(score) > now
                        and (raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)) not in removed_set
                    }
                    if not remaining_owner:
                        pipeline.delete(owner_key)
                        pipeline.delete(expiry_key)
                        pipeline.delete(active_key)
                        pipeline.delete(initialized_key)
                    elif remaining_owner <= retained_expiries.keys():
                        history_ttl = max(1, math.ceil(max(retained_expiries.values()) - now))
                        pipeline.expire(owner_key, history_ttl)
                        pipeline.expire(expiry_key, history_ttl)
                        pipeline.expire(initialized_key, history_ttl)
                pipeline.execute()
    return len(removed)


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
            run = _load_run(client, run_id)
            if not run or index >= len(run.get("results", [])):
                return None
            item = run["results"][index]
            if item.get("state") != "running" or item.get("_lease_nonce") != nonce:
                return None
            deadline = float(item.get("_deadline_at", now))
            lease_score = client.zscore(_lease_key(), _lease_member(run_id, index, nonce))
            if now >= deadline or lease_score is None or float(lease_score) <= now:
                return None
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
        run = _load_run(client, run_id)
        if not run or index >= len(run.get("results", [])):
            return False
        item = run["results"][index]
        now = _now()
        lease_score = client.zscore(_lease_key(), _lease_member(run_id, index, nonce))
        return bool(
            item.get("state") == "running"
            and item.get("_lease_nonce") == nonce
            and now < float(item.get("_deadline_at", 0))
            and lease_score is not None
            and float(lease_score) > now
        )


def checkpoint(run_id: str, index: int, nonce: str, task_id: str | None, context_id: str | None) -> bool:
    """Durably save A2A task/context identifiers immediately after observing them."""
    client = redis_client()
    with _locked(client, _run_lock_key(run_id)):
        run = _load_run(client, run_id)
        if not run or index >= len(run.get("results", [])):
            return False
        item = run["results"][index]
        if item.get("state") != "running" or item.get("_lease_nonce") != nonce:
            return False
        now = _now()
        lease_score = client.zscore(_lease_key(), _lease_member(run_id, index, nonce))
        deadline = float(item.get("_deadline_at", 0))
        if now >= deadline or lease_score is None or float(lease_score) <= now:
            return False
        if task_id:
            item["_a2a_task_id"] = task_id
        if context_id:
            item["_a2a_context_id"] = context_id
        with _fenced_pipeline(client) as pipeline:
            _save_run(client, run, pipeline)
            pipeline.execute()
        return True


def begin_provider_attempt(run_id: str, index: int, nonce: str) -> dict[str, Any] | None:
    """Count one actual new inference request, not claims or commit recovery."""
    client = redis_client()
    with _locked(client, _run_lock_key(run_id)):
        run = _load_run(client, run_id)
        if not run or index >= len(run.get("results", [])):
            return None
        item = run["results"][index]
        now = _now()
        lease_score = client.zscore(_lease_key(), _lease_member(run_id, index, nonce))
        if (
            item.get("state") != "running"
            or item.get("_lease_nonce") != nonce
            or item.get("_candidate") is not None
            or item.get("_a2a_task_id") is not None
            or now >= float(item.get("_deadline_at", 0))
            or lease_score is None
            or float(lease_score) <= now
        ):
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
        run = _load_run(client, run_id)
        if not run or index >= len(run.get("results", [])):
            return False
        item = run["results"][index]
        now = _now()
        lease_score = client.zscore(_lease_key(), _lease_member(run_id, index, nonce))
        if (
            item.get("state") != "running"
            or item.get("_lease_nonce") != nonce
            or now >= float(item.get("_deadline_at", 0))
            or lease_score is None
            or float(lease_score) <= now
        ):
            return False
        if item.get("_candidate") is not None:
            return item.get("_candidate") == candidate
        item["_candidate"] = candidate
        item["_commit_phase"] = "candidate_ready"
        item["_write_intent"] = False
        with _fenced_pipeline(client) as pipeline:
            _save_run(client, run, pipeline)
            pipeline.execute()
        return True


def set_commit_phase(run_id: str, index: int, nonce: str, phase: str) -> dict[str, Any] | None:
    """Persist write intent while the provider lease is still current."""
    if phase != "write_pending":
        raise ValueError("Unsupported AI triage commit phase")
    client = redis_client()
    with _locked(client, _run_lock_key(run_id)):
        run = _load_run(client, run_id)
        if not run or index >= len(run.get("results", [])):
            return None
        item = run["results"][index]
        now = _now()
        score = client.zscore(_lease_key(), _lease_member(run_id, index, nonce))
        if (
            item.get("state") != "running"
            or item.get("_lease_nonce") != nonce
            or item.get("_candidate") is None
            or score is None
            or float(score) <= now
            or now >= float(item.get("_deadline_at", 0))
        ):
            return None
        item["_commit_phase"] = phase
        item["_write_intent"] = True
        item["reason"] = None
        item["message"] = None
        _update_counts_and_state(run)
        with _fenced_pipeline(client) as pipeline:
            _persist_run(client, run, pipeline)
            pipeline.execute()
        return run


def defer_candidate_reconciliation(
    run_id: str, index: int, nonce: str, delay_seconds: float = 1.0
) -> dict[str, Any] | None:
    """Release a provider permit and schedule durable-candidate reconciliation."""
    client = redis_client()
    now = _now()
    member = _lease_member(run_id, index, nonce)
    with _locked(client, _global_lock_key()):
        with _locked(client, _run_lock_key(run_id)):
            run = _load_run(client, run_id)
            if not run or index >= len(run.get("results", [])):
                return None
            item = run["results"][index]
            score = client.zscore(_lease_key(), member)
            if (
                item.get("state") != "running"
                or item.get("_lease_nonce") != nonce
                or item.get("_candidate") is None
                or score is None
                or float(score) <= now
            ):
                return None

            horizon = item.get("_reconcile_horizon_at")
            if horizon is None:
                horizon = now + config.core.ai.retention_seconds
                item["_reconcile_horizon_at"] = horizon
            item.pop("_lease_nonce", None)
            item.pop("_lease_expires_at", None)
            item.pop("_commit_phase", None)
            item["_commit_phase"] = "reconciling"
            item["_reconcile_attempts"] = int(item.get("_reconcile_attempts", 0)) + 1
            due = min(float(horizon), now + max(0.0, delay_seconds))
            item["_reconcile_at"] = due
            item.update(
                reason="write_reconciliation_pending",
                message="Save outcome is being reconciled",
            )
            _update_counts_and_state(run)
            with _fenced_pipeline(client) as pipeline:
                pipeline.zrem(_lease_key(), member)
                pipeline.zadd(_reconcile_due_key(), {_reconcile_member(run_id, index): due})
                _persist_run(client, run, pipeline)
                pipeline.execute()
            return run


def _recover_reconciliation_leases_locked(client: Any, now: float) -> list[dict[str, Any]]:
    changed: list[dict[str, Any]] = []
    expired = client.zrangebyscore(_reconcile_lease_key(), "-inf", now)
    for raw_member in expired:
        member = raw_member.decode("utf-8") if isinstance(raw_member, bytes) else str(raw_member)
        parsed = _parse_lease_member(member)
        if not parsed:
            with _fenced_pipeline(client) as pipeline:
                pipeline.zrem(_reconcile_lease_key(), member)
                pipeline.execute()
            continue
        run_id, index, nonce = parsed
        with _locked(client, _run_lock_key(run_id)):
            run = _load_run(client, run_id)
            if not run or index >= len(run.get("results", [])):
                with _fenced_pipeline(client) as pipeline:
                    pipeline.zrem(_reconcile_lease_key(), member)
                    pipeline.execute()
                continue
            item = run["results"][index]
            if item.get("state") != "running" or item.get("_commit_phase") != "reconciling":
                with _fenced_pipeline(client) as pipeline:
                    pipeline.zrem(_reconcile_lease_key(), member)
                    pipeline.execute()
                continue
            if item.get("_reconcile_nonce") != nonce:
                with _fenced_pipeline(client) as pipeline:
                    pipeline.zrem(_reconcile_lease_key(), member)
                    pipeline.execute()
                continue
            item.pop("_reconcile_nonce", None)
            item.pop("_reconcile_lease_expires_at", None)
            horizon = float(item.get("_reconcile_horizon_at", now))
            with _fenced_pipeline(client) as pipeline:
                pipeline.zrem(_reconcile_lease_key(), member)
                if horizon <= now:
                    _terminalize_reconciliation_horizon(item, now)
                    _update_counts_and_state(run)
                    _persist_run(client, run, pipeline)
                else:
                    due_member = _reconcile_member(run_id, index)
                    item["_reconcile_at"] = now
                    pipeline.zadd(_reconcile_due_key(), {due_member: now})
                    _update_counts_and_state(run)
                    _persist_run(client, run, pipeline)
                pipeline.execute()
            changed.append(run)
    return changed


def claim_reconciliation() -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Claim a read/commit-recovery job without consuming a provider permit."""
    client = redis_client()
    now = _now()
    changed: list[dict[str, Any]] = []
    with _locked(client, _global_lock_key()):
        changed.extend(_recover_expired_locked(client, now))
        changed.extend(_recover_reconciliation_leases_locked(client, now))
        due_members = client.zrangebyscore(_reconcile_due_key(), "-inf", now)
        for raw_member in due_members:
            member = raw_member.decode("utf-8") if isinstance(raw_member, bytes) else str(raw_member)
            parsed = _parse_reconcile_member(member)
            if not parsed:
                with _fenced_pipeline(client) as pipeline:
                    pipeline.zrem(_reconcile_due_key(), member)
                    pipeline.execute()
                continue
            run_id, index = parsed
            with _locked(client, _run_lock_key(run_id)):
                run = _load_run(client, run_id)
                if (
                    not run
                    or index >= len(run.get("results", []))
                    or run["results"][index].get("state") != "running"
                    or run["results"][index].get("_commit_phase") != "reconciling"
                ):
                    with _fenced_pipeline(client) as pipeline:
                        pipeline.zrem(_reconcile_due_key(), member)
                        pipeline.execute()
                    continue
                item = run["results"][index]
                horizon = float(item.get("_reconcile_horizon_at", now))
                if horizon <= now:
                    _terminalize_reconciliation_horizon(item, now)
                    _update_counts_and_state(run)
                    with _fenced_pipeline(client) as pipeline:
                        pipeline.zrem(_reconcile_due_key(), member)
                        _persist_run(client, run, pipeline)
                        pipeline.execute()
                    changed.append(run)
                    continue

                nonce = uuid.uuid4().hex
                lease_expiry = min(horizon, now + config.core.ai.lease_seconds)
                item["_reconcile_nonce"] = nonce
                item["_reconcile_lease_expires_at"] = lease_expiry
                _update_counts_and_state(run)
                with _fenced_pipeline(client) as pipeline:
                    pipeline.zrem(_reconcile_due_key(), member)
                    pipeline.zadd(_reconcile_lease_key(), {_lease_member(run_id, index, nonce): lease_expiry})
                    _persist_run(client, run, pipeline)
                    pipeline.execute()
                return {
                    "run_id": run_id,
                    "index": index,
                    "hit_id": item["hit_id"],
                    "nonce": nonce,
                    "deadline_at": float(item.get("_deadline_at", now)),
                    "horizon_at": horizon,
                    "candidate": item["_candidate"],
                    "write_intent": bool(item.get("_write_intent")),
                    "run": run,
                }, changed
    return None, changed


def reconciliation_is_current(run_id: str, index: int, nonce: str) -> bool:
    """Return whether this nonce still owns its reconciliation lease."""
    client = redis_client()
    with _locked(client, _run_lock_key(run_id)):
        run = _load_run(client, run_id)
        if not run or index >= len(run.get("results", [])):
            return False
        item = run["results"][index]
        score = client.zscore(_reconcile_lease_key(), _lease_member(run_id, index, nonce))
        return (
            item.get("state") == "running"
            and item.get("_commit_phase") == "reconciling"
            and item.get("_reconcile_nonce") == nonce
            and score is not None
            and float(score) > _now()
        )


def defer_reconciliation(run_id: str, index: int, nonce: str, delay_seconds: float = 1.0) -> dict[str, Any] | None:
    """Release a read-only reconciliation lease and schedule the next check."""
    client = redis_client()
    now = _now()
    member = _lease_member(run_id, index, nonce)
    with _locked(client, _global_lock_key()):
        with _locked(client, _run_lock_key(run_id)):
            run = _load_run(client, run_id)
            if not run or index >= len(run.get("results", [])):
                return None
            item = run["results"][index]
            score = client.zscore(_reconcile_lease_key(), member)
            if (
                item.get("state") != "running"
                or item.get("_commit_phase") != "reconciling"
                or item.get("_reconcile_nonce") != nonce
                or score is None
                or float(score) <= now
            ):
                return None
            item.pop("_reconcile_nonce", None)
            item.pop("_reconcile_lease_expires_at", None)
            item["_reconcile_attempts"] = int(item.get("_reconcile_attempts", 0)) + 1
            horizon = float(item.get("_reconcile_horizon_at", now))
            with _fenced_pipeline(client) as pipeline:
                pipeline.zrem(_reconcile_lease_key(), member)
                if horizon <= now:
                    _terminalize_reconciliation_horizon(item, now)
                    _update_counts_and_state(run)
                    _persist_run(client, run, pipeline)
                else:
                    due = min(horizon, now + max(0.1, delay_seconds))
                    item["_reconcile_at"] = due
                    item.update(
                        reason="write_reconciliation_pending",
                        message="Save outcome is being reconciled",
                    )
                    _update_counts_and_state(run)
                    pipeline.zadd(_reconcile_due_key(), {_reconcile_member(run_id, index): due})
                    _persist_run(client, run, pipeline)
                pipeline.execute()
            return run


def mark_reconciliation_write_intent(run_id: str, index: int, nonce: str) -> bool:
    """Persist the write-intent marker before a reconciliation commit attempt."""
    client = redis_client()
    with _locked(client, _run_lock_key(run_id)):
        run = _load_run(client, run_id)
        if not run or index >= len(run.get("results", [])):
            return False
        item = run["results"][index]
        now = _now()
        member = _lease_member(run_id, index, nonce)
        score = client.zscore(_reconcile_lease_key(), member)
        if (
            item.get("state") != "running"
            or item.get("_commit_phase") != "reconciling"
            or item.get("_reconcile_nonce") != nonce
            or now >= float(item.get("_deadline_at", 0))
            or score is None
            or float(score) <= now
        ):
            return False
        item["_write_intent"] = True
        _update_counts_and_state(run)
        with _fenced_pipeline(client) as pipeline:
            _persist_run(client, run, pipeline)
            pipeline.execute()
        return True


def finish_reconciliation(
    run_id: str,
    index: int,
    nonce: str,
    *,
    state: str,
    reason: str | None = None,
    message: str | None = None,
) -> dict[str, Any] | None:
    """Complete a reconciliation only for the current reconciliation nonce."""
    client = redis_client()
    now = _now()
    member = _lease_member(run_id, index, nonce)
    with _locked(client, _global_lock_key()):
        with _locked(client, _run_lock_key(run_id)):
            run = _load_run(client, run_id)
            if not run or index >= len(run.get("results", [])):
                return None
            item = run["results"][index]
            score = client.zscore(_reconcile_lease_key(), member)
            if (
                item.get("state") != "running"
                or item.get("_commit_phase") != "reconciling"
                or item.get("_reconcile_nonce") != nonce
                or score is None
                or float(score) <= now
            ):
                return None
            item.pop("_reconcile_nonce", None)
            item.pop("_reconcile_lease_expires_at", None)
            item.update(
                state=state,
                reason=reason,
                message=message,
                finished_at=_timestamp(now),
            )
            _update_counts_and_state(run)
            with _fenced_pipeline(client) as pipeline:
                pipeline.zrem(_reconcile_lease_key(), member)
                pipeline.zrem(_reconcile_due_key(), _reconcile_member(run_id, index))
                _persist_run(client, run, pipeline)
                pipeline.execute()
            return run


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
                and transient_failures < config.core.ai.max_attempts
                and now < deadline
                and (int(item.get("attempts", 0)) < config.core.ai.max_attempts or can_resume)
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


def fail_pending_when_unavailable() -> tuple[list[dict[str, Any]], bool]:  # noqa: C901
    """Fail queued work without provider calls while integration config is invalid.

    Running leases from another live REST process are left alone. Once such a
    lease expires, recovery requeues it and this reconciler terminalizes it.
    """
    client = redis_client()
    now = _now()
    with _locked(client, _global_lock_key()):
        changed = _recover_expired_locked(client, now)
        active_ids = client.zrange(_active_key(), 0, -1)
        for raw_id in active_ids:
            run_id = raw_id.decode("utf-8") if isinstance(raw_id, bytes) else str(raw_id)
            with _locked(client, _run_lock_key(run_id)):
                run = _load_run(client, run_id)
                if not run:
                    with _fenced_pipeline(client) as pipeline:
                        pipeline.zrem(_active_key(), run_id)
                        pipeline.execute()
                    continue

                queued_indices: list[int] = []
                expired_members: list[str] = []
                reconcile_indices: list[int] = []
                for index, item in enumerate(run.get("results", [])):
                    if item.get("state") == "queued":
                        item.update(
                            state="failed",
                            reason="configuration_unavailable",
                            message="AI triage is disabled or not locally configured",
                            finished_at=_timestamp(now),
                        )
                        queued_indices.append(index)
                    elif item.get("state") == "running":
                        if item.get("_commit_phase") == "reconciling":
                            continue
                        nonce = item.get("_lease_nonce")
                        member = _lease_member(run_id, index, nonce) if isinstance(nonce, str) else None
                        score = client.zscore(_lease_key(), member) if member else None
                        if score is None or float(score) <= now:
                            if item.get("_write_intent") and item.get("_candidate") is not None:
                                item["_commit_phase"] = "reconciling"
                                item.setdefault("_reconcile_horizon_at", now + config.core.ai.retention_seconds)
                                item["_reconcile_at"] = now
                                item.update(
                                    reason="write_reconciliation_pending",
                                    message="Save outcome is being reconciled",
                                )
                                reconcile_indices.append(index)
                            else:
                                item.update(
                                    state="failed",
                                    reason="configuration_unavailable",
                                    message="AI triage is disabled or not locally configured",
                                    finished_at=_timestamp(now),
                                )
                            item.pop("_lease_nonce", None)
                            item.pop("_lease_expires_at", None)
                            if member:
                                expired_members.append(member)

                if queued_indices or expired_members or reconcile_indices:
                    _update_counts_and_state(run)
                    with _fenced_pipeline(client) as pipeline:
                        for index in queued_indices:
                            pipeline.lrem(_queue_key(), 0, json.dumps([run_id, index]))
                        if expired_members:
                            pipeline.zrem(_lease_key(), *expired_members)
                        for index in reconcile_indices:
                            pipeline.zadd(_reconcile_due_key(), {_reconcile_member(run_id, index): now})
                        _persist_run(client, run, pipeline)
                        pipeline.execute()
                    changed.append(run)

        return changed, bool(client.zcard(_active_key()))
