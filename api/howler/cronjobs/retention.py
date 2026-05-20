import os
from datetime import datetime, timedelta
from typing import Any

from apscheduler.schedulers.base import BaseScheduler
from apscheduler.triggers.cron import CronTrigger
from pytz import timezone

from howler.common.logging import get_logger
from howler.config import DEBUG, config
from howler.datastore.howler_store import HowlerDatastore

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

    logger.debug("Cleaning analytics with no matching hits")
    _remove_analytics_without_hits(ds)


def _remove_analytics_without_hits(ds: HowlerDatastore):

    matched_analytics = _find_analytics_with_hits(ds)

    ds.analytic.delete_by_search_object({"bool": {"must_not": [{"terms": {"name": matched_analytics}}]}})
    ds.analytic.commit()


def _find_analytics_with_hits(ds: HowlerDatastore) -> list[str]:

    total_analytics = ds.analytic.count("id:*", filters=None)["count"]

    if total_analytics:
        matched_analytics = ds.hit.search(
            "howler.id:*",
            aggregations=[
                (
                    "matched_analytics",
                    {
                        "terms": {
                            "field": "howler.analytic",
                            "size": total_analytics,
                        }
                    },
                )
            ],
        )

        matched_analytic_names = [
            bucket["key"] for bucket in matched_analytics["aggregations"]["matched_analytics"]["buckets"]
        ]

    else:
        matched_analytic_names = []

    return matched_analytic_names


def setup_job(sched: BaseScheduler):
    """Initialize the retention job"""
    if not config.system.retention.enabled:
        if not DEBUG or config.system.type == "production":
            logger.warning("Retention cronjob disabled! This is not recommended for a production settings.")

        return

    logger.debug("Initializing retention cronjob with cron %s", config.system.retention.crontab)

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
