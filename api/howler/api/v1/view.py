from typing import cast

from flask import Response, request
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

        view.owner = [kwargs["user"]["uname"]]

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

    # TODO: AG verify this work properly.
    if (user.uname not in existing_view.owner) and "admin" not in user.type:
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

    if existing_view.type == "personal" and user.uname in existing_view.owner:
        return forbidden(err="You cannot update a personal view that is not owned by you.")

    allowed_list: list[str] = existing_view.owner + existing_view.admin + existing_view.member
    if existing_view.type == "global" and (user.uname not in allowed_list) and "admin" not in user.type:
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
        kwargs["user"]["uname"] not in existing_view.owner and existing_view.owner != []
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


# Region: Permission


def __priviledge_value_verifications(
    view_id: str, is_adding: bool = True
) -> tuple[HowlerDatastore, dict, str, View] | Response:
    """Verify base value for privilege request are usable.

    If they are it return them else it return the error.
    give permission from one user to an other.

    Variables:
    view_id => The id of the view to give administrative priviledge of
    is_adding => is the verification to remove or to add someone to a group
    """
    storage = datastore()
    priv_change = request.json
    if not isinstance(priv_change, dict):
        return bad_request(err="Invalid data format")
    if not set(priv_change.keys()) & {"priviledge", "user_id"}:
        return bad_request(err="Invalid data format. Need new priviledge and user_id")
    user_name: str = priv_change["user_id"]

    if is_adding:
        temp_user = storage.user.get_if_exists(user_name)
        if not temp_user:
            return bad_request(err=f"Invalid data format. user id {priv_change['user_id']} does not exist")
        user_name = temp_user.uname

    existing_view: View = storage.view.get_if_exists(view_id)
    if not existing_view:
        return not_found(err="This view does not exist")

    return storage, priv_change, user_name, existing_view


def __is_allowed_to_change(priv_request: str, user: User, existing_view: View) -> None | Response:
    """Verify for privilege request if they are allowed to request the change or not.

    Variables:
    priv_request => The priviledge level requested base on the string from the object [administrator, member, owner]
    user => The user requesting the change
    existing_view => The view that will be change
    """
    if priv_request not in existing_view.get_priviledge_mapping():
        return bad_request(err=f"Wrong request. This priviledge {priv_request} does not exist.")

    is_view_admin: bool = user.uname in existing_view.admin or user.uname in existing_view.owner

    if not is_view_admin and "admin" not in user.type:
        return bad_request(err="You cannot give administrative priviledge for this view.")

    if priv_request == "owner" and user.uname not in existing_view.owner and not "admin" not in user.type:
        return bad_request(err="You cannot give owner priviledge for this view.")
    # use the maping to update the list to the proper priviledge

    return None


@generate_swagger_docs()
@view_api.route("/<view_id>/permission", methods=["PUT"])
@api_login(required_priv=["R", "W"])
def give_priviledge(view_id: str, user: User, **kwargs):
    """give permission from one user to an other.

    The json object need to send "priviledge", "user_id" as a key.
    priviledge : The value need to be one of ["administrator", "member", "owner"]
    user_id : the value need to be the user to add or remove from the permission
    is_adding: The value neeed to be a boolean representing if we add or remove a user.

    Variables:
    view_id => The id of the view to give administrative priviledge of

    Optional Arguments:
        None

    Result Example:
    {
        "success": True     # If the operation succeeded
    }
    """
    result = __priviledge_value_verifications(view_id)

    if isinstance(result, Response):
        return result

    storage, priv_change, user_add, existing_view = result

    priv_map: dict = existing_view.get_priviledge_mapping()

    priv_request: str = priv_change["priviledge"]
    is_allowed: None | Response = __is_allowed_to_change(
        priv_request=priv_request, user=user, existing_view=existing_view
    )

    if isinstance(result, Response):
        return is_allowed

    if user_add in priv_map[priv_request]:
        return bad_request(err=f"{user_add} already have the permission {priv_request}")

    priv_map[priv_request].append(str(user_add))

    storage.view.save(existing_view.view_id, existing_view)

    storage.view.commit()

    return ok(storage.view.get_if_exists(existing_view.view_id, as_obj=False))


@generate_swagger_docs()
@view_api.route("/<view_id>/permission", methods=["DELETE"])
@api_login(required_priv=["R", "W"])
def revoke_priviledge(view_id: str, user: User, **kwargs):
    """give permission from one user to an other.

    The json object need to send "priviledge", "user_id" as a key.
    priviledge : The value need to be one of ["administrator", "member", "owner"]
    user_id : the value need to be the user to add or remove from the permission
    is_adding: The value neeed to be a boolean representing if we add or remove a user.

    Variables:
    view_id => The id of the view to give administrative priviledge of

    Optional Arguments:
        None

    Result Example:
    {
        "success": True     # If the operation succeeded
    }
    """
    result = __priviledge_value_verifications(view_id=view_id, is_adding=False)

    if isinstance(result, Response):
        return result

    storage, priv_change, user_add, existing_view = result

    priv_map = existing_view.get_priviledge_mapping()

    priv_request: str = priv_change["priviledge"]
    is_allowed: None | Response = __is_allowed_to_change(
        priv_request=priv_request, user=user, existing_view=existing_view
    )

    if isinstance(result, Response):
        return is_allowed

    if user_add not in priv_map[priv_request]:
        return bad_request(err=f"{user_add} is not in the {priv_request} premission group")

    priv_map[priv_request].remove(str(user_add))

    storage.view.save(existing_view.view_id, existing_view)

    storage.view.commit()

    return ok(storage.view.get_if_exists(existing_view.view_id, as_obj=False))


# endRegion
