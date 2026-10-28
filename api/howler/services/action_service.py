from collections import defaultdict
from collections.abc import Callable, Mapping
from importlib.util import find_spec
from typing import Any, Literal, Optional, TypedDict, overload

from cryptography.exceptions import InvalidTag
from flask import Response, has_request_context, request
from pydantic import ValidationError

from howler import actions
from howler.actions.models import (
    format_validation_error,
    invalid_arguments_report,
    parse_data_json,
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
    """Return only the credential from a well-formed Bearer authorization header.

    Basic user/password and API-key credentials are not action-provider
    credentials and therefore must not be forwarded or persisted.
    """
    if not has_request_context():
        return None

    parts = request.headers.get("Authorization", "").split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None

    return parts[1] or None


def _parse_and_audit_operation(
    data_json: Any,
    query: str,
    operation_id: str,
    user: User | None,
    audit_fn: Callable[..., Any],
) -> tuple[dict[str, Any], dict[str, str] | None]:
    try:
        op_data = parse_data_json(data_json, forbid_dispatcher_args=True)
        invalid_report = None
    except ValueError as error:
        op_data = {}
        invalid_report = invalid_arguments_report(query, str(error))

    audit(
        [],
        {**op_data, "user": user, "query": query, "operation_id": operation_id},
        user["uname"] if user is not None else "unknown",
        user,
        audit_fn,
    )
    return op_data, invalid_report


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
        op_data, invalid_report = _parse_and_audit_operation(
            operation.get("data_json"), query, operation_id, user, audit_fn
        )
        report = (
            [invalid_report]
            if invalid_report is not None
            else actions.execute(
                operation_id=operation_id,
                request_id=request_id,
                query=query,
                user=user,
                **({"bearer_token": token} if (token := _request_auth_token()) else {}),
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


def _validate_operations_list(operations: Any, *, scope: str) -> Optional[Response]:
    if not isinstance(operations, list):
        return bad_request(
            err="'operations' must be a list of operations."
            if scope == "action"
            else "You must specify a list of operations."
        )

    if scope == "action" and not operations:
        return bad_request(err="You must specify at least one operation.")

    if any(
        not isinstance(op, dict) or not isinstance(op.get("operation_id"), str) or not op["operation_id"]
        for op in operations
    ):
        return bad_request(err="Every operation must specify an operation_id.")

    operation_ids = [op["operation_id"] for op in operations]
    if len(operation_ids) != len(set(operation_ids)):
        target = "the action" if scope == "action" else "request"
        return bad_request(err=f"You must have a maximum of one operation of each type in {target}.")

    return None


def validate_execute_request(execute_req: Any) -> Optional[Response]:
    """Validate a direct operation execution request payload."""
    if not isinstance(execute_req, dict):
        return bad_request(err="Incorrect data structure!")

    if error := _validate_operations_list(execute_req.get("operations"), scope="request"):
        return error

    query = execute_req.get("query")
    if not isinstance(query, str) or not query:
        return bad_request(err="You must specify a query.")

    return None


def validate_action(new_action: Any) -> Optional[Response]:  # noqa: C901
    """Validate a new action"""
    if not isinstance(new_action, dict):
        return bad_request(err="Incorrect data structure!")

    if "name" not in new_action:
        return bad_request(err="You must specify a name.")
    if not isinstance(new_action["name"], str) or not new_action["name"]:
        return bad_request(err="Name cannot be empty.")

    if "query" not in new_action:
        return bad_request(err="You must specify a query.")
    if not isinstance(new_action["query"], str) or not new_action["query"]:
        return bad_request(err="Query cannot be empty.")

    operations = new_action.get("operations")
    if operations is None:
        return bad_request(err="You must specify a list of operations.")
    if error := _validate_operations_list(operations, scope="action"):
        return error

    triggers = new_action.get("triggers", [])
    if not isinstance(triggers, list) or any(not isinstance(t, str) or t not in VALID_TRIGGERS for t in triggers):
        return bad_request(err="Invalid trigger provided.")

    for operation in operations:
        op_id = operation["operation_id"]
        try:
            op_data = parse_data_json(operation.get("data_json"), allow_empty=False)
        except ValueError as e:
            return bad_request(err=f"Invalid arguments for operation {op_id}: {e}")

        specification = actions.get_specification(op_id)
        if specification is None:
            return bad_request(err=f"The operation ID provided ({op_id}) does not match any enabled operations.")

        try:
            specification.validate_arguments(op_data)
        except ValidationError as e:
            return bad_request(err=f"Invalid arguments for operation {op_id}: {format_validation_error(e)}")

    return None


def _execute_bulk_operation(
    action: Action,
    operation: Any,
    intersected_query: str,
    user: Optional[User],
    auth_token: str | None,
) -> None:
    parsed_data, invalid_report = _parse_and_audit_operation(
        operation.data_json, intersected_query, operation.operation_id, user, bulk_execute_on_query
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
        parsed_data["auth_token"] = auth_token

    report = actions.execute(
        operation_id=operation.operation_id,
        query=intersected_query,
        user=user,
        **({"bearer_token": auth_token} if auth_token else {}),
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
