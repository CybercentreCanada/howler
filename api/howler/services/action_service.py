import json
import sys
from typing import Any, Optional

from flask import Response

from howler import actions
from howler.api import bad_request
from howler.common.exceptions import HowlerValueError
from howler.common.loader import datastore
from howler.common.logging import get_logger
from howler.common.logging.audit import audit
from howler.odm.models.action import VALID_TRIGGERS, Action
from howler.odm.models.user import User
from howler.utils.str_utils import sanitize_lucene_query

logger = get_logger(__file__)


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
            if "pytest" in sys.modules:
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
