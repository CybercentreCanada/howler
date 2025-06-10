import json
from typing import Any, Optional

from howler import actions
from howler.common.exceptions import HowlerValueError
from howler.common.loader import datastore
from howler.common.logging import get_logger
from howler.common.logging.audit import audit
from howler.odm.models.action import VALID_TRIGGERS, Action
from howler.odm.models.hit import Hit
from howler.odm.models.user import User
from howler.services import lucene_service
from howler.utils.str_utils import sanitize_lucene_query

logger = get_logger(__file__)


def __get_triggered_actions(trigger: str) -> list[Action]:
    storage = datastore()
    return storage.action.search(f"triggers:{sanitize_lucene_query(trigger)}", rows=1000)["items"]


def execute_on_hit(hit: Hit | dict[str, Any], trigger: str = "create", user: Optional[User] = None):  # noqa: F821
    "Execute matching actions on a given alert"
    if trigger not in VALID_TRIGGERS:
        raise HowlerValueError(f"{trigger} is not a valid trigger. It must be one of {','.join(VALID_TRIGGERS)}")

    if not user:
        raise NotImplementedError("Running actions without a user object is not currently supported")

    on_trigger_actions: list[Action] = __get_triggered_actions(trigger)

    hit = hit if isinstance(hit, dict) else hit.as_primitives()
    for action in on_trigger_actions:
        if not lucene_service.match(action.query, hit):
            continue

        logger.info("Running action %s on alert %s", action.action_id, hit["howler"]["id"])
        for operation in action.operations:
            if operation.operation_id == "example_plugin":
                continue

            parsed_data = json.loads(operation.data_json) if operation.data_json else operation.data

            audit(
                [],
                {
                    "query": f"howler.id:{hit['howler']['id']}",
                    "operation_id": operation.operation_id,
                    **parsed_data,
                },
                user["uname"] if user is not None else "unknown",
                user,
                execute_on_hit,
            )

            report = actions.execute(
                operation_id=operation.operation_id,
                query=f"howler.id:{hit['howler']['id']}",
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


def bulk_execute_on_query(query: str, trigger: str = "create", user: Optional[User] = None):
    """Execute the operations specified in registered actions on the given query"""
    if trigger not in VALID_TRIGGERS:
        raise HowlerValueError(f"{trigger} is not a valid trigger. It must be one of {','.join(VALID_TRIGGERS)}")

    if not user:
        raise NotImplementedError("Running actions without a user object is not currently supported")

    on_trigger_actions: list[Action] = __get_triggered_actions(trigger)

    for action in on_trigger_actions:
        intersected_query = f"({query}) AND ({action.query})"

        if datastore().hit.search(intersected_query, rows=0)["total"] < 1:
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
