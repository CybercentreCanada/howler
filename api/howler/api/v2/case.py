from howler.api import bad_request, forbidden, make_subapi_blueprint, no_content, not_found, ok
from howler.common.loader import datastore
from howler.common.logging import get_logger
from howler.common.swagger import generate_swagger_docs
from howler.odm.models.user import User
from howler.security import api_login

SUB_API = "case"
case_api = make_subapi_blueprint(SUB_API, api_version=2)
case_api._doc = "Manage the different cases created"  # type: ignore

logger = get_logger(__file__)


@generate_swagger_docs()
@case_api.route("/", methods=["POST"])
@api_login(required_priv=["R", "W"])
def create_case(**kwargs):
    """Create a new case

    Variables:
    None

    Optional Arguments:
    None

    Data Block:
    {
        "title": "New case"     # The name of this case
    }

    Result Example:
    {
        ...case            # The new case data
    }
    """
    raise NotImplementedError()


@generate_swagger_docs()
@case_api.route("/<id>", methods=["GET"])
@api_login(required_priv=["R"])
def get_case(id: str, user: User, **kwargs):
    """Get a specific case

    Variables:
    id => The id of the case to get

    Optional Arguments:
    None

    Result Example:
    {
        ...case    # The requested case, if it exists
    }
    """
    try:
        results = datastore().case.search(
            f"case_id:{id}",
            as_obj=False,
            rows=1,
        )["items"]

        if len(results) < 1:
            return not_found(err="Case not found")

        return ok(results[0])
    except ValueError as e:
        return bad_request(err=str(e))


@generate_swagger_docs()
@case_api.route("/<id>", methods=["DELETE"])
@api_login(required_priv=["W"])
def delete_case(id: str, user: User, **kwargs):
    """Delete a case

    Variables:
    id => The id of the case to delete

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

    existing_case = storage.case.get_if_exists(id)
    if not existing_case:
        return not_found(err="This case does not exist")

    if "admin" not in user.type:
        return forbidden(err="You cannot delete a case unless you are an administrator, or the owner.")

    success = storage.case.delete(id)

    storage.case.commit()

    return no_content({"success": success})


@generate_swagger_docs()
@case_api.route("/<id>", methods=["PUT"])
@api_login(required_priv=["R", "W"])
def update_case(id: str, user: User, **kwargs):
    """Update a case

    Variables:
    id => The id of the case to modify

    Optional Arguments:
    None

    Data Block:
    {
        "title": "New case Name"    # The name of this case
    }

    Result Example:
    {
        ...case     # The updated case data
    }
    """
    raise NotImplementedError()
