import hashlib
import json
import os
import random
import re
import sys
from datetime import datetime
from typing import Any, Optional

from apscheduler.schedulers.base import BaseScheduler
from apscheduler.triggers.cron import CronTrigger
from pytz import timezone
from sigma.backends.elasticsearch import LuceneBackend
from sigma.rule import SigmaRule
from yaml.scanner import ScannerError

from howler.common.exceptions import HowlerValueError
from howler.common.loader import datastore
from howler.common.logging import get_logger
from howler.config import DEBUG, HWL_ENABLE_RULES
from howler.datastore.collection import ESCollection
from howler.datastore.operations import OdmHelper, OdmUpdateOperation
from howler.odm.models.analytic import Analytic
from howler.odm.models.hit import Hit
from howler.odm.models.howler_data import HitOperationType

logger = get_logger(__file__)
hit_helper = OdmHelper(Hit)

__scheduler_instance: Optional[BaseScheduler] = None


def create_correlated_bundle(rule: Analytic, query: str, correlated_hits: list[Hit]):
    "Create a bundle based on the results of an analytic"
    # We'll create a hash using the hashes of the children, and the analytic ID/current time
    bundle_hash = hashlib.sha256()
    bundle_hash.update(rule.analytic_id.encode())
    bundle_hash.update(query.replace("now", datetime.now().isoformat()).encode())
    for match in correlated_hits:
        bundle_hash.update(match.howler.hash.encode())

    hashed = bundle_hash.hexdigest()

    # If a matching bundle exists already, just reused it (likely only ever lucene specific)
    existing_result = datastore().hit.search(f"howler.hash:{hashed}", rows=1)
    if existing_result["total"] > 0:
        logger.debug(f"Rule hash {hashed} exists - skipping create")
        return existing_result["items"][0]

    child_ids = [match.howler.id for match in correlated_hits]

    correlated_bundle = Hit(
        {
            "howler.analytic": rule.name,
            "howler.detection": "Rule",
            "howler.score": 0.0,
            "howler.hash": hashed,
            "howler.is_bundle": True,
            "howler.hits": child_ids,
            "howler.data": [
                json.dumps(
                    {
                        "raw": rule.rule,
                        "sanitized": query,
                    }
                )
            ],
            "event.created": "NOW",
            "event.kind": "alert",
            "event.module": rule.rule_type,
            "event.provider": "howler",
            "event.reason": f"Children match {query}",
            "event.type": ["info"],
        }
    )
    correlated_bundle.event.id = correlated_bundle.howler.id

    datastore().hit.save(correlated_bundle.howler.id, correlated_bundle)

    if len(child_ids) > 0:
        datastore().hit.update_by_query(
            f"howler.id:({' OR '.join(child_ids)})",
            [
                hit_helper.list_add(
                    "howler.bundles",
                    correlated_bundle.howler.id,
                    if_missing=True,
                ),
                OdmUpdateOperation(
                    ESCollection.UPDATE_APPEND,
                    "howler.log",
                    {
                        "timestamp": "NOW",
                        "key": "howler.bundles",
                        "explanation": f"This hit was correlated by the analytic '{rule.name}'.",
                        "new_value": correlated_bundle.howler.id,
                        "previous_value": "None",
                        "type": HitOperationType.APPENDED,
                        "user": "Howler",
                    },
                ),
            ],
        )

    return correlated_bundle


def create_executor(rule: Analytic):  # noqa: C901
    "Create a cronjob for a given analytic"

    def execute():  # noqa: C901
        "Execute the rule"
        try:
            if not rule.rule or not rule.rule_type:
                logger.error("Invalid rule %s! Skipping", rule.analytic_id)
                return

            logger.info(
                "Executing rule %s (%s)",
                rule.name,
                rule.analytic_id,
            )

            correlated_hits: Optional[list[Hit]] = None

            if rule.rule_type in ["lucene", "sigma"]:
                if rule.rule_type == "lucene":
                    query = re.sub(r"\n+", " ", re.sub(r"#.+", "", rule.rule)).strip()
                else:
                    try:
                        sigma_rule = SigmaRule.from_yaml(rule.rule)
                    except ScannerError as e:
                        raise HowlerValueError(
                            f"Error when parsing yaml: {e.problem} {e.problem_mark}",
                            cause=e,
                        )

                    es_collection = datastore().hit
                    lucene_queries = LuceneBackend(index_names=[es_collection.index_name]).convert_rule(sigma_rule)

                    query = " AND ".join([f"({q})" for q in lucene_queries])

                num_hits = datastore().hit.search(query, rows=1)["total"]
                if num_hits > 0:
                    bundle = create_correlated_bundle(rule, query, [])
                    datastore().hit.update_by_query(
                        f"({query}) AND -howler.bundles:{bundle.howler.id}",
                        [
                            hit_helper.list_add(
                                "howler.bundles",
                                bundle.howler.id,
                                if_missing=True,
                            ),
                            OdmUpdateOperation(
                                ESCollection.UPDATE_APPEND,
                                "howler.log",
                                {
                                    "timestamp": "NOW",
                                    "key": "howler.bundles",
                                    "explanation": f"This hit was correlated by the analytic '{rule.name}'.",
                                    "new_value": bundle.howler.id,
                                    "previous_value": "None",
                                    "type": HitOperationType.APPENDED,
                                    "user": "Howler",
                                },
                            ),
                        ],
                    )

                    datastore().hit.commit()

                    child_hits: list[Hit] = datastore().hit.search(
                        f"howler.bundles:{bundle.howler.id}", rows=1000, fl="howler.id"
                    )["items"]
                    datastore().hit.update_by_query(
                        f"howler.id:{bundle.howler.id}",
                        [hit_helper.list_add("howler.hits", hit.howler.id, if_missing=True) for hit in child_hits],
                    )

            elif rule.rule_type == "eql":
                query = rule.rule

                result = datastore().hit.raw_eql_search(query, rows=25, fl=",".join(Hit.flat_fields().keys()))

                if len(result["sequences"]) > 0:
                    for sequence in result["sequences"]:
                        if len(sequence) > 0:
                            create_correlated_bundle(rule, query, sequence)

                correlated_hits = result["items"]

            else:  # pragma: no cover
                raise HowlerValueError(f"Unknown rule type: {rule.rule_type}")  # noqa: TRY301

            if correlated_hits and len(correlated_hits) > 0:
                create_correlated_bundle(rule, query, correlated_hits)
        except Exception as e:
            logger.debug(e, exc_info=True)
            if __scheduler_instance:
                __scheduler_instance.remove_job(f"rule_{rule.analytic_id}")
            # TODO: Allow restarting of rules
            logger.critical(
                f"Rule {rule.name} ({rule.analytic_id}) has been stopped, due to an exception: {type(e)}",
                exc_info=True,
            )

    return execute


def register_rules(new_rule: Optional[Analytic] = None, test_override: bool = False):
    "Register all of the created analytic rules as cronjobs"
    global __scheduler_instance
    if not __scheduler_instance:  # pragma: no cover
        logger.error("Scheduler instance does not exist!")
        return

    if "pytest" in sys.modules and not test_override:
        logger.info("Skipping registration, running in a test environment")
        return

    if new_rule:
        if __scheduler_instance.get_job(f"rule_{new_rule.analytic_id}"):
            logger.info(f"Updating existing rule: {new_rule.analytic_id} on interval {new_rule.rule_crontab}")

            # remove the existing job
            __scheduler_instance.remove_job(f"rule_{new_rule.analytic_id}")
        else:
            logger.info(f"Registering new rule: {new_rule.analytic_id} on interval {new_rule.rule_crontab}")
        rules = [new_rule]
    else:
        logger.debug("Registering rules")
        rules: list[Analytic] = datastore().analytic.search("_exists_:rule")["items"]

    total_initialized = 0
    for rule in rules:
        job_id = f"rule_{rule.analytic_id}"
        interval = rule.rule_crontab or f"{random.randint(0, 59)} * * * *"  # noqa: S311

        if __scheduler_instance.get_job(job_id):
            logger.debug(f"Rule {job_id} already running!")
            return

        logger.debug(f"Initializing rule cronjob with:\tJob ID: {job_id}\tRule Name: {rule.name}\tCrontab: {interval}")

        if DEBUG or new_rule:
            _kwargs: dict[str, Any] = {"next_run_time": datetime.now()}
        else:
            _kwargs = {}

        total_initialized += 1
        __scheduler_instance.add_job(
            id=job_id,
            func=create_executor(rule),
            trigger=CronTrigger.from_crontab(interval, timezone=timezone(os.getenv("SCHEDULER_TZ", "America/Toronto"))),
            **_kwargs,
        )

    logger.info(f"Initialized {total_initialized} rules")


def setup_job(sched: BaseScheduler):
    "Initialize the rules cronjobs"
    if not DEBUG and not HWL_ENABLE_RULES:  # pragma: no cover
        logger.debug("Rule integration disabled")
        return

    logger.debug("Rule integration enabled")

    global __scheduler_instance
    __scheduler_instance = sched

    register_rules()

    logger.debug("Initialization complete")
