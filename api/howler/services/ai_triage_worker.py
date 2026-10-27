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
_stop_event = threading.Event()
_POLL_SECONDS = 0.5
_CHILD_CLEANUP_TIMEOUT = 2.0


class WorkerShutdownError(RuntimeError):
    """A worker did not stop within its bounded shutdown deadline."""


def _heartbeat_loop(
    run_id: str,
    index: int,
    nonce: str,
    lease_expiry: float,
    deadline_at: float,
    processing: Greenlet,
) -> None:
    """Renew a live worker lease and cancel provider work when ownership is lost."""
    interval = max(0.2, config.core.ai.lease_seconds / 3)
    while not processing.ready():
        now = time.time()
        margin = max(0.05, min(2.0, config.core.ai.lease_seconds * 0.1))
        wait_time = min(interval, lease_expiry - now - margin)
        if wait_time <= 0 or now >= deadline_at:
            processing.kill(block=False)
            return
        gevent.sleep(wait_time)
        if processing.ready():
            return
        remaining = lease_expiry - time.time() - margin
        if remaining <= 0:
            processing.kill(block=False)
            return
        try:
            with gevent.Timeout(remaining):
                renewed_expiry = ai_triage_queue.heartbeat(run_id, index, nonce)
        except gevent.Timeout:
            logger.error("Lease renewal exceeded its safety margin; cancelling provider request")  # noqa: TRY400
            processing.kill(block=False)
            return
        except Exception:
            logger.error("Unable to renew AI triage lease; cancelling provider request")  # noqa: TRY400
            processing.kill(block=False)
            return
        if renewed_expiry is None:
            processing.kill(block=False)
            return
        lease_expiry = float(renewed_expiry)


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
        job["run_id"], job["index"], job["nonce"], state=state, reason=reason, message=message, transient=transient
    )
    _emit(run)


def _process(job: dict[str, Any]) -> None:  # noqa: C901
    run_id = job["run_id"]
    index = job["index"]
    item_id = job["hit_id"]
    nonce = job["nonce"]
    deadline_at = float(job["deadline_at"])
    deadline = time.monotonic() + max(0.0, deadline_at - time.time())

    _emit(job["run"])
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
    if candidate is not None:
        if not ai_triage_service.candidate_is_valid(candidate):
            _finish(job, state="failed", reason="candidate_invalid", message="Saved AI candidate is invalid")
            return
        hit, source_version = ai_triage_service.get_current_hit(item_id, user)
        if hit is None:
            _finish(job, state="skipped", reason="alert_not_accessible", message="Alert is no longer accessible")
            return
        if ai_triage_service.has_managed_candidate(hit, candidate):
            _finish(job, state="succeeded", message="AI triage lead was already saved")
            return
        if not ai_triage_service._eligible_hit(hit):
            _finish(job, state="skipped", reason="alert_no_longer_eligible", message="Alert is no longer eligible")
            return
    else:
        user = ai_triage_service.get_current_user(current_run)
        if user is None or not ai_triage_service.user_can_run_ai_triage(user):
            _finish(
                job, state="skipped", reason="initiator_access_revoked", message="Initiator is no longer authorized"
            )
            return
        hit, source_version = ai_triage_service.get_current_hit(item_id, user)
        if hit is None:
            _finish(job, state="skipped", reason="alert_not_accessible", message="Alert is no longer accessible")
            return
        if not ai_triage_service._eligible_hit(hit):
            _finish(job, state="skipped", reason="alert_no_longer_eligible", message="Alert is no longer eligible")
            return
        prompt = current_run.get("_prompt")
        system_prompt = ai_triage_service.build_system_prompt(prompt if isinstance(prompt, str) else None)
        if time.monotonic() >= deadline:
            _finish(job, state="failed", reason="run_deadline_exceeded", message="AI triage exceeded its time limit")
            return

        def checkpoint(task_id: str | None, context_id: str | None) -> bool:
            try:
                return ai_triage_queue.checkpoint(run_id, index, nonce, task_id, context_id)
            except Exception as exc:
                raise ai_transport.AITransportError("A2A task checkpoint could not be persisted") from exc

        def begin_attempt() -> bool:
            try:
                attempt = ai_triage_queue.begin_provider_attempt(run_id, index, nonce)
            except Exception as exc:
                raise ai_transport.AITransportError("AI provider attempt could not be persisted") from exc
            if attempt is None:
                return False
            ai_triage_service.notify_run(attempt["run"])
            return True

        try:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                _finish(
                    job, state="failed", reason="run_deadline_exceeded", message="AI triage exceeded its time limit"
                )
                return
            with gevent.Timeout(
                remaining, ai_transport.AITransportError("AI provider exceeded the item deadline", transient=True)
            ):
                content = ai_transport.generate(
                    config.core.ai,
                    token,
                    system_prompt,
                    ai_triage_service.provider_input(hit),
                    deadline=deadline,
                    checkpoint=checkpoint,
                    begin_attempt=begin_attempt,
                    resume_task_id=result_item.get("_a2a_task_id"),
                    resume_context_id=result_item.get("_a2a_context_id"),
                )
        except ai_transport.AITransportError as exc:
            if exc.transient:
                _sleep(min(2 ** max(0, int(job["attempts"]) - 1), 4))
            _finish(
                job,
                state="failed",
                reason="provider_transient_error" if exc.transient else "provider_error",
                message=exc.reason,
                transient=exc.transient,
            )
            return
        except Exception:
            logger.error("Unhandled AI triage provider failure for run %s", run_id)  # noqa: TRY400
            _finish(job, state="failed", reason="provider_error", message="AI provider request failed")
            return

        candidate = ai_triage_service.prepare_candidate(content, run_id, source_version or "unknown")
        if not ai_triage_queue.store_candidate(run_id, index, nonce, candidate):
            return

    if not ai_triage_queue.lease_is_current(run_id, index, nonce):
        return
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return
    try:
        with gevent.Timeout(
            remaining, ai_transport.AITransportError("AI triage exceeded its commit deadline", transient=True)
        ):
            saved, reason = ai_triage_service.save_ai_lead(
                item_id,
                user,
                candidate,
                lease_check=lambda: ai_triage_queue.lease_is_current(run_id, index, nonce),
                user_loader=lambda: ai_triage_service.get_current_user(current_run),
                active_deadline=deadline,
            )
    except ai_transport.AITransportError:
        return
    if not saved:
        if reason == "lease_lost":
            return
        if reason == "write_reconciliation_pending":
            _sleep(min(2 ** max(0, int(job["attempts"]) - 1), 4))
            _finish(
                job,
                state="failed",
                reason="save_transient_error",
                message="Generated lead could not be saved; retrying",
                transient=True,
            )
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

    _finish(job, state="succeeded", message="AI triage lead saved")


def _process_claimed_job(job: dict[str, Any]) -> None:
    """Run one item alongside its lease heartbeat, then stop both greenlets."""
    processing = Greenlet(_process, job)
    heartbeat = Greenlet(
        _heartbeat_loop,
        job["run_id"],
        job["index"],
        job["nonce"],
        job["lease_expiry"],
        job["deadline_at"],
        processing,
    )
    children = [processing, heartbeat]
    try:
        processing.start()
        heartbeat.start()
        processing.join()
        if processing.exception and not isinstance(processing.exception, gevent.GreenletExit):
            logger.error("AI triage job exited unexpectedly")  # noqa: TRY400
    finally:
        for child in children:
            if child.started and not child.ready():
                child.kill(block=False)
        end = time.monotonic() + _CHILD_CLEANUP_TIMEOUT
        for child in children:
            if child.started:
                child.join(timeout=max(0.0, end - time.monotonic()))
        if any(child.started and not child.ready() for child in children):
            raise WorkerShutdownError("AI triage job did not stop before its cleanup deadline")


def _halt_worker_pool(current: Any) -> None:
    global _stopping
    _stopping = True
    _stop_event.set()
    for worker in _workers:
        if isinstance(worker, Greenlet) and worker is not current and not worker.ready():
            worker.kill(block=False)


def run_worker() -> None:
    """Consume work until the process requests a stop."""
    _run_worker_loop()


def _run_worker_loop() -> None:  # noqa: C901
    queue_failures = 0
    while not _stop_event.is_set() and not _stopping:
        try:
            if not ai_triage_service.is_available():
                changed, _active = ai_triage_queue.fail_pending_when_unavailable()
                for run in {run["run_id"]: run for run in changed}.values():
                    _emit(run)
                _sleep(1.0)
                continue
            if not _use_gevent:
                _raise_unpatched_runtime()
            job, recovered = ai_triage_queue.claim_next()
            for run in {run["run_id"]: run for run in recovered}.values():
                _emit(run)
            if job is None:
                queue_failures = 0
                _sleep(_POLL_SECONDS)
                continue
            _process_claimed_job(job)
            queue_failures = 0
        except WorkerShutdownError as exc:
            _halt_worker_pool(gevent.getcurrent())
            logger.critical("AI triage worker stopped before cleanup completed: %s", type(exc).__name__)
            raise
        except gevent.GreenletExit:
            raise
        except Exception:
            logger.error("AI triage worker encountered a queue error")  # noqa: TRY400
            queue_failures = min(queue_failures + 1, 5)
            _sleep(min(2**queue_failures, 30))


def _sleep(seconds: float) -> None:
    gevent.sleep(seconds) if _use_gevent else time.sleep(seconds)


def _raise_unpatched_runtime() -> None:
    raise RuntimeError("AI provider execution requires an early-gevent-patched REST process")


def start_workers() -> bool:
    """Start guarded REST workers independently of the scheduled job system."""
    global _started, _stopping, _use_gevent
    _use_gevent = monkey.is_module_patched("socket")
    if config.core.ai.enabled and not _use_gevent:
        raise RuntimeError(
            "AI Triage is enabled but this server lacks early-gevent-patched sockets; use the Howler server entrypoint"
        )
    if _stopping:
        raise WorkerShutdownError("AI triage workers cannot restart while shutdown is incomplete")
    if _started:
        return False
    _started, _stopping = True, False
    _stop_event.clear()
    count = config.core.ai.max_concurrent_jobs if ai_triage_service.is_available() else 1
    for slot in range(count):
        worker = (
            Greenlet(run_worker)
            if _use_gevent
            else threading.Thread(target=run_worker, name=f"ai-triage-worker-{slot}", daemon=True)
        )
        _workers.append(worker)
        worker.start()
    logger.info("Started %s AI triage worker consumer(s)", len(_workers))
    return True


def stop_workers(timeout: float = 1.0) -> None:
    """Stop all consumer roots within one bounded shutdown interval."""
    global _started, _stopping
    _stopping = True
    _stop_event.set()
    deadline = time.monotonic() + max(0.0, timeout)
    workers = list(_workers)
    for worker in workers:
        if isinstance(worker, Greenlet):
            worker.join(timeout=max(0.0, deadline - time.monotonic()))
            if not worker.ready():
                worker.kill(block=False)
                worker.join(timeout=max(0.0, deadline - time.monotonic()))
            if not worker.ready():
                raise WorkerShutdownError("AI triage worker did not stop before the shutdown deadline")
        else:
            worker.join(timeout=max(0.0, deadline - time.monotonic()))
            if worker.is_alive():
                raise WorkerShutdownError("Native AI triage worker did not join before the shutdown deadline")
    _workers.clear()
    _started = False
    _stopping = False
