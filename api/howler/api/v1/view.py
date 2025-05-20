from flask import request
from mergedeep.mergedeep import merge

from howler.api import (
    bad_request,
    created,
    forbidden,
    make_subapi_blueprint,
    no_content,
    not_found,
    ok,
)
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
view_api._doc = "Manage the different views created for filtering hits"

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
                f"type:global OR owner:({user['uname']} OR none)",
                as_obj=False,
                rows=1000,
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

            current_user["favourite_views"] = current_user.get("favourite_views", []) + [view.view_id]

            storage.user.save(current_user["uname"], current_user)

        storage.view.save(view.view_id, view)
        return created(view)
    except SearchException:
        return bad_request(err="You must use a valid query when creating a view.")
    except HowlerException as e:
        return bad_request(err=str(e))


@generate_swagger_docs()
@view_api.route("/<id>", methods=["DELETE"])
@api_login(required_priv=["W"])
def delete_view(id: str, user: User, **kwargs):
    """Delete a view

    Variables:
    id => The id of the view to delete

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

    existing_view: View = storage.view.get_if_exists(id)
    if not existing_view:
        return not_found(err="This view does not exist")

    if existing_view.owner != user.uname and "admin" not in user.type:
        return forbidden(err="You cannot delete a view unless you are an administrator, or the owner.")

    if existing_view.type == "readonly":
        return forbidden(err="You cannot delete built-in views.")

    success = storage.view.delete(id)

    storage.view.commit()

    return no_content({"success": success})


@generate_swagger_docs()
@view_api.route("/<id>", methods=["PUT"])
@api_login(required_priv=["R", "W"])
def update_view(id: str, user: User, **kwargs):
    """Update a view

    Variables:
    id => The id of the view to modify

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

    if set(new_data.keys()) - {"title", "query", "span", "sort", "settings"}:
        return bad_request(err="Only title, query, span and sort can be updated.")

    existing_view: View = storage.view.get_if_exists(id)
    if not existing_view:
        return not_found(err="This view does not exist")

    if existing_view.type == "readonly":
        return forbidden(err="You cannot edit a built-in view.")

    if existing_view.type == "personal" and existing_view.owner != user.uname:
        return forbidden(err="You cannot update a personal view that is not owned by you.")

    if existing_view.type == "global" and existing_view.owner != user.uname and "admin" not in user.type:
        return forbidden(err="Only the owner of a view and administrators can edit a global view.")

    new_view = View(merge({}, existing_view.as_primitives(), new_data))

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
@view_api.route("/<id>/favourite", methods=["POST"])
@api_login(required_priv=["R", "W"])
def set_as_favourite(id: str, **kwargs):
    """Add a view to a list of the user's favourites

    Variables:
    id => The id of the view to add as a favourite

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

    existing_view: View = storage.view.get_if_exists(id)
    if not existing_view:
        return not_found(err="This view does not exist")

    if existing_view.type != "global" and (
        existing_view.owner != kwargs["user"]["uname"] and existing_view.owner != "none"
    ):
        return forbidden(err="You can only favourite global views, or views owned by you.")

    try:
        current_user = storage.user.get_if_exists(kwargs["user"]["uname"])

        current_user["favourite_views"] = list(set(current_user.get("favourite_views", []) + [id]))

        storage.user.save(current_user["uname"], current_user)

        return ok()
    except ValueError as e:
        return bad_request(err=str(e))


@generate_swagger_docs()
@view_api.route("/<id>/favourite", methods=["DELETE"])
@api_login(required_priv=["R", "W"])
def remove_as_favourite(id, **kwargs):
    """Remove a view from a list of the user's favourites

    Variables:
    id => The id of the view to remove as a favourite

    Optional Arguments:
    None

    Result Example:
    {
        "success": True     # If the operation succeeded
    }
    """
    storage = datastore()

    if not storage.view.exists(id):
        return not_found(err="This view does not exist")

    try:
        current_user = storage.user.get_if_exists(kwargs["user"]["uname"])

        current_user["favourite_views"] = list(filter(lambda f: f != id, current_user.get("favourite_views", [])))

        storage.user.save(current_user["uname"], current_user)

        return no_content()
    except ValueError as e:
        return bad_request(err=str(e))
