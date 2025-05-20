import os
from datetime import datetime, timedelta
from typing import Any

from apscheduler.schedulers.base import BaseScheduler
from apscheduler.triggers.cron import CronTrigger
from pytz import timezone

from howler.common.logging import get_logger
from howler.config import DEBUG, config

logger = get_logger(__file__)


def execute():
    """Delete any hits older than the configured time"""
    from howler.common.loader import datastore

    delta_kwargs = {str(config.system.retention.limit_unit): config.system.retention.limit_amount}

    cutoff = (datetime.now() - timedelta(**delta_kwargs)).strftime("%Y-%m-%d")

    logger.debug("Removing hits older than %s", cutoff)

    ds = datastore()

    ds.hit.delete_by_query(f"event.created:{{* TO {cutoff}}} OR howler.expiry:{{* TO now}}")

    ds.hit.commit()

    logger.debug("Deletion complete")


def setup_job(sched: BaseScheduler):
    """Initialize the retention job"""
    if not config.system.retention.enabled:
        if not DEBUG or config.system.type == "production":
            logger.warning("Retention cronjob disabled! This is not recommended for a production settings.")

        return

    logger.debug(f"Initializing retention cronjob with cron {config.system.retention.crontab}")

    if DEBUG:
        _kwargs: dict[str, Any] = {"next_run_time": datetime.now()}
    else:
        _kwargs = {}

    if sched.get_job("retention"):
        logger.debug("Retention job already running!")
        return

    sched.add_job(
        id="retention",
        func=execute,
        trigger=CronTrigger.from_crontab(
            config.system.retention.crontab, timezone=timezone(os.getenv("SCHEDULER_TZ", "America/Toronto"))
        ),
        **_kwargs,
    )
    logger.debug("Initialization complete")
