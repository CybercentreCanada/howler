from flask import request

from howler.api import (
    bad_request,
    conflict,
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
from howler.odm.models.overview import Overview
from howler.odm.models.user import User
from howler.security import api_login
from howler.utils.str_utils import sanitize_lucene_query

SUB_API = "overview"
overview_api = make_subapi_blueprint(SUB_API, api_version=1)
overview_api._doc = "Manage the different overviews created for viewing hits"

logger = get_logger(__file__)


@generate_swagger_docs()
@overview_api.route("/", methods=["GET"])
@api_login(required_priv=["R"])
def get_overviews(**kwargs):
    """Get a list of overviews the user can use to render hits

    Variables:
    None

    Optional Arguments:
    None

    Result Example:
    [
        ...overviews    # A list of overviews the user can use
    ]
    """
    try:
        return ok(
            datastore().overview.search(
                "overview_id:*",
                as_obj=False,
                rows=10000,
            )["items"]
        )
    except ValueError as e:
        return bad_request(err=str(e))


@generate_swagger_docs()
@overview_api.route("/", methods=["POST"])
@api_login(required_priv=["R", "W"])
def create_overview(**kwargs):
    """Create a new overview

    Variables:
    None

    Optional Arguments:
    None

    Data Block:
    {
        "analytic": "analytic name"                     # The analytic this overview applies to
        "detection": "detection name"                   # The detection this overview applies to
        "content": "# Hello, World!\n\nExample Text"    # The content to show when this overview matches a hit
    }

    Result Example:
    {
        ...overview            # The new overview data
    }
    """
    overview_data = request.json
    if not isinstance(overview_data, dict):
        return bad_request(err="Invalid data format")

    if "content" not in overview_data:
        return bad_request(err="You must specify content when creating an overview!")

    storage = datastore()

    try:
        overview = Overview(overview_data)

        overview.owner = kwargs["user"]["uname"]

        query_str = f"analytic:{sanitize_lucene_query(overview.analytic)}"

        if overview.detection:
            query_str += f" AND detection:{overview.detection}"
        else:
            query_str += " AND -_exists_:detection"

        if storage.overview.search(query_str)["total"] > 0:
            return conflict(err="An overview covering this case already exists.")

        storage.overview.save(overview.overview_id, overview)
        return created(overview)
    except HowlerException as e:
        return bad_request(err=str(e))


@generate_swagger_docs()
@overview_api.route("/<id>", methods=["DELETE"])
@api_login(required_priv=["W"])
def delete_overview(id: str, user: User, **kwargs):
    """Delete an overview

    Variables:
    id => The id of the overview to delete

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

    if not storage.overview.exists(id):
        return not_found(err="This overview does not exist")

    existing_overview: Overview = storage.overview.get_if_exists(id)

    if existing_overview.owner != user.uname and "admin" not in user.type:
        return forbidden(err="You cannot delete an overview that is not owned by you.")

    result = storage.overview.delete(id)
    if result:
        return no_content()
    else:
        return not_found()


@generate_swagger_docs()
@overview_api.route("/<id>", methods=["PUT"])
@api_login(required_priv=["R", "W"])
def update_overview_content(id: str, user: User, **kwargs):
    """Update an overview's content

    Variables:
    id => The id of the overview to modify

    Optional Arguments:
    None

    Data Block:
    {
        "content: "# New Markdown\n\nExample
    }

    Result Example:
    {
        ...overview     # The updated overview data
    }
    """
    storage = datastore()

    if not storage.overview.exists(id):
        return not_found(err="This overview does not exist")

    data = request.json
    if not data or not isinstance(data.get("content", None), str):
        return bad_request(err="New overview content must be a string.")

    content = data["content"]

    existing_overview: Overview = storage.overview.get_if_exists(id)

    existing_overview.content = content

    storage.overview.save(existing_overview.overview_id, existing_overview)

    try:
        return ok(storage.overview.get_if_exists(existing_overview.overview_id, as_obj=False))
    except HowlerException as e:
        return bad_request(err=str(e))
