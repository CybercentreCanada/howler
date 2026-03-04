from flask import request
from werkzeug.exceptions import UnsupportedMediaType

from howler.api import bad_request, created, internal_error, make_subapi_blueprint, no_content, not_found, ok
from howler.common.exceptions import HowlerException, InvalidDataException, NotFoundException, ResourceExists
from howler.common.loader import datastore
from howler.common.logging import get_logger
from howler.common.swagger import generate_swagger_docs
from howler.datastore.exceptions import DataStoreException
from howler.odm.models.user import User
from howler.security import api_login
from howler.services import case_service

SUB_API = "case"
case_api = make_subapi_blueprint(SUB_API, api_version=2)
case_api._doc = "Manage the different cases created"  # type: ignore

logger = get_logger(__file__)


@generate_swagger_docs()
@case_api.route("/", methods=["POST"])
@api_login(required_priv=["R", "W"])
def create_case(user: User, **kwargs):
    """Create a case.

    Variables:
    user      => The user creating the case (injected by @api_login)

    Arguments:
    None

    Data Block:
    {
        "title": "Case Title",
        "summary": "Brief description",
        ...                         # Any other valid case fields
    }

    Result Example:
    {
        ...case     # The new case data
    }
    """
    case_data = request.json

    if not case_data or not isinstance(case_data, dict):
        return bad_request(err="Request body must be a JSON object with case data.")

    try:
        new_case = case_service.create_case(case_data, user.uname)
        return created(new_case)
    except InvalidDataException as e:
        return bad_request(err=str(e))
    except ResourceExists as e:
        return bad_request(err=str(e))
    except HowlerException as e:
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
    case = datastore().case.get_if_exists(key=id, as_obj=False)

    if not case:
        return not_found(err="Case %s does not exist" % id)

    return ok(case)


@generate_swagger_docs()
@case_api.route("/", methods=["DELETE"])
@api_login(required_priv=["W"], required_type=["admin"])
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

    ds = datastore()

    non_existing_case_ids = set([case_id for case_id in case_ids if not ds.case.exists(case_id)])

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

    ds = datastore()

    non_existing_case_ids = set([case_id for case_id in case_ids if not ds.case.exists(case_id)])

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
        ...                        # Any other valid case fields to update
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


@generate_swagger_docs()
@case_api.route("/<id>/items", methods=["POST"])
@api_login(required_priv=["R", "W"])
def append_item(id: str, user: User, **kwargs):  # noqa: C901
    """Append an item to a case

    This endpoint adds a new item to a case's items list. The item can reference
    different types of objects (hits, observables, or other cases). When a hit or
    observable is added, a bidirectional relationship is created - the case will
    reference the item, and the item will reference the case in its related.cases list.

    Variables:
    id       => The id of the case to modify

    Arguments:
    None

    Data Block:
    {
        "type": "hit",            # Type of item to append: "hit", "observable", "case", "table", "lead", or "reference"
        "value": "item-id-123"    # The ID or reference value for the item
    }

    Result Example:
    {
        "success": true     # Did the operation succeed?
    }
    """
    try:
        body = request.json
    except UnsupportedMediaType:
        return bad_request(err="Invalid JSON body")

    if "value" not in body:
        return bad_request(err="Case 'value' is required")

    if "type" not in body:
        return bad_request(err="Case 'type' missing")

    try:
        case_service.append_case_item(
            id, item_type=body["type"], item_value=body["value"], item_path=body.get("path", None)
        )
    except DataStoreException as e:
        logger.exception("Save Error")
        return internal_error(err=str(e))
    except InvalidDataException as e:
        return bad_request(err=str(e))

    return ok()


@generate_swagger_docs()
@case_api.route("/<id>/items/<value>", methods=["DELETE"])
@api_login(required_priv=["R", "W"])
def delete_item(id: str, value: str, **kwargs):
    """Delete an item from a case

    This endpoint removes an item from a case's items list. If the item is a hit or
    observable, the bidirectional relationship is cleaned up - the case reference will
    be removed from the backing object's related.cases list.

    Variables:
    id       => The id of the case to modify
    value    => The value of the item to delete (must match the item's value field)

    Arguments:
    None

    Data Block:
    None

    Result Example:
    {
        "success": true     # Did the deletion succeed?
    }
    """
    try:
        case_service.remove_case_item(id, item_value=value)
    except DataStoreException as e:
        logger.exception("Save Error")
        return internal_error(err=str(e))
    except InvalidDataException as e:
        return bad_request(err=str(e))

    return ok()
