import json
from collections import defaultdict
from collections.abc import Callable, Mapping
from importlib.util import find_spec
from typing import Any, Literal, Optional, TypedDict, overload

from cryptography.exceptions import InvalidTag
from flask import Response, has_request_context, request
from pydantic import ValidationError

from howler import actions
from howler.actions.models import (
    DISPATCHER_ARGUMENTS,
    ActionModel,
    format_action_validation_error,
    format_validation_error,
)
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
def get_action(
    id: str, as_odm: Literal[True], version: Literal[True], user: User | None = None
) -> tuple[Action, str]: ...  # codeql[py/ineffectual-statement]


@overload
def get_action(
    id: str, as_odm: Literal[True], version: Literal[False]
) -> Action: ...  # codeql[py/ineffectual-statement]


@overload
def get_action(id: str, as_odm: Literal[True]) -> Action: ...  # codeql[py/ineffectual-statement]


@overload
def get_action(id: str) -> Action: ...  # codeql[py/ineffectual-statement]


@overload
def get_action(
    id: str, as_odm: Literal[False], version: Literal[True]
) -> tuple[dict[str, Any], str]: ...  # codeql[py/ineffectual-statement]


@overload
def get_action(
    id: str, as_odm: Literal[False], version: Literal[False]
) -> dict[str, Any]: ...  # codeql[py/ineffectual-statement]


@overload
def get_action(id: str, as_odm: Literal[False]) -> dict[str, Any]: ...  # codeql[py/ineffectual-statement]


def get_action(id: str, as_odm=False, version=False, user: User | None = None):
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


def _invalid_arguments_report(query: str, message: str) -> dict[str, str]:
    return {
        "query": f"({query})",
        "outcome": "error",
        "title": "Invalid Arguments",
        "message": message,
    }


def _invalid_dispatcher_arguments_report(query: str, arguments: Mapping[str, Any]) -> dict[str, str] | None:
    """Return an Invalid Arguments report for dispatcher-owned keys in user data."""
    if reserved := DISPATCHER_ARGUMENTS & set(arguments):
        message = "; ".join(
            f"{key}: Extra inputs are not permitted (received {arguments[key]!r})" for key in sorted(reserved)
        )
        return _invalid_arguments_report(query, message)

    return None


def _parse_operation_data_json(data_json: Any, query: str) -> tuple[dict[str, Any], dict[str, str] | None]:
    if data_json is None or data_json == "":
        return {}, None

    if not isinstance(data_json, str):
        return {}, _invalid_arguments_report(query, "data_json must be a JSON string containing an object.")

    try:
        parsed_data = json.loads(data_json)
    except json.JSONDecodeError as error:
        return {}, _invalid_arguments_report(query, f"data_json must be valid JSON: {error.msg}.")

    if not isinstance(parsed_data, dict):
        return {}, _invalid_arguments_report(query, "data_json must be a JSON object.")

    return parsed_data, None


def _audit_action_operation(
    query: str,
    operation_id: str,
    arguments: Mapping[str, Any],
    user: User | None,
    audit_fn: Callable[..., Any],
    *,
    include_arguments: bool,
) -> None:
    audit_data = {
        "user": user,
        "query": query,
        "operation_id": operation_id,
    }
    if include_arguments:
        audit_data.update(arguments)

    audit(
        [],
        audit_data,
        user["uname"] if user is not None else "unknown",
        user,
        audit_fn,
    )


def execute_saved_action(
    action_id: str,
    *,
    query_override: str | None,
    request_id: str | None,
    user: User | None,
    audit_fn: Callable[..., Any],
) -> dict[str, list[dict[str, Any]]] | None:
    """Execute a saved action, reporting invalid persisted argument JSON per operation."""
    action = datastore().action.get(action_id)
    if not action:
        return None

    return execute_operations(
        query_override or action.query,
        request_id,
        [{"operation_id": operation.operation_id, "data_json": operation.data_json} for operation in action.operations],
        user,
        audit_fn=audit_fn,
    )


def execute_operations(
    query: str,
    request_id: str | None,
    operations: list[Mapping[str, Any]],
    user: User | None,
    *,
    audit_fn: Callable[..., Any],
) -> dict[str, list[dict[str, Any]]]:
    """Execute operations and return reports grouped by operation ID."""
    reports: dict[str, list[dict[str, Any]]] = {}
    for operation in operations:
        operation_id = operation["operation_id"]
        op_data, invalid_report = _parse_operation_data_json(operation.get("data_json"), query)
        if invalid_report is None:
            invalid_report = _invalid_dispatcher_arguments_report(query, op_data)

        _audit_action_operation(
            query,
            operation_id,
            op_data,
            user,
            audit_fn,
            include_arguments=invalid_report is None,
        )

        report = (
            [invalid_report]
            if invalid_report is not None
            else actions.execute(
                operation_id=operation_id,
                request_id=request_id,
                query=query,
                user=user,
                **op_data,
            )
        )
        reports.setdefault(operation_id, []).extend(report)

    return reports


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


def validate_action(new_action: Any) -> Optional[Response]:
    """Validate a new action"""
    try:
        action = ActionModel.model_validate(new_action)
    except ValidationError as e:
        return bad_request(err=format_action_validation_error(e))

    for operation in action.operations:
        specification = actions.get_specification(operation.operation_id)
        if specification is None:
            return bad_request(
                err=f"The operation ID provided ({operation.operation_id}) does not match any enabled operations."
            )

        try:
            specification.validate_arguments(operation.data)
        except ValidationError as e:
            return bad_request(
                err=f"Invalid arguments for operation {operation.operation_id}: {format_validation_error(e)}"
            )

    return None


def _execute_bulk_operation(
    action: Action,
    operation: Any,
    intersected_query: str,
    user: Optional[User],
    auth_token: str | None,
) -> None:
    parsed_data, invalid_report = _parse_operation_data_json(operation.data_json, intersected_query)
    if invalid_report is None:
        invalid_report = _invalid_dispatcher_arguments_report(intersected_query, parsed_data)

    _audit_action_operation(
        intersected_query,
        operation.operation_id,
        parsed_data,
        user,
        bulk_execute_on_query,
        include_arguments=invalid_report is None,
    )

    if invalid_report:
        logger.warning(
            "Invalid Arguments for action %s operation %s: %s",
            action.action_id,
            operation.operation_id,
            invalid_report["message"],
        )
        return

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

            _execute_bulk_operation(action, operation, intersected_query, user, auth_token)
