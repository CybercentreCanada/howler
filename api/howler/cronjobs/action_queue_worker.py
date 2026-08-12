"""Action queue worker cronjob — starts per-trigger action queue consumer threads.

Auto-discovered by ``howler.cronjobs.setup_jobs`` when ``HWL_USE_JOB_SYSTEM``
is enabled.  Instead of scheduling a periodic APScheduler job, this module
starts a long-running daemon thread per trigger type that drains its
dedicated action queue.
"""

import threading

from apscheduler.schedulers.base import BaseScheduler

from howler.common.logging import get_logger
from howler.config import config
from howler.odm.models.action import VALID_TRIGGERS
from howler.services.action_service import _get_action_queue, process_action_batch

logger = get_logger(__file__)

_threads: dict[str, threading.Thread] = {}

BATCH_SIZE: int = config.system.action_queue.batch_size
BATCH_TIMEOUT: int = config.system.action_queue.batch_timeout


def run_worker(trigger: str) -> None:  # pragma: no cover – long-running loop, tested via process_action_batch
    """Block on the action queue for *trigger* and process batches.

    Accumulates up to ``BATCH_SIZE`` items or flushes after ``BATCH_TIMEOUT``
    seconds, whichever comes first.
    """
    if not config.system.action_queue.enabled:
        logger.info("Action queue worker disabled by configuration, not starting for trigger=%s", trigger)
        return

    queue = _get_action_queue(trigger)
    logger.info(
        "Action queue worker started for trigger=%s (batch_size=%d, timeout=%ds)",
        trigger,
        BATCH_SIZE,
        BATCH_TIMEOUT,
    )

    batch: list[dict] = []

    while True:
        try:
            item = queue.pop(blocking=True, timeout=BATCH_TIMEOUT)

            if item is not None:
                batch.append(item)

            if len(batch) % 10 == 0 or len(batch) >= BATCH_SIZE:
                logger.info("Batch size: %s", len(batch))

            if len(batch) >= BATCH_SIZE or (item is None and batch):
                finalized_batch = [*batch]
                batch = []
                logger.debug("Processing action batch of %d item(s) for trigger=%s", len(batch), trigger)
                try:
                    process_action_batch(trigger, finalized_batch)
                    logger.info("Action batch complete: %d item(s) processed for trigger=%s", len(batch), trigger)
                except Exception:
                    logger.exception("Error processing action batch for trigger=%s", trigger)
        except Exception:
            logger.exception("Unexpected error in action queue worker loop for trigger=%s", trigger)


def setup_job(sched: BaseScheduler):
    """Start an action queue worker thread per trigger type if the action queue is enabled."""
    global _threads

    if not config.system.action_queue.enabled:
        logger.info("Action queue worker disabled by configuration")
        return

    for trigger in VALID_TRIGGERS:
        if trigger in _threads and _threads[trigger].is_alive():
            logger.debug("Action queue worker thread for trigger=%s already running", trigger)
            continue

        thread = threading.Thread(target=run_worker, args=(trigger,), name=f"action-queue-{trigger}", daemon=True)
        thread.start()
        _threads[trigger] = thread
        logger.info("Action queue worker thread started for trigger=%s", trigger)
