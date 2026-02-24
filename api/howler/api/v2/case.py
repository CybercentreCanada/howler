from typing import Any

from flask import request

from howler.api import bad_request, created, forbidden, make_subapi_blueprint, no_content, not_found, ok
from howler.common.exceptions import HowlerException, InvalidDataException, NotFoundException, ResourceExists
from howler.common.loader import datastore
from howler.common.logging import get_logger
from howler.common.swagger import generate_swagger_docs
from howler.odm.models.case import Case
from howler.odm.models.user import User
from howler.security import api_login
from howler.services import case_service
from howler.utils.str_utils import sanitize_lucene_query

SUB_API = "case"
case_api = make_subapi_blueprint(SUB_API, api_version=2)
case_api._doc = "Manage the different cases created"  # type: ignore

logger = get_logger(__file__)


@generate_swagger_docs()
@case_api.route("/", methods=["POST"])
@api_login(required_priv=["R", "W"])
def create_cases(user: User, **kwargs):
    """Create cases.

    Variables:
    None

    Arguments:
    None

    Data Block:
    {
        [
            {
                ...case
            },
            {
                ...case
            }
        ]
    }

    Result Example:
    {
        "valid": [
            {
                ...case
            },
            {
                ...case
            }
        ],
        "invalid": [
            {
                "input": { ...case },
                "error": "Id already exists"
            },
            {
                "input": { ...case },
                "error": "Object 'Case' expected a parameter named: title"
            }
        ]
    }
    """
    cases = request.json

    if cases is None:
        return bad_request(err="No cases were sent.")

    response_body: dict[str, list[Any]] = {"valid": [], "invalid": []}
    odms: list[tuple[str, Case]] = []

    for case_data in cases:
        try:
            case_id = case_data.get("case_id") or (
                f"case-{sanitize_lucene_query(case_data.get('title', 'untitled')).lower().replace(' ', '-')}"
            )
            case_data["case_id"] = case_id

            if case_service.exists(case_id):
                raise ResourceExists(f"Case {case_id} already exists in datastore")

            odm = Case(case_data)
            response_body["valid"].append(odm.as_primitives())
            odms.append((case_id, odm))
        except HowlerException as e:
            logger.warning(f"{type(e).__name__} when saving new case!")
            logger.warning(e)
            response_body["invalid"].append({"input": case_data, "error": str(e)})

    if len(response_body["invalid"]) == 0:
        if len(odms) > 0:
            for case_id, odm in odms:
                case_service.create_case(case_id, odm, user=user.uname, skip_exists=True)

            datastore().case.commit()

        return created(response_body)
    else:
        err_msg = ", ".join(item["error"] for item in response_body["invalid"])

        return bad_request(response_body, err=err_msg)


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

    non_existing_case_ids = [case_id for case_id in case_ids if not case_service.exists(case_id)]

    if non_existing_case_ids:
        return not_found(err=f"Case id(s) {', '.join(non_existing_case_ids)} do not exist.")

    case_service.delete_cases(case_ids)

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
