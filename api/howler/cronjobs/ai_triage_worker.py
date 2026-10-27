"""Single bounded consumer for per-alert AI triage jobs."""

import threading
import time
from typing import Any

import gevent
from apscheduler.schedulers.base import BaseScheduler
from gevent import monkey
from gevent.pool import Pool

from howler.common.logging import get_logger
from howler.config import config
from howler.services import ai_transport, ai_triage_service, auth_service

logger = get_logger(__file__)

_consumer: threading.Thread | None = None


class _AIJobTimeout(BaseException):
    """Cooperative timeout for one complete alert job."""


def _process(job: Any) -> None:
    """Process one alert once; failures are logged safely and discarded."""
    if not isinstance(job, dict):
        logger.warning("Discarding malformed AI triage job")
        return
    hit_id = job.get("hit_id")
    uname = job.get("uname")
    encrypted_token = job.get("bearer_token")
    prompt = job.get("prompt")
    if (
        not isinstance(hit_id, str)
        or not hit_id
        or not isinstance(uname, str)
        or not uname
        or not isinstance(encrypted_token, str)
        or (prompt is not None and not isinstance(prompt, str))
    ):
        logger.warning("Discarding malformed AI triage job")
        return

    deadline = time.monotonic() + float(config.core.ai.timeout_seconds)
    try:
        # One absolute budget covers auth, hit reads, provider work, CAS writes,
        # and the normal hit notification refresh. Timeout is BaseException-based
        # so service-level `except Exception` handlers cannot swallow it.
        with gevent.Timeout(max(0.0, deadline - time.monotonic()), _AIJobTimeout):
            user = ai_triage_service.load_current_user(uname)
            if user is None or not ai_triage_service.user_can_run_ai_triage(user):
                logger.info("Discarding AI triage job because its initiator is no longer authorized")
                return
            token = auth_service.decrypt_token(encrypted_token)
            if not token:
                logger.warning("Discarding AI triage job because its credential is unavailable")
                return

            hit, source_version = ai_triage_service.load_current_hit(hit_id, user)
            if hit is None or not ai_triage_service._eligible_hit(hit):
                logger.info("Discarding AI triage job because its alert is no longer eligible or accessible")
                return

            result = ai_transport.generate(
                config.core.ai,
                token,
                ai_triage_service.build_system_prompt(prompt),
                ai_triage_service.provider_input(hit),
                deadline=deadline,
            )
            if not ai_triage_service.save_ai_lead(hit_id, user, result, source_version):
                logger.warning("AI triage result was not saved for alert %s", hit_id)
    except _AIJobTimeout:
        logger.warning("AI triage job timed out for alert %s", hit_id)
    except ai_transport.AITransportError as exc:
        logger.warning("AI triage provider failed for alert %s: %s", hit_id, exc.reason)
    except Exception:
        # Avoid logging exception details: HTTP clients and datastore errors may
        # include credentials, provider content, or infrastructure information.
        logger.error("AI triage job failed for alert %s", hit_id)  # noqa: TRY400


def _consume_one(queue: Any, pool: Pool) -> None:
    """Wait for pool capacity before removing at most one job from Redis."""
    pool.wait_available()
    job = queue.pop(blocking=True, timeout=1)
    if job is not None:
        pool.spawn(_process, job)


def run_worker() -> None:  # pragma: no cover – exercised through bounded processing helpers
    """Consume jobs serially and dispatch no more than the configured pool size."""
    if not ai_triage_service.is_available():
        logger.info("AI triage worker disabled because local configuration is unavailable")
        return

    pool = Pool(config.core.ai.max_concurrent_jobs)
    queue = ai_triage_service.get_queue()
    logger.info("AI triage worker started (max_concurrent_jobs=%d)", pool.size)

    while True:
        try:
            # A killed/lost job is not automatically recovered; operators can
            # enqueue it again manually.
            _consume_one(queue, pool)
        except Exception:
            logger.exception("Unexpected error in AI triage consumer loop")
            gevent.sleep(1)


def setup_job(_scheduler: BaseScheduler) -> None:
    """Start the one AI consumer when the job system discovers this cronjob."""
    global _consumer
    if not ai_triage_service.is_available():
        logger.info("AI triage worker not started because local configuration is unavailable")
        return
    if not monkey.is_module_patched("socket"):
        raise RuntimeError("AI triage requires the early-gevent-patched Howler server entrypoint")
    if _consumer is not None and _consumer.is_alive():
        return
    _consumer = threading.Thread(target=run_worker, name="ai-triage-consumer", daemon=True)
    _consumer.start()
