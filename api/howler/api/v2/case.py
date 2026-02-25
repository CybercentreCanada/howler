from flask import request
from werkzeug.exceptions import UnsupportedMediaType

from howler.api import (
    bad_request,
    created,
    forbidden,
    internal_error,
    make_subapi_blueprint,
    no_content,
    not_found,
    not_implemented,
    ok,
)
from howler.common.exceptions import InvalidDataException, NotFoundException, ResourceExists
from howler.common.loader import datastore
from howler.common.swagger import generate_swagger_docs
from howler.odm.models.case import Case, CaseItem, CaseItemTypes
from howler.odm.models.hit import Hit
from howler.odm.models.observable import Observable
from howler.odm.models.user import User
from howler.security import api_login
from howler.services import case_service

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

    try:
        new_case = case_service.create_case(title, summary, user.uname)
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


@generate_swagger_docs()
@case_api.route("/<id>/items", methods=["POST"])
@api_login(required_priv=["R", "W"])
def append_item(id: str, user: User, **kwargs):
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
        "type": "hit",              # Type of item to append: "hit", "observable", "case", "table", "lead", or "reference"
        "value": "item-id-123"      # The ID or reference value for the item
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

    case: Case | None = datastore().case.get_if_exists(key=id, as_obj=True)

    if case is None:
        return not_found(err="Case not found")

    if "type" not in body:
        return bad_request(err="Case 'type' missing")

    case_item_data: dict[str, str] = {}
    backing_obj: Hit | Observable | None = None

    match body.get("type", "").lower():
        case CaseItemTypes.HIT:
            backing_obj: Hit = datastore().hit.get(body["value"]) or None

            if backing_obj is None:
                return not_found(err="Hit not found")

            case_item_data = {
                "path": f"alerts/{backing_obj.howler.analytic} ({backing_obj.howler.id})",
                "type": "hit",
                "id": body["value"],
                "value": body["value"],
            }

        case CaseItemTypes.OBSERVABLE:
            backing_obj: Observable = datastore().observable.get(body["value"]) or None

            if backing_obj is None:
                return not_found(err="Observable not found")

            case_item_data = {
                "path": f"observables/{backing_obj.howler.analytic} ({backing_obj.howler.id})",
                "type": "hit",
                "id": body["value"],
                "value": body["value"],
            }

        case CaseItemTypes.CASE:
            related_case: Case = datastore().case.get(body["value"]) or None

            if related_case is None:
                return not_found(err="Case not found")

            case_item_data = {
                "path": f"cases/{related_case.title} ({related_case.case_id})",
                "type": "case",
                "id": body["value"],
                "value": body["value"],
            }

        case _:
            return not_implemented(err="Case Item type not implemented")

    if not case_item_data:
        return bad_request(err="Unable to construct item to add to Case")

    if any(body["value"] == item["value"] for item in case["items"]):
        return bad_request(err="Case item already exists")

    case_item = CaseItem(case_item_data)
    case["items"].append(case_item)

    if not datastore().case.save(case.case_id, case):
        return internal_error(err="Failed to save case with new item")

    if backing_obj is not None:
        if any(case.case_id == related_id for related_id in backing_obj.howler.related):
            return ok()

        backing_obj.howler.related.append(case.case_id)
        datastore()[backing_obj.__class__.__name__.lower()].save(backing_obj.howler.id, backing_obj)

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
    case: Case | None = datastore().case.get_if_exists(key=id, as_obj=True)

    if case is None:
        return not_found(err="Case not found")

    case_item = next((item for item in case.items if item["value"] == value), None)

    if case_item is None:
        return not_found(err="Case item not found")

    backing_obj: Hit | Observable | None = None
    match case_item.type:
        case CaseItemTypes.HIT:
            backing_obj: Hit = datastore().hit.get(case_item.id) or None
        case CaseItemTypes.OBSERVABLE:
            backing_obj: Observable = datastore().observable.get(case_item.id) or None

    case.items.remove(case_item)

    if not datastore().case.save(case.case_id, case):
        return internal_error(err="Failed to save case after item removal")

    if backing_obj is not None and case.case_id in backing_obj.howler.related:
        backing_obj.howler.related.remove(case.case_id)
        datastore()[backing_obj.__class__.__name__.lower()].save(backing_obj.howler.id, backing_obj)

    return ok()
