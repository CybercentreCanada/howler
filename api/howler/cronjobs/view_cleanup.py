import os
from datetime import datetime
from typing import Any, List

from apscheduler.schedulers.base import BaseScheduler
from apscheduler.triggers.cron import CronTrigger
from pytz import timezone

from howler.common.logging import get_logger
from howler.config import DEBUG, config

logger = get_logger(__file__)


def execute():
    """Delete any pinned views that no longer exist"""
    from howler.common.loader import datastore

    # Initialize datastore
    ds = datastore()
    # fetch the first result from user ds (needed to initialize total)
    result = ds.user.search("*:*", rows=250, fl="*")
    total_user_count = result["total"]
    user_list: List[Any] = result["items"]
    # Do the same thing for the views
    result = ds.view.search("*:*", rows=250)
    total_view_count = result["total"]
    view_list: List[Any] = result["items"]
    view_ids: List[str] = []

    # Collect all views
    while len(view_list) < total_view_count:
        view_list.extend(ds.view.search("*:*", rows=250, offset=len(user_list)))

    # Collect all users
    while len(user_list) < total_user_count:
        user_list.extend(ds.user.search("*:*", rows=250, offset=len(user_list)))

    for view in view_list:
        view_ids.append(view["view_id"])

    # Iterate over each user to see if the dashboard contains invalid entries (deleted views)
    for user in user_list:
        valid_entries = []
        # No views/analytics saved to the dashboard? Skip it
        if user["dashboard"] == []:
            continue
        for dashboard_entry in user["dashboard"]:
            if dashboard_entry["type"] != "view" or (
                dashboard_entry["type"] == "view" and dashboard_entry["entry_id"] in view_ids
            ):
                valid_entries.append(dashboard_entry)
        # If the length of valid entries is less than the current dashboard, one or more pins are invalid
        if len(valid_entries) < len(user["dashboard"]):
            # set the user dashboard to valid entries
            user["dashboard"] = valid_entries
            # update the user
            ds.user.save(user["uname"], user)


def setup_job(sched: BaseScheduler):
    """Initialize the view cleanup job"""
    if not config.system.view_cleanup.enabled:
        if not DEBUG or config.system.type == "production":
            logger.warning("view cleanup cronjob disabled! This is not recommended for a production settings.")

        return

    logger.debug(f"Initializing view cleanup cronjob with cron {config.system.view_cleanup.crontab}")

    if DEBUG:
        _kwargs: dict[str, Any] = {"next_run_time": datetime.now()}
    else:
        _kwargs = {}

    if sched.get_job("view_cleanup"):
        logger.debug("view cleanup job already running!")
        return

    sched.add_job(
        id="view_cleanup",
        func=execute,
        trigger=CronTrigger.from_crontab(
            config.system.view_cleanup.crontab, timezone=timezone(os.getenv("SCHEDULER_TZ", "America/Toronto"))
        ),
        **_kwargs,
    )
    logger.debug("Initialization complete")
