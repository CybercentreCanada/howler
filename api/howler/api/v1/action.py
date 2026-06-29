import json

from flask import Response, request
from markupsafe import escape

import howler.actions as actions
from howler.api import bad_request, created, forbidden, internal_error, make_subapi_blueprint, no_content, not_found, ok
from howler.api.v1.utils.params import parse_refresh
from howler.common.exceptions import HowlerException, HowlerInvalidParameterException
from howler.common.loader import datastore
from howler.common.logging.audit import audit
from howler.common.swagger import generate_swagger_docs
from howler.config import CLASSIFICATION
from howler.datastore.howler_store import HowlerDatastore
from howler.odm.models.action import Action
from howler.odm.models.user import User
from howler.security import api_login
from howler.services import action_service
from howler.services.permission_service import (
    get_require_data_helper,
    is_allowed_to_change,
    privilege_value_verifications,
)

SUB_API = "action"
classification_definition = CLASSIFICATION.get_parsed_classification_definition()

action_api = make_subapi_blueprint(SUB_API, api_version=1)
action_api._doc = "Endpoints relating to bulk actions and automation"  # type: ignore


@generate_swagger_docs()
@action_api.route("/")
@api_login(
    audit=False,
    check_xsrf_token=False,
    required_type=["admin", "automation_basic", "automation_advanced", "actionrunner_basic", "actionrunner_advanced"],
)
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


@generate_swagger_docs()
@action_api.route("/", methods=["POST"])
@api_login(audit=False, check_xsrf_token=False, required_type=["admin", "automation_basic", "automation_advanced"])
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
    try:
        refresh = parse_refresh(request.args.get("refresh"))
    except HowlerInvalidParameterException as e:
        return bad_request(err=str(e))
    if new_action is None:
        return bad_request(err="You must specify an action")

    if error := action_service.validate_action(new_action):
        return error

    try:
        new_action["owner_id"] = user.uname

        action_obj = Action(new_action)

        ds = datastore()
        ds.action.save(action_obj.action_id, action_obj, refresh=refresh)
        ds.action.commit()
    except HowlerException as e:
        return bad_request(err=str(e))

    return created(action_obj)


@generate_swagger_docs()
@action_api.route("/<id>", methods=["PUT", "PATCH"])
@api_login(
    audit=False,
    check_xsrf_token=False,
    required_type=["admin", "automation_basic", "automation_advanced"],
)
def update_action(id: str, user: User, **_) -> Response:
    """Update an existing action

    Variables:
    id  => id of the action to update

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
    try:
        refresh = parse_refresh(request.args.get("refresh"))
    except HowlerInvalidParameterException as e:
        return bad_request(err=str(e))

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
    allowed_list = (
        ([existing_action["owner_id"]] or []) + (existing_action["admins"] or []) + (existing_action["members"] or [])
    )

    if user.uname not in allowed_list and "admin" not in user.type:
        return forbidden(err="You do not have the permission to update this action")
    updated_action = {
        **existing_action,
        **updated_action,
        "action_id": existing_action["action_id"],
    }

    if error := action_service.validate_action(updated_action):
        return error

    try:
        action_obj = Action(updated_action)
        action_obj.action_id = id
        ds.action.save(action_obj.action_id, action_obj, refresh=refresh)
        ds.action.commit()
    except HowlerException as e:
        return bad_request(err=str(e))

    return ok(action_obj)


@generate_swagger_docs()
@action_api.route("/<id>", methods=["DELETE"])
@api_login(audit=True, check_xsrf_token=False, required_type=["admin", "automation_basic", "automation_advanced"])
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

    try:
        refresh = parse_refresh(request.args.get("refresh"))
    except HowlerInvalidParameterException as e:
        return bad_request(err=str(e))

    if not result["total"]:
        return not_found(err="Action does not exist")

    action: Action = result["items"][0]

    if user.uname != action.owner_id and "admin" not in user.type:
        return forbidden(err="You do not have the permissions necessary to delete this action.")

    try:
        ds.action.delete(id, refresh=refresh)
        ds.action.commit()

        return no_content()
    except HowlerException as e:
        return internal_error(err=str(e))


@generate_swagger_docs()
@action_api.route("/<id>/execute", methods=["POST"])
@api_login(
    audit=True,
    check_xsrf_token=False,
    required_type=["admin", "automation_basic", "automation_advanced", "actionrunner_basic", "actionrunner_advanced"],
)
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
    current_user: User | None = kwargs.get("user", None)

    for operation in action.operations:
        op_data = json.loads(operation.data_json) if operation.data_json else {}

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
@api_login(
    audit=False,
    check_xsrf_token=False,
    required_type=["admin", "automation_basic", "automation_advanced", "actionrunner_basic", "actionrunner_advanced"],
)
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
@api_login(
    audit=True,
    check_xsrf_token=False,
    required_type=["admin", "automation_basic", "automation_advanced", "actionrunner_basic", "actionrunner_advanced"],
)
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
    current_user: User | None = kwargs.get("user", None)
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


# region Permission


@generate_swagger_docs()
@action_api.route("/<id>/permission", methods=["PUT"])
@api_login(required_priv=["R", "W"], required_type=["automation_basic"])
def give_privilege(id: str, user: User, **kwargs):
    """give permission from one user to an other.

        The json object need to send "privilege", "user_id" as a key.
        privilege : The value need to be one of ["administrator", "member", "owner"]
        user_id : the value need to be the user to add or remove from the permission
    Variables:
    action_id => The id of the action to give administrative privilege of

    Arguments:
        id : The id of the action to give administrative privilege of
        user : the user requesting the privilege change (injected by the api_login decorator)

    Optional Arguments:
        None

    Data Block:
    {
        "privilege": "privilege to give"  # [member, administrator, owner]
        "user_id": "user to give permission to"
    }

    Result Example:
    {
        "success": True     # If the operation succeeded
    }
    """
    temp_value: tuple[HowlerDatastore, str, str] | str = get_require_data_helper(request.json)

    if isinstance(temp_value, str):
        return bad_request(err=temp_value)

    storage, priv_requested, user_to_add = temp_value
    result = privilege_value_verifications(
        item_id=escape(str(id)), level_requested=priv_requested, member_to_modify=user_to_add, item_type=Action
    )

    if isinstance(result, str):
        return bad_request(err=result)

    if not isinstance(result[1], Action):
        return bad_request(err=f"Wrong request type. Object of type {type(result[1])} was requested insted of View")

    storage, existing_action = result

    priv_map = existing_action.get_privilege_mapping()

    priv_request: str = escape(str(priv_requested))
    is_allowed: bool = is_allowed_to_change(level_requested=priv_request, user=user, existing_item=existing_action)

    if not is_allowed:
        return forbidden(err="You do not have the necessary permissions to modify this privilege level.")

    if user_to_add in priv_map[priv_request]:
        return bad_request(err=f"{user_to_add} already have the permission {priv_request}")

    existing_action.set_privilege_mapping(priv_request, user_to_add)

    storage.action.save(existing_action.action_id, existing_action)

    storage.action.commit()

    return ok(storage.action.get_if_exists(existing_action.action_id, as_obj=False))


@generate_swagger_docs()
@action_api.route("/<id>/permission", methods=["DELETE"])
@api_login(required_priv=["R", "W"], required_type=["automation_basic"])
def revoke_privilege(id: str, user: User, **kwargs):
    """Give permission from one user to another.

    Variables:
        id => The unique ID of the action embedded in the URL path

    Arguments:
        id: The id of the action to modify permissions for
        user: The user making the request (injected by the api_login decorator)

    Optional Arguments:
        None

    Data Block:
        {
            "privilege": "privilege to give",  # [member, administrator, owner]
            "user_id": "user to remove permission from",
        }

    Result Example:
        {
            "success": True
        }
    """
    temp_value: tuple[HowlerDatastore, str, str] | str = get_require_data_helper(request.json)

    if isinstance(temp_value, str):
        return bad_request(err=temp_value)

    storage, priv_requested, user_to_remove = temp_value
    result = privilege_value_verifications(
        item_id=escape(str(id)),
        level_requested=priv_requested,
        member_to_modify=user_to_remove,
        is_adding=False,
        item_type=Action,
    )

    if isinstance(result, str):
        return bad_request(err=result)

    if not isinstance(result[1], Action):
        return bad_request(err=f"Wrong request type. Object of type {type(result[1])} was requested insted of View")

    storage, existing_action = result

    priv_map = existing_action.get_privilege_mapping()
    is_allowed: bool = is_allowed_to_change(
        level_requested=priv_requested,
        user=user,
        existing_item=existing_action,
    )

    if isinstance(is_allowed, Response):
        return is_allowed

    if not is_allowed:
        return forbidden(err="You do not have the necessary permissions to modify this privilege level.")

    if user_to_remove not in priv_map[priv_requested]:
        return bad_request(err=f"{user_to_remove} is not in the {priv_requested} premission group")

    if priv_requested == "owner":
        return bad_request(
            err="You cannot remove the owner privilege. Only transfer is allowed. (Use the give_privilege endpoint)"
        )

    existing_action.remove_privilege_mapping(priv_requested, user_to_remove)

    storage.action.save(existing_action.action_id, existing_action)

    storage.action.commit()

    return ok(storage.action.get_if_exists(existing_action.action_id, as_obj=False))


@generate_swagger_docs()
@action_api.route("/<id>/permission_options", methods=["GET"])
@api_login(required_priv=["R"])
def get_action_permission(id: str, user: User, **kwargs):
    """Get details for a specific action

    Variables:
        id => The unique ID of the action embedded in the URL path
    Arguments:
        id: The id of the Action to get permissions for
        user: The user making the request (injected by the api_login decorator)

    Optional Arguments:
        None
    Result Example:
         {
            "administrator": [ # Each entry corresponds to a given privilege level
                "user1", "user2" # A list of users that have this privilege
            ],
        }
    returns a dict with the possible permissions for the action and the users that have them.
    """
    storage = datastore()

    action: Action = storage.action.get_if_exists(id, as_obj=False)  # type: ignore
    if not action or not isinstance(action, Action):
        return not_found(err="This action does not exist")

    if action.get("type") == "personal" and user.uname != action.get("owner"):
        return forbidden(err="You cannot access a personal action that is not owned by you.")
    return ok(action.get_privilege_mapping())


# endregion
