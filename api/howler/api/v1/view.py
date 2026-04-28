from typing import cast

from flask import request
from mergedeep.mergedeep import merge

from howler.api import bad_request, created, forbidden, make_subapi_blueprint, no_content, not_found, ok
from howler.common.exceptions import HowlerException
from howler.common.loader import datastore
from howler.common.logging import get_logger
from howler.common.swagger import generate_swagger_docs
from howler.datastore.exceptions import SearchException
from howler.odm.models.user import User
from howler.odm.models.view import View
from howler.security import api_login

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

    # TODO: AG verify this work properly. Allowing the view admin to delete the branch as well.
    if (existing_view.owner != user.uname or existing_view.admin != user.uname) and "admin" not in user.type:
        return forbidden(err="You cannot delete a view unless you are an administrator, the owner or the view admin.")

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
    storage = datastore()

    new_data = request.json
    if not isinstance(new_data, dict):
        return bad_request(err="Invalid data format")

    if set(new_data.keys()) & {"view_id", "owner"}:
        # TODO : AG : Should I do this here insted ?
        return bad_request(err="You cannot change the owner or id of a view.")

    existing_view: View = storage.view.get_if_exists(view_id)
    if not existing_view:
        return not_found(err="This view does not exist")

    if existing_view.type == "readonly":
        return forbidden(err="You cannot edit a built-in view.")

    if existing_view.type == "personal" and existing_view.owner != user.uname:
        return forbidden(err="You cannot update a personal view that is not owned by you.")

    if existing_view.type == "global" and existing_view.owner != user.uname and "admin" not in user.type:
        return forbidden(err="Only the owner of a view and administrators can edit a global view.")

    new_view = View(cast(dict, merge({}, existing_view.as_primitives(), new_data)))

    storage.view.save(new_view.view_id, new_view)

    storage.view.commit()

    try:
        if "query" in new_data:
            # Make sure the query is valid
            storage.hit.search(new_data["query"])

        return ok(storage.view.get_if_exists(existing_view.view_id, as_obj=False))
    except SearchException:
        return bad_request(err="You must use a valid query when updating a view.")
    except HowlerException as e:
        return bad_request(err=str(e))


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

    if existing_view.type != "global" and (
        existing_view.owner != kwargs["user"]["uname"] and existing_view.owner != "none"
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


@generate_swagger_docs()
@view_api.route("/<view_id>", methods=["PUT"])
@api_login(required_priv=["R", "W"])
# TODO : AG : find a better name
def give_priviledge(view_id: str, user: User, **kwargs):
    """Transfer ownership from one user to an other.

    The json object need to send "priviledge", "user_id" as key.
    The value need to be one of "administrator", "member" or "owner"
    Variables:
    view_id => The id of the view to give administrative priviledge of


    Optional Arguments:
    None

    Result Example:
    {
        "success": True     # If the operation succeeded
    }
    """
    storage = datastore()
    new_data = request.json
    if not isinstance(new_data, dict):
        return bad_request(err="Invalid data format")

    # TODO : AG : will need to create that when calling the function ( the admin_uid value )
    # so when the user select the user he want to give admin it send the selected user
    if not set(new_data.keys()) & {"priviledge", "user_id"}:
        return bad_request(err="Invalid data format. Need new priviledge and user_id")

    existing_view: View = storage.view.get_if_exists(view_id)
    if not existing_view:
        return not_found(err="This view does not exist")

    priv_map: dict = {
        "administrator": existing_view.admin,
        "member": existing_view.member,
        "owner": existing_view.owner,
    }
    priv_request: str = new_data["priviledge"]

    if priv_request not in priv_map:
        return bad_request(err=f"Wrong request. This priviledge {priv_request} does not exist.")

    is_view_admin: bool = user.uname in existing_view.admin or user.uname in existing_view.owner
    if not is_view_admin and "admin" not in user.type:
        return bad_request(err="You cannot give administrative priviledge for this view.")

    if priv_request == "owner" and user.uname not in existing_view.owner and not "admin" not in user.type:
        return bad_request(err="You cannot give owner priviledge for this view.")
    priv_map[priv_request].append(str(new_data["user_id"]))

    storage.view.save(existing_view.view_id, existing_view)

    storage.view.commit()

    return ok(storage.view.get_if_exists(existing_view.view_id, as_obj=False))
