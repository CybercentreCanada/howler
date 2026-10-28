"""Concurrent consumers for per-alert AI triage jobs."""

import threading
import time
from typing import Any, cast

from apscheduler.schedulers.base import BaseScheduler

from howler.actions.ai_triage import ROLES
from howler.common.logging import get_logger
from howler.config import config
from howler.services import ai_transport, ai_triage_service, auth_service, hit_service

logger = get_logger(__file__)

_threads: dict[int, threading.Thread] = {}


def _process(job: Any) -> None:
    """Process one alert once; failures are logged safely and discarded."""
    hit_id = "unknown"

    try:
        hit_id = job["hit_id"]
        uname = job["uname"]
        encrypted_token = job["bearer_token"]
        prompt = job["prompt"]
        deadline = time.monotonic() + config.core.ai.timeout_seconds

        user = ai_triage_service.load_current_user(uname)
        if user is None or not user.is_active or not (set(ROLES) | {"admin"}) & set(user.type):
            logger.info("Discarding AI triage job because its initiator is no longer authorized")
            return

        token = auth_service.decrypt_token(encrypted_token)
        hit, _version = hit_service.get_hit(hit_id, as_odm=True, version=True, user=user)
        if hit is None or not ai_triage_service._eligible_hit(hit):
            logger.info("Discarding AI triage job because its alert is no longer eligible or accessible")
            return

        result = ai_transport.generate(
            config.core.ai,
            cast(str, token),
            ai_triage_service.build_system_prompt(prompt),
            ai_triage_service.provider_input(hit),
            deadline=deadline,
        )
        if not ai_triage_service.save_ai_lead(hit_id, user, result):
            logger.warning("AI triage result was not saved for alert %s", hit_id)
    except ai_transport.AITransportError as exc:
        logger.warning("AI triage provider failed for alert %s: %s", hit_id, exc.reason)
    except Exception:
        # Exception messages may contain credentials, provider content, or infrastructure details.
        logger.error("AI triage job failed for alert %s", hit_id)  # noqa: TRY400


def run_worker() -> None:  # pragma: no cover – exercised through job processing helpers
    """Consume jobs from the persistent queue until the process exits."""
    queue = ai_triage_service.get_queue()
    while True:
        try:
            job = queue.pop(blocking=True, timeout=1)
            if job:
                _process(job)
        except Exception:
            logger.exception("Unexpected error in AI triage consumer loop")


def setup_job(_scheduler: BaseScheduler) -> None:
    """Start the configured number of daemon consumers when AI triage is available."""
    if not ai_triage_service.is_available():
        logger.info("AI triage worker not started because local configuration is unavailable")
        return

    for index in range(config.core.ai.max_concurrent_jobs):
        thread = _threads.get(index)
        if thread is not None and thread.is_alive():
            continue

        thread = threading.Thread(target=run_worker, name=f"ai-triage-consumer-{index}", daemon=True)
        thread.start()
        _threads[index] = thread
        logger.info("AI triage consumer thread started (%d/%d)", index + 1, config.core.ai.max_concurrent_jobs)
