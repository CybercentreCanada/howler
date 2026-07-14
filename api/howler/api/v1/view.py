from typing import cast

from flask import request
from markupsafe import escape
from mergedeep.mergedeep import merge

from howler.api import bad_request, created, forbidden, make_subapi_blueprint, no_content, not_found, ok
from howler.api.v1.utils.params import parse_parameters, parse_refresh
from howler.common.exceptions import (
    HowlerException,
    HowlerInvalidParameterException,
    HowlerInvalidPermissionException,
    InvalidDataException,
)
from howler.common.loader import datastore
from howler.common.logging import get_logger
from howler.common.swagger import generate_swagger_docs
from howler.datastore.exceptions import SearchException
from howler.datastore.howler_store import HowlerDatastore
from howler.odm.models.user import User
from howler.odm.models.view import View
from howler.security import api_login
from howler.services import permission_service

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
    try:
        refresh = parse_refresh(request.args.get("refresh"))
    except HowlerInvalidParameterException as e:
        return bad_request(err=str(e))

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

        storage.view.save(view.view_id, view, refresh=refresh)
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
    try:
        refresh = parse_refresh(request.args.get("refresh"))
    except (InvalidDataException, ValueError) as e:
        return bad_request(err=f"Invalid refresh parameter: {str(e)}")

    existing_view: View = storage.view.get_if_exists(view_id)

    if not existing_view:
        return not_found(err="This view does not exist")

    if existing_view.owner != user.uname and "admin" not in user.type:
        return forbidden(err="You cannot delete a view unless you are an owner or a global admin.")

    if existing_view.type == "readonly":
        return forbidden(err="You cannot delete built-in views.")

    success = storage.view.delete(view_id, refresh=refresh)

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
    refresh = kwargs.get("refresh")

    storage = datastore()

    new_data = request.json
    if not isinstance(new_data, dict):
        return bad_request(err="Invalid data format")

    if set(new_data.keys()) & {"view_id", "owner"}:
        return bad_request(err="You cannot change the owner or id of a view.")

    existing_view: View = storage.view.get_if_exists(view_id)
    if not existing_view:
        return not_found(err="This view does not exist")

    if existing_view.type == "readonly":
        return forbidden(err="You cannot edit a built-in view.")

    if existing_view.type == "personal" and existing_view.owner != user.uname:
        return forbidden(err="You cannot update a personal view that is not owned by you.")
    is_member = (
        existing_view.owner != user.uname
        or user.uname not in existing_view.admins
        or user.uname not in existing_view.members
    )
    if existing_view.type == "global" and is_member and "admin" not in user.type:
        return forbidden(err="Only the owner of a view and administrators can edit a global view.")

    new_view = View(cast(dict, merge({}, existing_view.as_primitives(), new_data)))

    storage.view.save(new_view.view_id, new_view, refresh=refresh)

    try:
        if "query" in new_data:
            # Make sure the query is valid
            storage.hit.search(new_data["query"])
    except SearchException:
        return bad_request(err="You must use a valid query when updating a view.")
    except HowlerException as e:
        return bad_request(err=str(e))

    return ok(new_view.as_primitives())


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

    if (
        existing_view.type != "global"
        and kwargs["user"]["uname"] != existing_view.owner
        and existing_view.owner != "none"
    ):
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
@parse_parameters(refresh=parse_refresh)
def give_privilege(view_id: str, user: User, **kwargs):
    """Grant a privilege on a view to another user.

    Variables:
    view_id => The ID of the view for which to grant a privilege

    Optional Arguments:
        refresh : boolean requesting to refresh DB before returning

    Data Block:
    {
        "privilege": "privilege to grant"  # [members, admins, owner]
        "user_id": "user to grant permission to"
    }

    Result Example:
    {
        "success": True     # If the operation succeeded
    }
    """
    temp_value: tuple[HowlerDatastore, str, str] | str = permission_service.get_require_data_helper(request.json)
    refresh = kwargs.get("refresh")
    if isinstance(temp_value, str):
        return bad_request(err=temp_value)

    storage, priv_requested, user_to_add = temp_value  # TODO: storage is not used here

    result = storage.view.get_if_exists(escape(str(view_id)))

    if not result:
        return not_found(err="This view does not exist")

    if not isinstance(result, View):
        return bad_request(err=f"Wrong request type. Object of type {type(result)} was requested insted of View")

    priv_request: str = escape(str(priv_requested))

    try:
        success, result = permission_service.set_privilege(priv_request, user_to_add, result, user)
    except HowlerInvalidPermissionException as e:
        return forbidden(err=e.message)
    except InvalidDataException as e:
        return bad_request(err=e.message)

    if success:
        storage.view.save(result.view_id, result, refresh=refresh)

    return ok(result.as_primitives())


@generate_swagger_docs()
@view_api.route("/<view_id>/permission", methods=["DELETE"])
@parse_parameters(refresh=parse_refresh)
@api_login(required_priv=["R", "W"])
def revoke_privilege(view_id: str, user: User, **kwargs):
    """Revoke permission from one user to another.

    Variables:
        view_id => The id of the view to revoke administrative privilege of

    Arguments:
        view_id: The id of the view to revoke administrative privilege of
        user: The user making the request (injected by the api_login decorator)

    Optional Arguments:
    refresh =>  ('true' | 'false' | 'wait_for') Whether to refresh the datastore before returning.
        'wait_for' will wait for the change to be visible in search.

    Data Block:
        {
            "privilege": "privilege to revoke",  # [members, admins, owner]
            "user_id": "user to remove permission from",
        }

    Result Example:
        {
            "success": True
        }
    """
    temp_value: tuple[HowlerDatastore, str, str] | str = permission_service.get_require_data_helper(request.json)
    refresh = kwargs.get("refresh")

    if isinstance(temp_value, str):
        return bad_request(err=temp_value)

    storage, priv_requested, user_to_remove = temp_value
    result = storage.view.get_if_exists(escape(str(view_id)))

    if not result:
        return not_found(err="This view does not exist")

    if not isinstance(result, View):
        return bad_request(err=f"Wrong request type. Object of type {type(result)} was requested insted of View")

    priv_request: str = escape(str(priv_requested))

    if priv_request == "owner":
        return bad_request(err="You cannot remove the owner privilege of a view. Transfer ownership instead.")

    current_members = result.admins if priv_request == "admins" else result.members
    if user_to_remove not in current_members:
        return bad_request(err=f"{user_to_remove} is not in the {priv_request} permission group")

    try:
        success, result = permission_service.remove_privilege(priv_request, user_to_remove, result, user)
    except HowlerInvalidPermissionException as e:
        return forbidden(err=e.message)
    except InvalidDataException as e:
        return bad_request(err=e.message)

    if success:
        storage.view.save(result.view_id, result, refresh=refresh)

    return ok(result.as_primitives())


# endregion
