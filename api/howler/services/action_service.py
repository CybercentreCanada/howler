import json
from collections import defaultdict
from importlib.util import find_spec
from typing import Any, Literal, Optional, TypedDict, overload

from cryptography.exceptions import InvalidTag
from flask import Response, has_request_context, request

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
from howler.services import auth_service
from howler.utils.constants import TESTING
from howler.utils.str_utils import sanitize_lucene_query

logger = get_logger(__file__)


class TriggeredAction(TypedDict):
    """Type for triggered actions"""

    hit_ids: list[str]
    uname: str | None
    auth_token: str | None


# Per-trigger persistent queues for buffering action execution requests.
_action_queues: dict[str, NamedQueue[TriggeredAction]] = {}


@overload
def get_action(id: str, as_odm: Literal[True], version: Literal[True]) -> tuple[Action, str]: ...


@overload
def get_action(id: str, as_odm: Literal[True], version: Literal[False]) -> Action: ...


@overload
def get_action(id: str, as_odm: Literal[True]) -> Action: ...


@overload
def get_action(id: str) -> Action: ...


@overload
def get_action(id: str, as_odm: Literal[False], version: Literal[True]) -> tuple[dict[str, Any], str]: ...


@overload
def get_action(id: str, as_odm: Literal[False], version: Literal[False]) -> dict[str, Any]: ...


@overload
def get_action(id: str, as_odm: Literal[False]) -> dict[str, Any]: ...


def get_action(id: str, as_odm=False, version=False):
    """Retrieve an action from the datastore as an ODM object or dictionary."""
    return datastore().action.get_if_exists(key=id, as_obj=as_odm, version=version)


def _is_builtin_operation(operation_id: str) -> bool:
    """Return whether an operation is implemented by Howler's built-in actions package."""
    return find_spec(f"howler.actions.{operation_id}") is not None


def _request_auth_token() -> str | None:
    """Extract the credential portion of the current request's authorization header."""
    if not has_request_context():
        return None

    authorization = request.headers.get("Authorization")
    if authorization is None or " " not in authorization:
        return None

    return authorization.split(" ", maxsplit=1)[1]


def get_action_queue(trigger: str) -> NamedQueue[TriggeredAction]:
    """Return the action queue for *trigger*, creating it on first use.

    Raises:
        ValueError: If *trigger* is not in ``VALID_TRIGGERS``.
    """
    if trigger not in VALID_TRIGGERS:
        raise HowlerValueError(f"Invalid trigger {trigger!r}. Must be one of {VALID_TRIGGERS}")

    if trigger not in _action_queues:
        _action_queues[trigger] = NamedQueue(
            f"howler.action_queue.{trigger}",
            host=config.core.redis.persistent.host,
            port=config.core.redis.persistent.port,
            private=False,
        )

    return _action_queues[trigger]


def enqueue_action_execution(hit_ids: str | list[str], trigger: str = "create", user: Optional[User] = None) -> None:
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

    if not isinstance(hit_ids, list):
        hit_ids = [hit_ids]

    if trigger not in VALID_TRIGGERS:
        raise HowlerValueError(f"Invalid trigger {trigger!r}. Must be one of {VALID_TRIGGERS}")

    auth_token = _request_auth_token()

    if not config.system.action_queue.enabled:
        logger.debug(
            "Executing actions for trigger %s on hit id(s) [%s] with user %s",
            trigger,
            ", ".join(hit_ids),
            user.uname if user else "NO_USER",
        )

        query = f"howler.id:({' OR '.join(sanitize_lucene_query(h) for h in hit_ids)})"
        bulk_execute_on_query(query, trigger=trigger, user=user, auth_token=auth_token)
        return

    try:
        logger.debug(
            "Enqueuing actions for trigger %s on hit id(s) [%s] with user %s",
            trigger,
            ", ".join(hit_ids),
            user.uname if user else "NO_USER",
        )
        get_action_queue(trigger).push(
            {
                "hit_ids": hit_ids,
                "uname": user.uname if user else None,
                "auth_token": auth_service.encrypt_token(auth_token),
            }
        )
    except Exception:
        logger.exception("Failed to enqueue action execution, falling back to direct execution")
        query = f"howler.id:({' OR '.join(sanitize_lucene_query(h) for h in hit_ids)})"
        bulk_execute_on_query(query, trigger=trigger, user=user, auth_token=auth_token)


def process_action_batch(trigger: str, items: list[TriggeredAction]) -> None:
    """Process a batch of queued action execution requests for a single trigger.

    Groups items by user and issues a single coalesced
    ``bulk_execute_on_query`` call per group, reducing Elasticsearch load.

    Args:
        trigger: The trigger type this batch belongs to.
        items: List of dicts with keys ``hit_ids`` and ``user``.
    """
    if not items:
        return

    groups: dict[tuple[str | None, str | None], list[str]] = defaultdict(list)

    for item in items:
        uname = item.get("uname")
        groups[(uname, item.get("auth_token"))].extend(item["hit_ids"])

    for (uname, encrypted_auth_token), hit_ids in groups.items():
        # Deduplicate IDs within a batch group
        unique_ids = list(dict.fromkeys(hit_ids))
        query = f"howler.id:({' OR '.join(sanitize_lucene_query(h) for h in unique_ids)})"

        try:
            auth_token = auth_service.decrypt_token(encrypted_auth_token)
        except InvalidTag:
            logger.error(  # noqa: TRY400
                "Queued authorization token for user=%s was encrypted with a different key. "
                "Ensure all Howler instances sharing persistent Redis use the same system.encryption_key.",
                uname,
            )
            auth_token = None
        except Exception:
            logger.exception("Unable to decrypt queued authorization token for user=%s", uname)
            auth_token = None

        try:
            user = datastore().user.get(uname)
            bulk_execute_on_query(query, trigger=trigger, user=user, auth_token=auth_token)
        except Exception:
            logger.exception("Error processing action batch for trigger=%s user=%s", trigger, uname)


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


def bulk_execute_on_query(
    query: str, trigger: str = "create", user: Optional[User] = None, auth_token: str | None = None
):
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

            if auth_token is not None and not _is_builtin_operation(operation.operation_id):
                logger.debug("Appending auth token to external operation %s", operation.operation_id)
                parsed_data["auth_token"] = auth_token

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
