from flask import request

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
from howler.common.exceptions import ForbiddenException, HowlerException, InvalidDataException, NotFoundException
from howler.common.loader import datastore
from howler.common.logging import get_logger
from howler.common.swagger import generate_swagger_docs
from howler.odm.models.dossier import Dossier
from howler.odm.models.user import User
from howler.security import api_login
from howler.services import dossier_service, lucene_service

SUB_API = "dossier"
dossier_api = make_subapi_blueprint(SUB_API, api_version=1)
dossier_api._doc = "Manage the different dossiers created for filtering hits"

logger = get_logger(__file__)


@generate_swagger_docs()
@dossier_api.route("/", methods=["GET"])
@api_login(required_priv=["R"])
def get_dossiers(user: User, **kwargs):
    """Get a list of dossiers the user can see

    Variables:
    None

    Optional Arguments:
    None

    Result Example:
    [
        ...dossiers    # A list of dossiers the user can use
    ]
    """
    try:
        return ok(
            datastore().dossier.search(
                f"type:global OR owner:({user['uname']} OR none)",
                as_obj=False,
                rows=1000,
            )["items"]
        )
    except ValueError as e:
        return bad_request(err=str(e))


@generate_swagger_docs()
@dossier_api.route("/", methods=["POST"])
@api_login(required_priv=["R", "W"])
def create_dossier(**kwargs):
    """Create a new dossier

    Variables:
    None

    Optional Arguments:
    None

    Data Block:
    {
        "title": "New dossier"     # The name of this dossier
        "query": "howler.id:*"  # The query to run
        "type": "global"        # The type of dossier - personal or global
    }

    Result Example:
    {
        ...dossier            # The new dossier data
    }
    """
    dossier_data = request.json

    try:
        return created(dossier_service.create_dossier(dossier_data, username=kwargs["user"]["uname"]))
    except InvalidDataException as e:
        return bad_request(err=str(e))
    except HowlerException:
        logger.exception("Exception on create dossier")
        return internal_error(err="An unknown error occured when creating the dossier.")


@generate_swagger_docs()
@dossier_api.route("/<id>", methods=["GET"])
@api_login(required_priv=["R"])
def get_dossier(id: str, user: User, **kwargs):
    """Get a specific dossier

    Variables:
    id => The id of the dossier to get

    Optional Arguments:
    None

    Result Example:
    [
        ...dossiers    # A list of dossiers the user can use
    ]
    """
    try:
        results = datastore().dossier.search(
            f"dossier_id:{id}",
            as_obj=False,
            rows=1,
        )["items"]

        if len(results) < 1:
            return not_found(err="Dossier not found")

        return ok(results[0])
    except ValueError as e:
        return bad_request(err=str(e))


@generate_swagger_docs()
@dossier_api.route("/hit/<id>", methods=["GET"])
@api_login(required_priv=["R"])
def get_dossier_for_hit(id: str, user: User, **kwargs):
    """Get dossiers matching a given hit

    Variables:
    id => The id of the dossier to get

    Optional Arguments:
    None

    Result Example:
    [
        ...dossiers    # A list of dossiers the user can use
    ]
    """
    storage = datastore()
    try:
        response = storage.hit.search(f"howler.id:{id}", rows=1)

        if response["total"] < 1:
            return not_found(err="Hit does not exist.")

        hit = response["items"][0]

        results: list[Dossier] = storage.dossier.search(
            "dossier_id:*",
            as_obj=True,
            rows=1000,
        )["items"]

        matching_dossiers: list[Dossier] = []
        for dossier in results:
            if dossier.query is None:
                matching_dossiers.append(dossier)
                continue

            if lucene_service.match(dossier.query, hit.as_primitives()):
                matching_dossiers.append(dossier)

        return ok(matching_dossiers)
    except ValueError as e:
        return bad_request(err=str(e))


@generate_swagger_docs()
@dossier_api.route("/<id>", methods=["DELETE"])
@api_login(required_priv=["W"])
def delete_dossier(id: str, user: User, **kwargs):
    """Delete a dossier

    Variables:
    id => The id of the dossier to delete

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

    existing_dossier: Dossier = storage.dossier.get_if_exists(id)
    if not existing_dossier:
        return not_found(err="This dossier does not exist")

    if existing_dossier.owner != user.uname and "admin" not in user.type:
        return forbidden(err="You cannot delete a dossier unless you are an administrator, or the owner.")

    success = storage.dossier.delete(id)

    storage.dossier.commit()

    return no_content({"success": success})


@generate_swagger_docs()
@dossier_api.route("/<id>", methods=["PUT"])
@api_login(required_priv=["R", "W"])
def update_dossier(id: str, user: User, **kwargs):
    """Update a dossier

    Variables:
    id => The id of the dossier to modify

    Optional Arguments:
    None

    Data Block:
    {
        "title": "New dossier Name"    # The name of this dossier
        "query": "howler.id:*"      # The query to run
    }

    Result Example:
    {
        ...dossier     # The updated dossier data
    }
    """
    new_data = request.json
    if not isinstance(new_data, dict):
        return bad_request(err="Invalid data format")

    try:
        updated_dossier = dossier_service.update_dossier(id, new_data, user)

        return ok(updated_dossier)
    except ForbiddenException as e:
        return forbidden(err=e.message)
    except InvalidDataException as e:
        return bad_request(err=e.message)
    except NotFoundException as e:
        return not_found(err=e.message)
    except HowlerException as e:
        logger.exception("Unknown error on dossier update:")
        return internal_error(err=e.message)
