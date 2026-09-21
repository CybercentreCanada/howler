import os
from datetime import datetime, timedelta
from typing import Any

from apscheduler.schedulers.base import BaseScheduler
from apscheduler.triggers.cron import CronTrigger
from pytz import timezone

from howler.common.logging import get_logger
from howler.config import DEBUG, config
from howler.datastore.howler_store import HowlerDatastore
from howler.datastore.operations import OdmHelper
from howler.odm.models.case import CaseItemTypes
from howler.odm.models.hit import Hit
from howler.services import case_service

logger = get_logger(__file__)
hit_helper = OdmHelper(Hit)


def execute():
    """Delete any hits older than the configured time"""
    from howler.common.loader import datastore

    delta_kwargs = {str(config.system.retention.limit_unit): config.system.retention.limit_amount}

    cutoff = (datetime.now() - timedelta(**delta_kwargs)).strftime("%Y-%m-%d")

    logger.debug("Removing hits older than %s", cutoff)

    ds = datastore()

    _delete_matching_hits(ds, f"event.created:{{* TO {cutoff}}} OR howler.expiry:{{* TO now}}")

    logger.debug("Deletion complete")

    _execute_rules(ds)

    logger.debug("Cleaning analytics with no matching hits")
    _remove_analytics_without_hits(ds)


def _execute_rules(ds: HowlerDatastore) -> None:
    """Execute dynamic retention rules from config.

    Iterates each enabled rule, computes its cutoff date, and deletes
    hits that match the rule's query and are older than the cutoff.
    Errors for individual rules are logged and skipped so that
    remaining rules still execute. Emits a structured result log
    for each rule execution.

    Note: Rules are independent. If multiple rules match the same hit,
    the hit is deleted by whichever rule runs first; subsequent matching
    rules will no-op against the already-deleted document.

    Args:
        ds: Active HowlerDatastore instance.
    """
    rules = config.system.retention.rules
    if not rules:
        return

    logger.info("Processing dynamic retention rules:")

    for rule in rules:
        result = {}

        if not rule.enabled:
            logger.debug("Skipping disabled retention rule '%s'", rule.name)
            result = {"rule": rule.name, "status": "skipped", "reason": "disabled"}
            logger.info("Rule result: '%s'", result)
            continue

        delta_kwargs = {str(rule.limit_unit): rule.limit_amount}
        cutoff_dt = datetime.now(tz=timezone("UTC")) - timedelta(**delta_kwargs)
        cutoff = cutoff_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        combined_query = f"({rule.query}) AND event.created:{{* TO {cutoff}}}"

        logger.debug(
            "Executing retention rule '%s': query=%s cutoff=%s",
            rule.name,
            rule.query,
            cutoff,
        )

        try:
            count = ds.hit.count(combined_query, filters=None).get("count", -1)
            _delete_matching_hits(ds, combined_query)
            logger.debug("Retention rule '%s' complete", rule.name)
            result = {"rule": rule.name, "status": "ok", "deleted": count, "cutoff": cutoff}
        except Exception:
            logger.error(
                "Retention rule '%s' failed — skipping. query=%s",
                rule.name,
                combined_query,
                exc_info=True,
            )
            result = {"rule": rule.name, "status": "error", "query": combined_query}

        logger.info("Rule result: '%s'", result)


def _delete_matching_hits(ds: HowlerDatastore, query: str) -> None:
    """Remove matching hits after cleaning their references from cases and hits."""
    hit_ids = {hit.howler.id for hit in ds.hit.stream_search(query)}

    if hit_ids:
        id_query = " OR ".join(hit_ids)
        for case in ds.case.stream_search(f"items.value:({id_query})"):
            item_ids = [item.id for item in case.items if item.type == CaseItemTypes.HIT and item.value in hit_ids]
            if item_ids:
                case_service.remove_case_items(case, item_ids)

        ds.hit.update_by_query(
            f"howler.related:({id_query})",
            [hit_helper.list_remove("howler.related", hit_id, silent=True) for hit_id in hit_ids],
        )

    ds.hit.delete_by_query(query)
    ds.hit.commit()


def _remove_analytics_without_hits(ds: HowlerDatastore):
    matched_analytics = _find_analytics_with_hits(ds)

    if matched_analytics is not None:
        ds.analytic.delete_by_search_object(
            {
                "bool": {
                    "filter": [
                        {
                            "bool": {
                                "must_not": [
                                    {"exists": {"field": "rule"}},
                                    {"exists": {"field": "rule_type"}},
                                ]
                            }
                        }
                    ],
                    "must_not": [{"terms": {"name": matched_analytics}}],
                }
            }
        )
        ds.analytic.commit()
    else:
        logger.warning(
            "Aggregation search for matched analytics did not run or returned no results. "
            "There is likely an issue with the query. Skipping cleanup."
        )


def _find_analytics_with_hits(ds: HowlerDatastore) -> list[str] | None:
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
            rows=0,
        )

        if "matched_analytics" in matched_analytics["aggregations"]:
            matched_analytic_names = [
                bucket["key"] for bucket in matched_analytics["aggregations"]["matched_analytics"]["buckets"]
            ]
        else:
            return None

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


if __name__ == "__main__":
    execute()
