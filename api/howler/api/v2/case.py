from flask import request

from howler.api import bad_request, created, forbidden, make_subapi_blueprint, no_content, not_found, ok
from howler.common.exceptions import InvalidDataException, NotFoundException, ResourceExists
from howler.common.swagger import generate_swagger_docs
from howler.odm.models.user import User
from howler.security import api_login
from howler.services import case_service
from howler.utils.str_utils import sanitize_lucene_query

SUB_API = "case"
case_api = make_subapi_blueprint(SUB_API, api_version=2)
case_api._doc = "Manage the different cases created"  # type: ignore


@generate_swagger_docs()
@case_api.route("/", methods=["POST"])
@api_login(required_priv=["R", "W"])
def create_case(user: User, **kwargs):
    """Create a case.

    Variables:
    user      => The user creating the case (injected by @api_login)

    Data Block:
    {
        "title": "Case Title",
        "summary": "Brief description"
    }

    Result Example:
    {
        ...case     # The new case data
    }
    """
    case_data = request.json

    if not case_data or not isinstance(case_data, dict):
        return bad_request(err="Request body must be a JSON object with title and summary.")

    title = case_data.get("title")
    summary = case_data.get("summary")

    if not title or not summary:
        return bad_request(err="Both title and summary are required.")

    case_id = f"case-{sanitize_lucene_query(title).lower().replace(' ', '-')}"

    try:
        new_case = case_service.create_case(case_id, title, summary, user=user.uname)
        return created(new_case)
    except ResourceExists as e:
        return bad_request(err=str(e))


@generate_swagger_docs()
@case_api.route("/<id>", methods=["GET"])
@api_login(audit=True, required_priv=["R"])
def get_case(id: str, **kwargs):
    """Get a case.

    Variables:
    id       => Id of the case you would like to get

    Arguments:
    None

    Result Example:
    {
        ...case    # The requested case, if it exists
    }
    """
    case = case_service.get_case(id, as_odm=False)

    if not case:
        return not_found(err="Case %s does not exist" % id)

    return ok(case)


@generate_swagger_docs()
@case_api.route("/", methods=["DELETE"])
@api_login(required_priv=["W"])
def delete_cases(user: User, **kwargs):
    """Delete cases.

    Variables:
    None

    Arguments:
    None

    Data Block:
    [
        caseId, caseId, caseId
    ]

    Result Example:
    {
        "success": true             # Did the deletion succeed?
    }
    """
    case_ids = request.json

    if case_ids is None:
        return bad_request(err="No case ids were sent.")

    if "admin" not in user.type:
        return forbidden(err="Cannot delete case, only admin is allowed to delete")

    non_existing_case_ids = set([case_id for case_id in case_ids if not case_service.exists(case_id)])

    if non_existing_case_ids:
        return not_found(err=f"Case id(s) {', '.join(non_existing_case_ids)} do not exist.")

    case_service.delete_cases(case_ids)

    return no_content()


@generate_swagger_docs()
@case_api.route("/hide", methods=["POST"])
@api_login(required_priv=["W"])
def hide_cases(user: User, **kwargs):
    """Hide cases.

    Variables:
    None

    Arguments:
    None

    Data Block:
    [
        caseId, caseId, caseId
    ]

    Result Example:
    {
        "success": true             # Did the hiding succeed?
    }
    """
    case_ids = request.json

    if case_ids is None:
        return bad_request(err="No case ids were sent.")

    non_existing_case_ids = set([case_id for case_id in case_ids if not case_service.exists(case_id)])

    if non_existing_case_ids:
        return not_found(err=f"Case id(s) {', '.join(non_existing_case_ids)} do not exist.")

    case_service.hide_cases(case_ids, user=user.uname)

    return no_content()


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
    case_data = request.json

    if not case_data or not isinstance(case_data, dict):
        return bad_request(err="Request body must be a JSON object with fields to update.")

    try:
        updated_case = case_service.update_case(id, case_data, user)
        return ok(updated_case)
    except NotFoundException as e:
        return not_found(err=str(e))
    except InvalidDataException as e:
        return bad_request(err=str(e))
