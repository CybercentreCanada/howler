from typing import cast

from flask import request
from markupsafe import escape
from mergedeep.mergedeep import merge

from howler.api import bad_request, created, forbidden, make_subapi_blueprint, no_content, not_found, ok
from howler.common.exceptions import HowlerException
from howler.common.loader import datastore
from howler.common.logging import get_logger
from howler.common.swagger import generate_swagger_docs
from howler.datastore.exceptions import SearchException
from howler.datastore.howler_store import HowlerDatastore
from howler.odm.models.user import User
from howler.odm.models.view import View
from howler.security import api_login
from howler.services.permission_service import (
    _get_edit_auth_error,
    get_require_data_helper,
    is_allowed_to_change,
    privilege_value_verifications,
)

SUB_API = "view"
view_api = make_subapi_blueprint(SUB_API, api_version=1)
view_api._doc = "Manage the different views created for filtering hits"  # type: ignore

logger = get_logger(__file__)


@generate_swagger_docs()
@view_api.route("/", methods=["GET"])
@api_login(required_priv=["R"])
def get_views(user: User, **kwargs):
    """Get a list of views the user can use to filter hits

    Variables:
    None

    Optional Arguments:
    None

    Result Example:
    [
        ...views    # A list of views the user can use
    ]
    """
    try:
        return ok(
            datastore().view.search(
                f"type:global OR owner:({user['uname']} OR none)", as_obj=False, rows=1000, sort="title asc"
            )["items"]
        )
    except ValueError as e:
        return bad_request(err=str(e))


@generate_swagger_docs()
@view_api.route("/", methods=["POST"])
@api_login(required_priv=["R", "W"])
def create_view(**kwargs):
    """Create a new view

    Variables:
    None

    Optional Arguments:
    None

    Data Block:
    {
        "title": "New View"     # The name of this view
        "query": "howler.id:*"  # The query to run
        "type": "global"        # The type of view - personal or global
    }

    Result Example:
    {
        ...view            # The new view data
    }
    """
    view_data = request.json
    if not isinstance(view_data, dict):
        return bad_request(err="Invalid data format")

    if "title" not in view_data:
        return bad_request(err="You must specify a title when creating a view.")

    if "query" not in view_data:
        return bad_request(err="You must specify a query when creating a view.")

    if "type" not in view_data:
        return bad_request(err="You must specify a type when creating a view.")

    storage = datastore()

    try:
        # Make sure the query is valid
        storage.hit.search(view_data["query"])

        view = View(view_data)

        view.owner = kwargs["user"]["uname"]

        if view.type == "personal":
            current_user = storage.user.get_if_exists(kwargs["user"]["uname"])

            current_user.favourite_views.append(view.view_id)

            storage.user.save(current_user["uname"], current_user)

        storage.view.save(view.view_id, view)
        return created(view)
    except SearchException:
        return bad_request(err="You must use a valid query when creating a view.")
    except HowlerException as e:
        return bad_request(err=str(e))


@generate_swagger_docs()
@view_api.route("/<view_id>", methods=["DELETE"])
@api_login(required_priv=["W"])
def delete_view(view_id: str, user: User, **kwargs):
    """Delete a view

    Variables:
    view_id => The id of the view to delete

    Optional Arguments:
    None

    Data Block:
    None

    Result Example:
    {
        "success": true     # Did the deletion succeed?
    }
    """
    storage = datastore()

    existing_view: View = storage.view.get_if_exists(view_id)
    if not existing_view:
        return not_found(err="This view does not exist")

    if existing_view.owner != user.uname and "admin" not in user.type:
        return forbidden(err="You cannot delete a view unless you are an owner or a global admin.")

    if existing_view.type == "readonly":
        return forbidden(err="You cannot delete built-in views.")

    success = storage.view.delete(view_id)

    storage.view.commit()

    return no_content({"success": success})


@generate_swagger_docs()
@view_api.route("/<view_id>", methods=["PUT"])
@api_login(required_priv=["R", "W"])
def update_view(view_id: str, user: User, **kwargs):
    """Update a view

    Variables:
    view_id => The view_id of the view to modify

    Optional Arguments:
    None

    Data Block:
    {
        "title": "New View Name"    # The name of this view
        "query": "howler.id:*"      # The query to run
    }

    Result Example:
    {
        ...view     # The updated view data
    }
    """
    new_data = request.json
    if not isinstance(new_data, dict):
        return bad_request(err="Invalid data format")

    # .isdisjoint() is a very clean, fast way to check for restricted keys
    if not new_data.keys().isdisjoint({"view_id", "owner"}):
        return bad_request(err="You cannot change the owner or id of a view.")

    storage = datastore()
    existing_view: View = storage.view.get_if_exists(view_id)

    if not existing_view:
        return not_found(err="This view does not exist")

    # Delegate the heavy auth checks to the helper function
    auth_error = _get_edit_auth_error(existing_view, user)
    if auth_error:
        return forbidden(err=auth_error)

    if "query" in new_data:
        try:
            storage.hit.search(new_data["query"])
        except SearchException:
            return bad_request(err="You must use a valid query when updating a view.")
        except HowlerException as e:
            return bad_request(err=str(e))

    updated_primitives = merge({}, existing_view.as_primitives(), new_data)
    new_view = View(cast(dict, updated_primitives))

    storage.view.save(new_view.view_id, new_view)
    storage.view.commit()

    return ok(storage.view.get_if_exists(new_view.view_id, as_obj=False))


@generate_swagger_docs()
@view_api.route("/<view_id>/favourite", methods=["POST"])
@api_login(required_priv=["R", "W"])
def set_as_favourite(view_id: str, **kwargs):
    """Add a view to a list of the user's favourites

    Variables:
    view_id => The id of the view to add as a favourite

    Optional Arguments:
    None

    Data Block:
    {}  # Empty

    Result Example:
    {
        "success": True     # If the operation succeeded
    }
    """
    storage = datastore()

    existing_view: View = storage.view.get_if_exists(view_id)
    if not existing_view:
        return not_found(err="This view does not exist")

    if existing_view.type != "global" and kwargs["user"]["uname"] != existing_view.owner and existing_view.owner:
        return forbidden(err="You can only favourite global views, or views owned by you.")

    try:
        current_user = storage.user.get_if_exists(kwargs["user"]["uname"])

        current_user["favourite_views"] = list(set(current_user.favourite_views + [view_id]))

        storage.user.save(current_user["uname"], current_user)

        return ok()
    except ValueError as e:
        return bad_request(err=str(e))


@generate_swagger_docs()
@view_api.route("/<view_id>/favourite", methods=["DELETE"])
@api_login(required_priv=["R", "W"])
def remove_as_favourite(view_id: str, **kwargs):
    """Remove a view from a list of the user's favourites

    Variables:
    view_id => The id of the view to remove as a favourite

    Optional Arguments:
    None

    Result Example:
    {
        "success": True     # If the operation succeeded
    }
    """
    storage = datastore()

    try:
        current_user = storage.user.get_if_exists(kwargs["user"]["uname"])

        current_favourites: list[str] = current_user.favourite_views

        if view_id not in current_favourites:
            return not_found(err="View is not favourited.")

        current_user["favourite_views"] = [favourite for favourite in current_favourites if favourite != view_id]

        storage.user.save(current_user["uname"], current_user)

        return no_content()
    except ValueError as e:
        return bad_request(err=str(e))


# region Permission


@generate_swagger_docs()
@view_api.route("/<view_id>/permission", methods=["PUT"])
@api_login(required_priv=["R", "W"])
def give_privilege(view_id: str, user: User, **kwargs):
    """give permission from one user to an other.

    The json object need to send "privilege", "user_id" as a key.
    privilege : The value need to be one of ["administrator", "member", "owner"]
    user_id : the value need to be the user to add or remove from the permission
    is_adding: The value neeed to be a boolean representing if we add or remove a user.

    Variables:
    view_id => The id of the view to give administrative privilege of

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
        item_id=escape(str(view_id)),
        level_requested=priv_requested,
        member_to_modify=user_to_add,
        item_type=View,
    )

    if isinstance(result, str):
        return bad_request(err=result)

    if not isinstance(result[1], View):
        return bad_request(err=f"Wrong request type. Object of type {type(result[1])} was requested insted of View")

    storage, existing_view = result

    priv_map: dict = existing_view.get_privilege_mapping()

    priv_request: str = escape(str(priv_requested))
    is_allowed: bool = is_allowed_to_change(level_requested=priv_request, user=user, existing_item=existing_view)

    if not is_allowed:
        return bad_request(err=f'You are not allowed to give the privilege "{priv_request}" for this view ')

    if priv_request == "owner":
        if existing_view.owner == user_to_add:
            return bad_request(err=f"{user_to_add} already have the permission {priv_request}")
        existing_view.set_privilege_mapping(priv_request, user_to_add)
    else:
        if user_to_add in priv_map[priv_request]:
            return bad_request(err=f"{user_to_add} already have the permission {priv_request}")

        existing_view.set_privilege_mapping(priv_request, priv_map[priv_request] + [user_to_add])

    storage.view.save(existing_view.view_id, existing_view)

    storage.view.commit()
    return ok(storage.view.get_if_exists(existing_view.view_id, as_obj=False))


@generate_swagger_docs()
@view_api.route("/<view_id>/permission", methods=["DELETE"])
@api_login(required_priv=["R", "W"])
def revoke_privilege(view_id: str, user: User, **kwargs):
    """Revoke permission from one user to another.

    Variables:
        view_id => The id of the view to revoke administrative privilege of

    Arguments:
        None

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
        item_id=escape(str(view_id)),
        level_requested=priv_requested,
        member_to_modify=user_to_remove,
        is_adding=False,
        item_type=View,
    )

    if isinstance(result, str):
        return bad_request(err=result)

    if not isinstance(result[1], View):
        return bad_request(err=f"Wrong request type. Object of type {type(result[1])} was requested insted of View")

    storage, existing_view = result

    priv_map = existing_view.get_privilege_mapping()

    priv_request: str = escape(str(priv_requested))
    is_allowed: bool = is_allowed_to_change(level_requested=priv_request, user=user, existing_item=existing_view)

    if not is_allowed:
        return bad_request(err=f"You are not allowed to give {priv_request} on view {view_id}")

    if priv_request == "owner":
        return bad_request(err="You cannot remove the owner of a view. Transfer ownership instead.")

    if user_to_remove not in priv_map[priv_request]:
        return bad_request(err=f"{user_to_remove} is not in the {priv_request} premission group")
    existing_view.remove_privilege_mapping(priv_request, user_to_remove)

    storage.view.save(existing_view.view_id, existing_view)

    storage.view.commit()

    return ok(storage.view.get_if_exists(existing_view.view_id, as_obj=False))


@generate_swagger_docs()
@view_api.route("/<view_id>/permission_options", methods=["GET"])
@api_login(required_priv=["R", "W"], required_type=["automation_basic"])
def get_permission_option(view_id: str, user: User):
    """Get the permission options for a given view

    Variables:
    view_id => The id of the view to remove administrative privilege of

     The json object need to send "privilege", "user_id" as a key.
    privilege : The value need to be one of ["administrator", "member", "owner"]
    user_id : the value need to be the user to add or remove from the permission
    is_adding: The value neeed to be a boolean representing if we add or remove a user.

    Arguments:
        view_id: The id of the view to get permissions for
        user: The user making the request (injected by the api_login decorator)
    Optional Arguments:
        None
    Result Example:
         {
            "administrator": [ # Each entry corresponds to a given privilege level
                "user1", "user2" # A list of users that have this privilege
            ],
            "member": [
                "user3"
            ],
            "owner": "user4"
        }
    returns a dict with the possible permissions for the view and the users that have them.
    """
    ds = datastore()
    view: View = ds.view.get(view_id)
    if not view:
        return not_found(err="The specified view does not exist")

    return ok(view.get_privilege_mapping())


@generate_swagger_docs()
@view_api.route("/<view_id>/permission_options", methods=["GET"])
@api_login(required_priv=["R"])
def get_view_permission_options(view_id: str, user: User, **kwargs):
    """Get privilege/permission mapping for a given view"""
    ds = datastore()

    view: View = ds.view.get(view_id)
    if not view:
        return not_found(err="The specified view does not exist")

    # Returns ONLY the dictionary with owner, administrator, and member lists
    return ok(view.get_privilege_mapping())


# endregion
