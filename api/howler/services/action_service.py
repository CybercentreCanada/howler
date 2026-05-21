import json
from typing import Any, Optional

from flask import Response

from howler import actions
from howler.api import bad_request
from howler.common.exceptions import HowlerValueError
from howler.common.loader import datastore
from howler.common.logging import get_logger
from howler.common.logging.audit import audit
from howler.config import config
from howler.odm.models.action import VALID_TRIGGERS, Action
from howler.odm.models.user import User
from howler.remote.datatypes.queues.named import NamedQueue
from howler.utils.constants import TESTING
from howler.utils.str_utils import sanitize_lucene_query

logger = get_logger(__file__)

# Per-trigger persistent queues for buffering action execution requests.
_action_queues: dict[str, NamedQueue[dict]] = {}


def _get_action_queue(trigger: str) -> NamedQueue[dict]:
    """Return the action queue for *trigger*, creating it on first use."""
    if trigger not in _action_queues:
        _action_queues[trigger] = NamedQueue(
            f"howler.action_queue.{trigger}",
            host=config.core.redis.persistent.host,
            port=config.core.redis.persistent.port,
            private=False,
        )

    return _action_queues[trigger]


def enqueue_action_execution(hit_ids: list[str], trigger: str = "create", user: Optional[User] = None) -> None:
    """Buffer action execution by pushing to a Redis queue.

    When the action queue is disabled in configuration, falls back to
    calling ``bulk_execute_on_query`` directly for backwards compatibility.

    Args:
        hit_ids: List of hit IDs to execute actions against.
        trigger: The trigger type (create, promote, demote, add_label, remove_label).
        user: The user initiating the action.
    """
    if not hit_ids:
        return

    if not config.system.action_queue.enabled:
        query = f"howler.id:({' OR '.join(sanitize_lucene_query(h) for h in hit_ids)})"
        bulk_execute_on_query(query, trigger=trigger, user=user)
        return

    try:
        _get_action_queue(trigger).push(
            {
                "hit_ids": hit_ids,
                "user": user.as_primitives() if user is not None and hasattr(user, "as_primitives") else user,
            }
        )
    except Exception:
        logger.exception("Failed to enqueue action execution, falling back to direct execution")
        query = f"howler.id:({' OR '.join(sanitize_lucene_query(h) for h in hit_ids)})"
        bulk_execute_on_query(query, trigger=trigger, user=user)


def process_action_batch(trigger: str, items: list[dict]) -> None:
    """Process a batch of queued action execution requests for a single trigger.

    Groups items by user and issues a single coalesced
    ``bulk_execute_on_query`` call per group, reducing Elasticsearch load.

    Args:
        trigger: The trigger type this batch belongs to.
        items: List of dicts with keys ``hit_ids`` and ``user``.
    """
    if not items:
        return

    groups: dict[str | None, tuple[list[str], Any]] = {}

    for item in items:
        user_data = item.get("user")
        user_key = user_data["uname"] if isinstance(user_data, dict) and "uname" in user_data else None

        if user_key not in groups:
            groups[user_key] = ([], user_data)

        groups[user_key][0].extend(item["hit_ids"])

    for user_key, (hit_ids, user_data) in groups.items():
        # Deduplicate IDs within a batch group
        unique_ids = list(dict.fromkeys(hit_ids))
        query = f"howler.id:({' OR '.join(sanitize_lucene_query(h) for h in unique_ids)})"

        try:
            bulk_execute_on_query(query, trigger=trigger, user=user_data)
        except Exception:
            logger.exception("Error processing action batch for trigger=%s user=%s", trigger, user_key)


def validate_action(new_action: Any) -> Optional[Response]:  # noqa: C901
    """Validate a new action"""
    if not isinstance(new_action, dict):
        return bad_request(err="Incorrect data structure!")

    if "name" not in new_action:
        return bad_request(err="You must specify a name.")
    elif not new_action["name"]:
        return bad_request(err="Name cannot be empty.")

    if "query" not in new_action:
        return bad_request(err="You must specify a query.")
    elif not new_action["query"]:
        return bad_request(err="Query cannot be empty.")

    operations = new_action.get("operations", None)
    if operations is None:
        return bad_request(err="You must specify a list of operations.")

    if not isinstance(operations, list):
        return bad_request(err="'operations' must be a list of operations.")

    if len(operations) < 1:
        return bad_request(err="You must specify at least one operation.")

    operation_ids = [o["operation_id"] for o in operations]
    if len(operation_ids) != len(set(operation_ids)):
        return bad_request(err="You must have a maximum of one operation of each type in the action.")

    if set(new_action.get("triggers", [])) - set(VALID_TRIGGERS):
        return bad_request(err="Invalid trigger provided.")

    return None


def bulk_execute_on_query(query: str, trigger: str = "create", user: Optional[User] = None):
    """Execute the operations specified in registered actions on the given query"""
    storage = datastore()

    if trigger not in VALID_TRIGGERS:
        raise HowlerValueError(f"{trigger} is not a valid trigger. It must be one of {','.join(VALID_TRIGGERS)}")

    on_trigger_actions: list[Action] = storage.action.search(f"triggers:{sanitize_lucene_query(trigger)}", rows=10000)[
        "items"
    ]

    for action in on_trigger_actions:
        intersected_query = f"({query}) AND ({action.query})"

        if datastore().hit.search(intersected_query, rows=0)["total"] < 1:
            if TESTING:
                logger.debug("Action %s does not apply to query %s", action.action_id, query)

            continue

        logger.info("Running action %s on bulk query %s", action.action_id, query)
        for operation in action.operations:
            if operation.operation_id == "example_plugin":
                continue

            parsed_data = json.loads(operation.data_json) if operation.data_json else operation.data

            audit(
                [],
                {
                    "query": intersected_query,
                    "operation_id": operation.operation_id,
                    **parsed_data,
                },
                user["uname"] if user is not None else "unknown",
                user,
                bulk_execute_on_query,
            )

            if not user:
                raise NotImplementedError("Running actions without a user object is not currently supported")

            report = actions.execute(
                operation_id=operation.operation_id,
                query=intersected_query,
                user=user,
                **parsed_data,
            )

            for entry in report:
                logger.info(
                    "%s (%s): %s",
                    operation.operation_id,
                    entry["outcome"],
                    entry["message"],
                )
                logger.debug("\t%s", entry["query"])
