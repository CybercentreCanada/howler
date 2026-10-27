"""Bounded gevent consumers for the persistent AI triage queue."""

import threading
import time
from typing import Any

import gevent
from gevent import Greenlet, monkey

from howler.common.logging import get_logger
from howler.config import config
from howler.services import ai_transport, ai_triage_queue, ai_triage_service

logger = get_logger(__file__)

_started = False
_stopping = False
_use_gevent = False
_workers: list[Greenlet | threading.Thread] = []
_worker_cleanup_owners: dict[Any, ai_triage_queue.LockCleanupOwner] = {}
_stop_event = threading.Event()
_shutdown_deadline: float | None = None
_worker_children: dict[Any, set[Greenlet]] = {}
_outstanding_children: set[Greenlet] = set()
_POLL_SECONDS = 0.5
_CHILD_CLEANUP_TIMEOUT = 2.0


class WorkerShutdownError(RuntimeError):
    """A worker tree did not drain before its single shutdown deadline."""


def _start_child(parent: Any, target: Any, *args: Any) -> Greenlet:
    """Register a child before it can run, then start it under the owner tree."""
    child = Greenlet(target, *args)
    _register_child(parent, child)
    try:
        child.start()
    except BaseException:
        _unregister_child(parent, child)
        raise
    return child


def _process_with_lock_owner(owner: ai_triage_queue.LockCleanupOwner, job: dict[str, Any]) -> None:
    with ai_triage_queue.bind_lock_cleanup_owner(owner):
        _process(job)


def _heartbeat_with_lock_owner(
    owner: ai_triage_queue.LockCleanupOwner,
    run_id: str,
    index: int,
    nonce: str,
    lease_expiry: float,
    deadline_at: float,
    processing: Greenlet,
) -> None:
    with ai_triage_queue.bind_lock_cleanup_owner(owner):
        _heartbeat_loop(run_id, index, nonce, lease_expiry, deadline_at, processing, owner)


def _renewal_with_lock_owner(
    owner: ai_triage_queue.LockCleanupOwner | None,
    run_id: str,
    index: int,
    nonce: str,
) -> float | None:
    with ai_triage_queue.bind_lock_cleanup_owner(owner):
        return ai_triage_queue.heartbeat(run_id, index, nonce)


def _active_cleanup_deadline() -> float:
    return _shutdown_deadline if _shutdown_deadline is not None else time.monotonic() + _CHILD_CLEANUP_TIMEOUT


def _owner_cleanup_deadline(owner: ai_triage_queue.LockCleanupOwner) -> float:
    """Use one absolute deadline for the whole owner tree's unwind and drain."""
    deadline = ai_triage_queue.lock_cleanup_deadline(owner)
    active_deadline = _active_cleanup_deadline()
    deadline = active_deadline if deadline is None else min(deadline, active_deadline)
    ai_triage_queue.set_lock_cleanup_deadline(owner, deadline)
    return deadline


def _invoke_owned_callback(owner: ai_triage_queue.LockCleanupOwner, callback: Any, args: tuple[Any, ...]) -> Any:
    with ai_triage_queue.bind_lock_cleanup_owner(owner):
        return callback(*args)


class _ProviderCallbackBridge:
    """Run persistence callbacks outside the HTTP-owning processing greenlet."""

    def __init__(
        self: Any,
        parent_owner: ai_triage_queue.LockCleanupOwner | None,
        checkpoint: Any,
        begin_attempt: Any,
    ):
        self.owner = ai_triage_queue.new_lock_cleanup_owner(parent_owner)
        self.children: list[Greenlet] = []
        self._checkpoint_callback = checkpoint
        self._begin_callback = begin_attempt

    def _invoke(self: Any, callback: Any, *args: Any) -> Any:
        parent = gevent.getcurrent()
        child = Greenlet(_invoke_owned_callback, self.owner, callback, args)
        _register_child(parent, child)
        self.children.append(child)
        try:
            child.start()
        except BaseException:
            _unregister_child(parent, child)
            raise

        try:
            # Keep gevent's normal result/exception behavior on success.
            return child.get()
        except BaseException:
            # The caller owns provider HTTP. Cancel the Redis callback and
            # return immediately so generate() can unwind/close that HTTP stack.
            if not child.ready():
                self.owner.cancelled = True
                child.kill(block=False)
            raise

    def checkpoint(self: Any, task_id: str | None, context_id: str | None) -> bool:
        return self._invoke(self._checkpoint_callback, task_id, context_id)

    def begin_attempt(self: Any) -> bool:
        return self._invoke(self._begin_callback)

    def drain_after_provider_unwind(self: Any) -> None:
        """Drain callback children/helpers only after provider HTTP has closed."""
        deadline = _owner_cleanup_deadline(self.owner)
        incomplete, cancellation = _drain_greenlets(self.children, deadline)
        if incomplete:
            raise ai_triage_queue.LockCleanupError("AI provider callback child did not drain before its deadline")
        drained, helper_cancellation = ai_triage_queue.wait_for_lock_cleanup_owner(self.owner, deadline)
        if not drained or ai_triage_queue.pending_lock_helpers(self.owner):
            raise ai_triage_queue.LockCleanupError("AI provider callback Redis cleanup did not drain")
        if failure := ai_triage_queue.pending_lock_cleanup_failure(self.owner):
            raise ai_triage_queue.LockCleanupError(failure)
        if not ai_triage_queue.finish_lock_cleanup_owner(self.owner):
            raise ai_triage_queue.LockCleanupError("AI provider callback cleanup scope remains open")
        if cancellation is not None:
            raise cancellation
        if helper_cancellation is not None:
            raise helper_cancellation


def _drain_greenlets(children: list[Greenlet], deadline: float) -> tuple[bool, BaseException | None]:
    """Wait for a fixed handle set, deferring repeated cancellation until drained."""
    pending_cancellation: BaseException | None = None
    for child in children:
        while not child.ready():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                gevent.sleep(min(0.01, remaining))
            except BaseException as exc:
                if pending_cancellation is None:
                    pending_cancellation = exc
        if child.ready():
            _outstanding_children.discard(child)
        else:
            _outstanding_children.add(child)

    incomplete = any(not child.ready() for child in children)
    return incomplete, pending_cancellation


def _cancel_and_drain_greenlets(children: list[Greenlet], deadline: float) -> BaseException | None:
    # Cancel request/provider work before waiting on any lower-level cleanup
    # helper (especially a Redis renewal) so HTTP contexts close promptly.
    for child in children:
        if not child.ready():
            child.kill(block=False)
    incomplete, cancellation = _drain_greenlets(children, deadline)
    if incomplete:
        raise WorkerShutdownError("AI triage worker child did not drain before its cleanup deadline")
    return cancellation


def _stop_peer_workers(current: Greenlet) -> None:
    global _stopping
    _stopping = True
    _stop_event.set()
    for worker in _workers:
        if isinstance(worker, Greenlet) and worker is not current and not worker.ready():
            worker.kill(block=False)


def _heartbeat_loop(
    run_id: str,
    index: int,
    nonce: str,
    lease_expiry: float,
    deadline_at: float,
    processing: Greenlet,
    cleanup_owner: ai_triage_queue.LockCleanupOwner | None = None,
) -> None:
    interval = max(0.2, config.core.ai.lease_seconds / 3)
    try:
        while True:
            now = time.time()
            margin = max(0.05, min(2.0, config.core.ai.lease_seconds * 0.1))
            wait_time = min(interval, lease_expiry - now - margin)
            if wait_time <= 0 or now >= deadline_at:
                processing.kill(block=False)
                return
            gevent.sleep(wait_time)
            renewed_expiry = _renew_lease(
                run_id,
                index,
                nonce,
                processing,
                timeout=max(0.01, lease_expiry - time.time() - margin),
                cleanup_owner=cleanup_owner,
            )
            if renewed_expiry is None:
                processing.kill(block=False)
                return
            lease_expiry = float(renewed_expiry)
    finally:
        # A parent cancellation must cancel provider/read work immediately. The
        # renewal helper below is drained by this greenlet's own finalizer.
        if not processing.ready():
            processing.kill(block=False)


def _renew_lease(  # noqa: C901
    run_id: str,
    index: int,
    nonce: str,
    processing: Greenlet,
    *,
    timeout: float,
    cleanup_owner: ai_triage_queue.LockCleanupOwner | None = None,
) -> float | None:
    """Run one registered renewal and drain it even if this watchdog is killed."""
    parent = gevent.getcurrent()
    renewal = _start_child(parent, _renewal_with_lock_owner, cleanup_owner, run_id, index, nonce)
    renewed_expiry: float | None = None
    pending_exception: BaseException | None = None
    stop_processing = False
    try:
        try:
            renewed_expiry = renewal.get(timeout=timeout)
        except gevent.Timeout:
            logger.error("Lease renewal exceeded its safety margin; cancelling provider request")  # noqa: TRY400
            stop_processing = True
        except ai_triage_queue.LockCleanupError as exc:
            pending_exception = exc
            stop_processing = True
        except Exception:
            logger.error("Unable to renew AI triage lease; cancelling provider request")  # noqa: TRY400
            stop_processing = True
    except BaseException as exc:
        pending_exception = exc
        stop_processing = True
    finally:
        # Kill HTTP work before waiting on a Redis renewal that may itself be
        # unwinding a cancellation-safe lock finalizer.
        if stop_processing and not processing.ready():
            processing.kill(block=False)
        if not renewal.ready():
            if not processing.ready():
                processing.kill(block=False)
            renewal.kill(block=False)
        cancellation = _cancel_and_drain_greenlets([renewal], _active_cleanup_deadline())
        if pending_exception is None:
            pending_exception = cancellation
        if isinstance(renewal.exception, ai_triage_queue.LockCleanupError) and pending_exception is None:
            pending_exception = renewal.exception

    if pending_exception is not None:
        raise pending_exception
    return None if stop_processing else renewed_expiry


def _emit(run: dict[str, Any] | None) -> None:
    if run:
        ai_triage_service.notify_run(run)


def _finish(
    job: dict[str, Any],
    *,
    state: str,
    reason: str | None = None,
    message: str | None = None,
    transient: bool = False,
) -> None:
    run = ai_triage_queue.finish_item(
        job["run_id"],
        job["index"],
        job["nonce"],
        state=state,
        reason=reason,
        message=message,
        transient=transient,
    )
    _emit(run)


def _process(job: dict[str, Any]) -> None:  # noqa: C901
    run_id = job["run_id"]
    index = job["index"]
    item_id = job["hit_id"]
    nonce = job["nonce"]
    run = job["run"]
    deadline_at = float(job["deadline_at"])
    # Convert the persisted epoch before socket/user/alert reads so all of that
    # work consumes the same immutable per-item budget.
    deadline_monotonic = time.monotonic() + max(0.0, deadline_at - time.time())

    _emit(run)
    user, token, current_run = ai_triage_service.run_owner_and_token(run_id)
    if user is None or not token or current_run is None:
        _finish(
            job,
            state="failed",
            reason="authentication_unavailable",
            message="The initiating Bearer authorization is no longer available",
        )
        return
    if not ai_triage_service.user_can_run_ai_triage(user):
        _finish(job, state="skipped", reason="initiator_access_revoked", message="Initiator is no longer authorized")
        return
    if not ai_triage_queue.lease_is_current(run_id, index, nonce):
        return

    result_item = current_run["results"][index]
    candidate = result_item.get("_candidate")
    if candidate is not None and not ai_triage_service.candidate_is_valid(candidate):
        _finish(job, state="failed", reason="candidate_invalid", message="Saved AI candidate is invalid")
        return
    hit, source_version = ai_triage_service.get_current_hit(item_id, user)
    if hit is None:
        _finish(job, state="skipped", reason="alert_not_accessible", message="Alert is no longer accessible")
        return
    if candidate is not None and ai_triage_service.has_managed_candidate(hit, candidate):
        _finish(job, state="succeeded", reason=None, message="AI triage lead was already saved")
        return
    if not ai_triage_service._eligible_hit(hit):
        _finish(job, state="skipped", reason="alert_no_longer_eligible", message="Alert is no longer eligible")
        return

    prompt = current_run.get("_prompt")
    system_prompt = ai_triage_service.build_system_prompt(prompt if isinstance(prompt, str) else None)
    if time.monotonic() >= deadline_monotonic:
        _finish(job, state="failed", reason="run_deadline_exceeded", message="AI triage exceeded its time limit")
        return

    if candidate is not None:
        pass
    else:
        # Refresh both the actor and the hit at the provider boundary. Role or
        # classification revocation during queue/provider delay is authoritative.
        current_user = ai_triage_service.get_current_user(current_run)
        if current_user is None or not ai_triage_service.user_can_run_ai_triage(current_user):
            _finish(
                job, state="skipped", reason="initiator_access_revoked", message="Initiator is no longer authorized"
            )
            return
        hit, source_version = ai_triage_service.get_current_hit(item_id, current_user)
        if hit is None:
            _finish(job, state="skipped", reason="alert_not_accessible", message="Alert is no longer accessible")
            return
        if not ai_triage_service._eligible_hit(hit):
            _finish(job, state="skipped", reason="alert_no_longer_eligible", message="Alert is no longer eligible")
            return
        user = current_user

        def checkpoint(task_id: str | None, context_id: str | None) -> bool:
            try:
                return ai_triage_queue.checkpoint(run_id, index, nonce, task_id, context_id)
            except ai_triage_queue.LockCleanupError:
                raise
            except Exception as exc:
                raise ai_transport.AITransportError("A2A task checkpoint could not be persisted") from exc

        def begin_attempt() -> bool:
            try:
                attempt = ai_triage_queue.begin_provider_attempt(run_id, index, nonce)
            except ai_triage_queue.LockCleanupError:
                raise
            except Exception as exc:
                raise ai_transport.AITransportError("AI provider attempt could not be persisted") from exc
            if attempt is None:
                return False
            ai_triage_service.notify_run(attempt["run"])
            return True

        bridge = _ProviderCallbackBridge(ai_triage_queue.current_lock_cleanup_owner(), checkpoint, begin_attempt)
        try:
            try:
                timeout = deadline_monotonic - time.monotonic()
                if timeout <= 0:
                    _finish(
                        job,
                        state="failed",
                        reason="run_deadline_exceeded",
                        message="AI triage exceeded its time limit",
                    )
                    return
                with gevent.Timeout(
                    timeout,
                    ai_transport.AITransportError("AI provider exceeded the item deadline", transient=True),
                ):
                    content = ai_transport.generate(
                        config.core.ai,
                        token,
                        system_prompt,
                        ai_triage_service.provider_input(hit),
                        deadline=deadline_monotonic,
                        checkpoint=bridge.checkpoint,
                        begin_attempt=bridge.begin_attempt,
                        resume_task_id=result_item.get("_a2a_task_id"),
                        resume_context_id=result_item.get("_a2a_context_id"),
                    )
            finally:
                # generate() owns and closes the active Response and Session in
                # its own greenlet before callback cleanup is ever awaited.
                bridge.drain_after_provider_unwind()
        except ai_transport.AITransportError as exc:
            if exc.transient:
                # A small bounded delay avoids immediately hammering a provider after
                # a retryable error while keeping the active lease heartbeated.
                _sleep(min(2 ** max(0, int(job["attempts"]) - 1), 4))
            _finish(
                job,
                state="failed",
                reason="provider_transient_error" if exc.transient else "provider_error",
                message=exc.reason,
                transient=exc.transient,
            )
            return
        except ai_triage_queue.LockCleanupError:
            raise
        except Exception:
            # Do not serialize/log exception text: HTTP exceptions may contain
            # provider URLs or other configured secret material.
            logger.error("Unhandled AI triage provider failure for run %s", run_id)  # noqa: TRY400
            _finish(job, state="failed", reason="provider_error", message="AI provider request failed")
            return

        source_version = source_version or "unknown"
        candidate = ai_triage_service.prepare_candidate(content, run_id, source_version)
        if not ai_triage_queue.store_candidate(run_id, index, nonce, candidate):
            return

    if not ai_triage_queue.lease_is_current(run_id, index, nonce):
        return
    write_pending = ai_triage_queue.set_commit_phase(run_id, index, nonce, "write_pending")
    if write_pending is None:
        return
    _emit(write_pending)
    commit_timeout = deadline_monotonic - time.monotonic()
    if commit_timeout <= 0:
        return
    try:
        with gevent.Timeout(
            commit_timeout,
            ai_transport.AITransportError("AI triage exceeded its commit deadline", transient=True),
        ):
            saved, reason = ai_triage_service.save_ai_lead(
                item_id,
                user,
                candidate,
                lease_check=lambda: ai_triage_queue.lease_is_current(run_id, index, nonce),
                user_loader=lambda: ai_triage_service.get_current_user(current_run),
                active_deadline=deadline_monotonic,
            )
    except ai_transport.AITransportError:
        # The durable write intent and candidate survive for read-only recovery.
        return
    if not saved:
        if reason == "lease_lost":
            return
        if reason == "write_reconciliation_pending":
            _emit(ai_triage_queue.defer_candidate_reconciliation(run_id, index, nonce))
            return
        skipped = reason in {"alert_not_accessible", "alert_no_longer_eligible", "initiator_access_revoked"}
        _finish(
            job,
            state="skipped" if skipped else "failed",
            reason=reason,
            message=(
                "Alert changed or is no longer eligible; generated lead was not saved"
                if skipped
                else "Generated lead could not be safely saved"
            ),
        )
        return

    _finish(job, state="succeeded", reason=None, message="AI triage lead saved")


def _process_reconciliation(job: dict[str, Any], *, allow_write: bool) -> None:
    run_id = job["run_id"]
    index = job["index"]
    nonce = job["nonce"]
    deadline_at = float(job["deadline_at"])
    # Recovery never creates a fresh active budget. Translate the persisted
    # alert deadline once, before any blocking reconciliation reads or CAS
    # retries, and pass that immutable monotonic deadline through the service.
    active_deadline = time.monotonic() + max(0.0, deadline_at - time.time())

    state, reason = ai_triage_service.reconcile_candidate(
        job["hit_id"],
        job["candidate"],
        user_loader=lambda: ai_triage_service.get_current_user(job["run"]),
        lease_check=lambda: ai_triage_queue.reconciliation_is_current(run_id, index, nonce),
        write_intent_check=lambda: ai_triage_queue.mark_reconciliation_write_intent(run_id, index, nonce),
        allow_write=allow_write,
        write_intent=bool(job.get("write_intent")),
        active_deadline=active_deadline,
    )
    if state == "stale":
        return
    if state == "pending":
        attempts = int(job["run"]["results"][index].get("_reconcile_attempts", 0))
        updated = ai_triage_queue.defer_reconciliation(run_id, index, nonce, delay_seconds=min(2**attempts, 60))
    else:
        final_state = "succeeded" if state == "saved" else state
        message = {
            "saved": "AI triage lead saved",
            "skipped": "Alert or initiator is no longer eligible for the pending save",
            "failed": "The saved AI candidate is invalid",
            "configuration_unavailable": "AI triage became unavailable before the dossier write",
            "run_deadline_exceeded": "AI triage exceeded its time limit before the dossier write",
            "write_not_submitted": "No dossier write was submitted for this candidate",
        }.get(state, "AI triage reconciliation finished")
        updated = ai_triage_queue.finish_reconciliation(
            run_id,
            index,
            nonce,
            state=final_state,
            reason=reason,
            message=message,
        )
    _emit(updated)


def _process_claimed_job(job: dict[str, Any], parent_cleanup_owner: ai_triage_queue.LockCleanupOwner) -> None:  # noqa: C901
    """Own and drain the processing/watchdog pair before another claim begins."""
    parent = gevent.getcurrent()
    cleanup_owner = ai_triage_queue.new_lock_cleanup_owner(parent_cleanup_owner)
    processing: Greenlet | None = None
    heartbeat: Greenlet | None = None
    started_children: list[Greenlet] = []
    pending_exception: BaseException | None = None
    try:
        # Register both handles before either child can execute user/provider or
        # Redis work; each child in turn registers its renewal descendants.
        processing = Greenlet(_process_with_lock_owner, cleanup_owner, job)
        heartbeat = Greenlet(
            _heartbeat_with_lock_owner,
            cleanup_owner,
            job["run_id"],
            job["index"],
            job["nonce"],
            job["lease_expiry"],
            job["deadline_at"],
            processing,
        )
        _register_child(parent, processing)
        _register_child(parent, heartbeat)
        processing.start()
        started_children.append(processing)
        heartbeat.start()
        started_children.append(heartbeat)
        processing.join()
        if processing.exception and not isinstance(processing.exception, gevent.GreenletExit):
            if isinstance(processing.exception, ai_triage_queue.LockCleanupError):
                pending_exception = processing.exception
            else:
                logger.error("AI triage job exited unexpectedly")  # noqa: TRY400
    except BaseException as exc:
        pending_exception = exc
    finally:
        cleanup_deadline = _owner_cleanup_deadline(cleanup_owner)
        # Cancellation ordering is intentional: cancel provider work first so
        # HTTP/session finalizers run before the heartbeat waits for Redis.
        if processing is not None and processing in started_children and not processing.ready():
            processing.kill(block=False)
        if heartbeat is not None and heartbeat in started_children and not heartbeat.ready():
            heartbeat.kill(block=False)
        children = started_children
        incomplete, cancellation = _drain_greenlets(children, cleanup_deadline)
        for child in (processing, heartbeat):
            if child is not None and child not in started_children:
                _unregister_child(parent, child)
        _prune_finished_children()
        if incomplete:
            raise WorkerShutdownError("AI triage job children did not drain before the cleanup deadline")
        if any(not child.ready() for child in _worker_children.get(parent, set())):
            raise WorkerShutdownError("AI triage job descendants remain after their direct children stopped")
        if cancellation is not None and pending_exception is None:
            pending_exception = cancellation
        if (
            heartbeat is not None
            and heartbeat.exception is not None
            and not isinstance(heartbeat.exception, gevent.GreenletExit)
        ):
            pending_exception = heartbeat.exception
        if processing is not None and isinstance(processing.exception, ai_triage_queue.LockCleanupError):
            pending_exception = processing.exception
        owner_drained, owner_cancellation = ai_triage_queue.wait_for_lock_cleanup_owner(cleanup_owner, cleanup_deadline)
        if not owner_drained:
            raise WorkerShutdownError("AI triage job's lock cleanup chain did not drain")
        if owner_cancellation is not None and pending_exception is None:
            pending_exception = owner_cancellation
        if owner_failure := ai_triage_queue.pending_lock_cleanup_failure(cleanup_owner):
            pending_exception = ai_triage_queue.LockCleanupError(owner_failure)
        if ai_triage_queue.pending_lock_helpers(cleanup_owner):
            pending_exception = ai_triage_queue.LockCleanupError("AI triage job lock helpers remain outstanding")
        if not ai_triage_queue.finish_lock_cleanup_owner(cleanup_owner):
            pending_exception = ai_triage_queue.LockCleanupError("AI triage job cleanup scope remains open")

    if pending_exception is not None:
        raise pending_exception


def _register_child(parent: Any, child: Greenlet) -> None:
    """Attach a not-yet-started Greenlet to its owner before start()."""
    children = _worker_children.setdefault(parent, set())
    children.add(child)

    def forget_finished(completed: Greenlet) -> None:
        children.discard(completed)
        if not children:
            _worker_children.pop(parent, None)

    child.rawlink(forget_finished)


def _unregister_child(parent: Any, child: Greenlet) -> None:
    children = _worker_children.get(parent)
    if children is not None:
        children.discard(child)
        if not children:
            _worker_children.pop(parent, None)


def _halt_worker_pool(current: Any) -> None:
    global _stopping
    _stopping = True
    _stop_event.set()
    for worker in _workers:
        if isinstance(worker, Greenlet) and worker is not current and not worker.ready():
            worker.kill(block=False)


def _prune_finished_children() -> None:
    _outstanding_children.difference_update([child for child in _outstanding_children if child.ready()])
    for parent, children in tuple(_worker_children.items()):
        children.difference_update([child for child in children if child.ready()])
        if not children:
            _worker_children.pop(parent, None)


def run_worker() -> None:
    """Consume work under a root-owned Redis helper scope."""
    cleanup_owner = ai_triage_queue.new_lock_cleanup_owner()
    root = gevent.getcurrent() if _use_gevent else threading.current_thread()
    _worker_cleanup_owners[root] = cleanup_owner
    pending_exception: BaseException | None = None
    try:
        with ai_triage_queue.bind_lock_cleanup_owner(cleanup_owner):
            _run_worker_loop(cleanup_owner)
    except BaseException as exc:
        pending_exception = exc
    finally:
        cleanup_deadline = _owner_cleanup_deadline(cleanup_owner)
        drained, cancellation = ai_triage_queue.wait_for_lock_cleanup_owner(cleanup_owner, cleanup_deadline)
        if not drained:
            _halt_worker_pool(gevent.getcurrent())
            raise WorkerShutdownError("Worker root lock helpers did not drain before its cleanup deadline")
        if cleanup_owner.failure is not None:
            pending_exception = ai_triage_queue.LockCleanupError(cleanup_owner.failure)
        elif cancellation is not None and pending_exception is None:
            pending_exception = cancellation
    if pending_exception is not None:
        raise pending_exception


def _run_worker_loop(cleanup_owner: ai_triage_queue.LockCleanupOwner) -> None:  # noqa: C901
    """Consume jobs forever; one greenlet represents one local worker slot."""
    queue_failures = 0
    while not _stop_event.is_set() and not _stopping:
        try:
            ai_available = ai_triage_service.is_available()
            reconciliation, reconciled_runs = ai_triage_queue.claim_reconciliation()
            latest_by_id = {run["run_id"]: run for run in reconciled_runs}
            for run in latest_by_id.values():
                _emit(run)
            if reconciliation is not None:
                _process_reconciliation(reconciliation, allow_write=ai_available)
                continue

            if not ai_available:
                reconciled, active = ai_triage_queue.fail_pending_when_unavailable()
                latest_by_id = {run["run_id"]: run for run in reconciled}
                for run in latest_by_id.values():
                    _emit(run)
                if not active:
                    # Keep a lightweight provider-free reconciler alive so a
                    # still-enabled peer cannot enqueue a run after this
                    # process starts with AI disabled.
                    _sleep(1.0)
                    continue
                _sleep(1.0)
                continue
            if not _use_gevent:
                _raise_unpatched_runtime()

            job, recovered = ai_triage_queue.claim_next()
            latest_by_id = {run["run_id"]: run for run in recovered}
            for run in latest_by_id.values():
                _emit(run)
            if job is None:
                queue_failures = 0
                _sleep(_POLL_SECONDS)
                continue

            _process_claimed_job(job, cleanup_owner)
            queue_failures = 0
        except (ai_triage_queue.LockCleanupError, WorkerShutdownError) as exc:
            _halt_worker_pool(gevent.getcurrent())
            logger.critical("AI triage worker stopped after incomplete cleanup: %s", type(exc).__name__)
            raise
        except gevent.GreenletExit:
            raise
        except Exception:
            # Queue outages are handled by retrying the poll loop. Keep
            # exception details out of logs in case Redis errors echo payloads.
            logger.error("AI triage worker encountered a queue error")  # noqa: TRY400
            queue_failures = min(queue_failures + 1, 5)
            _sleep(min(2**queue_failures, 30))


def _sleep(seconds: float) -> None:
    if _use_gevent:
        gevent.sleep(seconds)
    else:
        time.sleep(seconds)


def _raise_unpatched_runtime() -> None:
    raise RuntimeError("AI provider execution requires an early-gevent-patched REST process")


def start_workers() -> bool:
    """Start guarded REST workers, independently of the scheduled job system."""
    global _started, _stopping, _use_gevent
    _use_gevent = monkey.is_module_patched("socket")
    if config.core.ai.enabled and not _use_gevent:
        raise RuntimeError(
            "AI Triage is enabled but this server lacks early-gevent-patched sockets; use the Howler server entrypoint"
        )
    if _stopping:
        raise WorkerShutdownError("AI triage workers cannot restart while prior cleanup is incomplete")
    if _started:
        return False
    _started = True
    _stopping = False
    _stop_event.clear()
    worker_count = config.core.ai.max_concurrent_jobs if ai_triage_service.is_available() else 1
    for slot in range(worker_count):
        if _use_gevent:
            worker = Greenlet(run_worker)
            _workers.append(worker)
            worker.start()
        else:
            worker = threading.Thread(target=run_worker, name=f"ai-triage-worker-{slot}", daemon=True)
            _workers.append(worker)
            worker.start()
    logger.info("Started %s AI triage worker consumer(s)", len(_workers))
    return True


def stop_workers(timeout: float = 1.0) -> None:  # noqa: C901
    """Stop roots and drain every owned descendant before declaring shutdown."""
    global _shutdown_deadline, _started, _stopping
    _stopping = True
    _stop_event.set()
    _shutdown_deadline = time.monotonic() + max(0.0, timeout)

    roots = list(_workers)
    for worker in roots:
        if isinstance(worker, Greenlet) and not worker.ready():
            worker.kill(block=False)

    pending_cancellation: BaseException | None = None
    for worker in _workers:
        if isinstance(worker, Greenlet):
            incomplete, cancellation = _drain_greenlets([worker], _shutdown_deadline)
            if cancellation is not None and pending_cancellation is None:
                pending_cancellation = cancellation
            if incomplete:
                raise WorkerShutdownError("AI triage worker root did not stop before the shutdown deadline")
            if worker.exception is not None and not isinstance(worker.exception, gevent.GreenletExit):
                raise WorkerShutdownError(
                    "AI triage worker root exited with an incomplete cleanup error"
                ) from worker.exception
        else:
            while worker.is_alive():
                remaining = _shutdown_deadline - time.monotonic()
                if remaining <= 0:
                    raise WorkerShutdownError("Native AI triage worker did not join before the shutdown deadline")
                try:
                    worker.join(timeout=min(0.01, remaining))
                except BaseException as exc:
                    if pending_cancellation is None:
                        pending_cancellation = exc
            if worker.is_alive():
                raise WorkerShutdownError("Native AI triage worker is still alive after its join deadline")

    _prune_finished_children()
    pending_descendants = [child for child in _outstanding_children if not child.ready()]
    pending_descendants.extend(
        child for children in _worker_children.values() for child in children if not child.ready()
    )
    if pending_descendants:
        raise WorkerShutdownError("AI triage worker descendants or lock helpers remain outstanding")
    for root in roots:
        if cleanup_owner := _worker_cleanup_owners.get(root):
            if ai_triage_queue.pending_lock_helpers(cleanup_owner):
                raise WorkerShutdownError("AI triage worker-owned lock helpers remain outstanding")
            if ai_triage_queue.pending_lock_cleanup_failure(cleanup_owner):
                raise WorkerShutdownError("AI triage worker-owned lock cleanup previously failed")

    for root in roots:
        _worker_cleanup_owners.pop(root, None)
    _workers.clear()
    _started = False
    _stopping = False
    _shutdown_deadline = None
    if pending_cancellation is not None:
        raise pending_cancellation
