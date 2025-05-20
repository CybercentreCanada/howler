import json
from typing import Any, Optional

from flask import Response, request

import howler.actions as actions
from howler.api import (
    bad_request,
    created,
    forbidden,
    internal_error,
    make_subapi_blueprint,
    no_content,
    not_found,
    ok,
)
from howler.common.exceptions import HowlerException
from howler.common.loader import datastore
from howler.common.logging.audit import audit
from howler.common.swagger import generate_swagger_docs
from howler.config import CLASSIFICATION
from howler.odm.models.action import Action
from howler.odm.models.user import User
from howler.security import api_login
from howler.services.action_service import VALID_TRIGGERS

SUB_API = "action"
classification_definition = CLASSIFICATION.get_parsed_classification_definition()

action_api = make_subapi_blueprint(SUB_API, api_version=1)
action_api._doc = "Endpoints relating to bulk actions and automation"


@generate_swagger_docs()
@action_api.route("/")
@api_login(audit=False, check_xsrf_token=False, required_type=["automation_basic"])
def get_actions(**_) -> Response:
    """Get a list of existing actions

    Variables:
    None

    Optional Arguments:
    None

    Result Example:
    [
        ...actions    # A list of actions the user can see
    ]
    """
    return ok(datastore().action.search("*:*", as_obj=False)["items"])


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


@generate_swagger_docs()
@action_api.route("/", methods=["POST"])
@api_login(audit=False, check_xsrf_token=False, required_type=["automation_basic"])
def add_action(user: User, **_) -> Response:
    """Create a new action

    Variables:
    None

    Optional Arguments:
    None

    Data Block:
    {
        "name": "New Action",               # An action name (human readable)
        "query": "howler.id:*",             # The query to execute when triggering this action
        "operations": [                     # A list of operations to execute
            {
                "operation_id": "add_label",          # The id of the operation to run
                "data_json": "{'category': 'generic', 'label': 'assigned'}" # Various requisite values for the operation
            }
        ]
    }

    Result Example:
    {
        ...action   # The saved action data
    }
    """
    new_action = request.json

    if new_action is None:
        return bad_request(err="You must specify an action")

    if error := validate_action(new_action):
        return error

    try:
        new_action["owner_id"] = user.uname

        action_obj = Action(new_action)

        ds = datastore()
        ds.action.save(action_obj.action_id, action_obj)
        ds.action.commit()
    except HowlerException as e:
        return bad_request(err=str(e))

    return created(action_obj)


@generate_swagger_docs()
@action_api.route("/<id>", methods=["PUT", "PATCH"])
@api_login(
    audit=False,
    check_xsrf_token=False,
    required_type=["automation_basic"],
)
def update_action(id: str, user: User, **_) -> Response:
    """Update an existing action

    Variables:
    id  => id of the aciton to update

    Optional Arguments:
    None

    Data Block:
    {
        "name": "New Action",               # An action name (human readable)
        "query": "howler.id:*",             # The query to execute when triggering this action
        "actions": [                        # A list of actions to execute
            {
                "operation_id": "add_label",          # The id of the action to run
                "data_json": "{ 'category': 'generic', 'label': 'assigned' }" # Various requisite values for the action
            }
        ]
    }

    Result Example:
    {
        ...action   # The saved action data
    }
    """
    updated_action = request.json
    if not isinstance(updated_action, dict):
        return bad_request(err="Incorrect data structure!")

    ds = datastore()

    existing_action = ds.action.get(id, as_obj=False)

    if not existing_action:
        return not_found(err="The specified automation does not exist")

    if "automation_advanced" not in user.type and updated_action.get("triggers", []) != existing_action.get(
        "triggers", []
    ):
        return forbidden(err="Updating triggers requires the role 'automation_advanced'.")

    updated_action = {
        **existing_action,
        **updated_action,
        "action_id": existing_action["action_id"],
    }

    if error := validate_action(updated_action):
        return error

    try:
        action_obj = Action(updated_action)
        action_obj.action_id = id

        ds.action.save(action_obj.action_id, action_obj)
        ds.action.commit()
    except HowlerException as e:
        return bad_request(err=str(e))

    return ok(action_obj)


@generate_swagger_docs()
@action_api.route("/<id>", methods=["DELETE"])
@api_login(audit=True, check_xsrf_token=False, required_type=["automation_basic"])
def delete_action(id: str, user: User, **kwargs) -> Response:
    """Delete an existing action

    Variables:
    id  => The id of the action to delete

    Optional Arguments:
    None

    Result Example:
    None
    """
    ds = datastore()

    result = ds.action.search(f"action_id:{id}", rows=1)

    if not result["total"]:
        return not_found(err="Action does not exist")

    action: Action = result["items"][0]

    if action.owner_id != user.uname and "admin" not in user.type:
        return forbidden(err="You do not have the permissions necessary to delete this action.")

    try:
        ds.action.delete(id)
        ds.action.commit()

        return no_content()
    except HowlerException as e:
        return internal_error(err=str(e))


@generate_swagger_docs()
@action_api.route("/<id>/execute", methods=["POST"])
@api_login(audit=True, check_xsrf_token=False, required_type=["automation_basic"])
def execute_action(id: str, **kwargs) -> Response:
    """Execute one or more actions on a given query

    Variables:
    id  => The id of the action to execute

    Optional Arguments:
    None

    Data Block:
    {
        "request_id": "abc123",     # An id used to identify the request in websocket updates
        "query": "howler.id:*"      # An optional override query
    }

    Result Example:
    {
        "add_label": [                                              # Each entry corresponds to a given action ID
            {
                "query": "howler.id:*",                             # The query this portion of the report applies to
                "title": "Execution Succeeeded",                    # The title of this section of the report
                "message": "Label successfully added to 42 hits"    # A longer explanation of this portion
            }
        ]
    }
    """
    execute_req = request.json
    if not isinstance(execute_req, dict):
        return bad_request(err="Incorrect data structure!")

    action: Action = datastore().action.get(id)

    if not action:
        return not_found(err="The specified action does not exist")

    reports: dict[str, list[dict]] = {}
    current_user = kwargs.get("user", None)

    for operation in action.operations:
        op_data = json.loads(operation["data_json"])

        query = execute_req.get("query", action.query) or action.query

        audit(
            [],
            {
                **kwargs,
                "query": query,
                "operation_id": operation.operation_id,
                **op_data,
            },
            current_user["uname"] if current_user is not None else "unknown",
            current_user,
            execute_action,
        )

        report = actions.execute(
            operation_id=operation.operation_id,
            request_id=execute_req["request_id"],
            query=query,
            user=current_user,
            **op_data,
        )

        if operation.operation_id not in reports:
            reports[operation.operation_id] = []

        reports[operation.operation_id].extend(report)

    return ok(reports)


@generate_swagger_docs()
@action_api.route("/operations")
@api_login(audit=False, check_xsrf_token=False, required_type=["automation_basic"])
def get_operations(**_) -> Response:
    """Get a list of operations the user can run on a query

    Variables:
    None

    Optional Arguments:
    None

    Result Example:
    [
        ...operations    # A list of specifications for the operations the user can use
    ]
    """
    return ok(actions.specifications())


@generate_swagger_docs()
@action_api.route("/execute", methods=["POST"])
@api_login(audit=True, check_xsrf_token=False, required_type=["automation_basic"])
def execute_operations(**kwargs) -> Response:
    """Execute one or more operations on a given query

    Variables:
    None

    Optional Arguments:
    None

    Data Block:
    {
        "query": "howler.id:*",     # The query to run
        "request_id": "abc123",     # An id used to identify the request in websocket updates
        "operations": [                # A list of operations to execute
            {
                "operation_id": "add_label",          # The id of the action to run
                "data_json": { "category": "generic", "label": "assigned" } # Various requisite values for the action
            }
        ]
    }

    Result Example:
    {
        "add_label": [                                              # Each entry corresponds to a given operation ID
            {
                "query": "howler.id:*",                             # The query this portion of the report applies to
                "title": "Execution Succeeeded",                    # The title of this section of the report
                "message": "Label successfully added to 42 hits"    # A longer explanation of this portion
            }
        ]
    }
    """
    execute_req = request.json
    if not isinstance(execute_req, dict):
        return bad_request(err="Incorrect data structure!")

    reports: dict[str, list[dict]] = {}
    current_user = kwargs.get("user", None)
    operations = execute_req["operations"]

    operation_ids = [o["operation_id"] for o in operations]
    if len(operation_ids) != len(set(operation_ids)):
        return bad_request(err="You must have a maximum of one operation of each type in request.")

    for operation in operations:
        op_data = json.loads(operation["data_json"])

        audit(
            [],
            {
                **kwargs,
                "query": execute_req["query"],
                "operation_id": operation["operation_id"],
                **op_data,
            },
            current_user["uname"] if current_user is not None else "unknown",
            current_user,
            execute_operations,
        )

        report = actions.execute(
            operation_id=operation["operation_id"],
            request_id=execute_req["request_id"],
            query=execute_req["query"],
            user=current_user,
            **op_data,
        )

        if operation["operation_id"] not in reports:
            reports[operation["operation_id"]] = []

        reports[operation["operation_id"]].extend(report)

    return ok(reports)
