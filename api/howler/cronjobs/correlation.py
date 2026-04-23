"""Correlation cronjob — starts the correlation worker thread.

Auto-discovered by ``howler.cronjobs.setup_jobs`` when ``HWL_USE_JOB_SYSTEM``
is enabled.  Instead of scheduling a periodic APScheduler job, this module
starts a long-running daemon thread that drains the ingestion queue.
"""

import threading

from apscheduler.schedulers.base import BaseScheduler

from howler.common.logging import get_logger
from howler.odm.models.config import config

logger = get_logger(__file__)

_thread: threading.Thread | None = None


def setup_job(sched: BaseScheduler):
    """Start the correlation worker thread if correlation is enabled."""
    global _thread

    if not config.system.correlation.enabled:
        logger.info("Correlation worker disabled by configuration")
        return

    if _thread is not None and _thread.is_alive():
        logger.debug("Correlation worker thread already running")
        return

    from howler.services.correlation_service import run_worker

    _thread = threading.Thread(target=run_worker, name="correlation-worker", daemon=True)
    _thread.start()
    logger.info("Correlation worker thread started")
