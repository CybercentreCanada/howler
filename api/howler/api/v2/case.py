from flask import request
from werkzeug.exceptions import UnsupportedMediaType

from howler.api import bad_request, created, internal_error, make_subapi_blueprint, no_content, not_found, ok
from howler.common.exceptions import HowlerException, InvalidDataException, NotFoundException, ResourceExists
from howler.common.loader import datastore
from howler.common.logging import get_logger
from howler.common.swagger import generate_swagger_docs
from howler.datastore.exceptions import DataStoreException
from howler.odm.models.case import CaseItem
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
        return created(case_service.create_case(case_data, user.uname))
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
        "value": "item-id-123"    # The ID or reference value for the item,
        "path": "example/path/Title"
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

    for field in ["value", "type", "path"]:
        if field not in body:
            return bad_request(err=f"CaseItem '{field}' is required")

    try:
        return ok(case_service.append_case_item(id, item=CaseItem(body)))
    except DataStoreException as e:
        logger.exception("Save Error")
        return internal_error(err=str(e))
    except InvalidDataException as e:
        return bad_request(err=str(e))


@generate_swagger_docs()
@case_api.route("/<case_id>/items", methods=["DELETE"])
@api_login(required_priv=["R", "W"])
def delete_item(case_id: str, **kwargs):
    """Delete one or more items from a case

    This endpoint removes items from a case's items list. If an item is a hit or
    observable, the bidirectional relationship is cleaned up - the case reference will
    be removed from the backing object's related.cases list.

    Variables:
    case_id       => The id of the case to modify

    Arguments:
    None

    Data Block:
    {
        "values": ["item-id-123", "item-id-456"]   # The values of the items to delete
    }

    Result Example:
    {
        ...case     # The updated case data
    }
    """
    body = request.json

    if not body or not isinstance(body, dict) or "values" not in body:
        return bad_request(err="Request body must be a JSON object with a 'values' field.")

    values = body["values"]
    if not isinstance(values, list) or not values:
        return bad_request(err="'values' must be a non-empty list.")

    try:
        return ok(case_service.remove_case_items(case_id, values))
    except DataStoreException as e:
        logger.exception("Save Error")
        return internal_error(err=str(e))
    except (InvalidDataException, NotFoundException) as e:
        return bad_request(err=str(e))


@generate_swagger_docs()
@case_api.route("/<case_id>/items", methods=["PUT"])
@api_login(required_priv=["R", "W"])
def rename_item(case_id: str, **kwargs):
    """Rename (re-path) an item within a case

    Updates the path of a single item identified by its value. The new path must
    not already be used by another item in the case.

    Variables:
    case_id       => The id of the case to modify

    Arguments:
    None

    Data Block:
    {
        "value": "item-id-123",          # The value of the item to rename
        "new_path": "folder/New Name"    # The new path for the item
    }

    Result Example:
    {
        ...case     # The updated case data
    }
    """
    body = request.json

    if not body or not isinstance(body, dict):
        return bad_request(err="Request body must be a JSON object.")

    for field in ["value", "new_path"]:
        if field not in body:
            return bad_request(err=f"'{field}' is required.")

    try:
        return ok(case_service.rename_case_item(case_id, item_value=body["value"], new_path=body["new_path"]))
    except DataStoreException as e:
        logger.exception("Save Error")
        return internal_error(err=str(e))
    except (InvalidDataException, NotFoundException) as e:
        return bad_request(err=str(e))


@generate_swagger_docs()
@case_api.route("/<id>/rules", methods=["POST"])
@api_login(required_priv=["R", "W"])
def add_rule(id: str, user: User, **kwargs):
    """Add a correlation rule to a case

    Creates a new correlation rule that will match incoming alerts into the case.
    The rule's id and author are generated server-side.

    Variables:
    id       => The id of the case to add a rule to

    Arguments:
    None

    Data Block:
    {
        "query": "howler.analytic:Suspicious*",
        "destination": "alerts/{{howler.analytic}}",
        "timeframe": "2026-05-06T00:00:00Z"   // optional, null means no expiry
    }

    Result Example:
    {
        ...case     # The updated case data
    }
    """
    body = request.json

    if not body or not isinstance(body, dict):
        return bad_request(err="Request body must be a JSON object with rule data.")

    try:
        return ok(case_service.add_case_rule(id, body, user))
    except NotFoundException as e:
        return not_found(err=str(e))
    except InvalidDataException as e:
        return bad_request(err=str(e))


@generate_swagger_docs()
@case_api.route("/<id>/rules/<rule_id>", methods=["DELETE"])
@api_login(required_priv=["R", "W"])
def delete_rule(id: str, rule_id: str, user: User, **kwargs):
    """Delete a correlation rule from a case

    Variables:
    id        => The id of the case
    rule_id   => The id of the rule to delete

    Arguments:
    None

    Result Example:
    {
        ...case     # The updated case data
    }
    """
    try:
        return ok(case_service.remove_case_rule(id, rule_id, user))
    except NotFoundException as e:
        return not_found(err=str(e))


@generate_swagger_docs()
@case_api.route("/<id>/rules/<rule_id>", methods=["PUT"])
@api_login(required_priv=["R", "W"])
def update_rule(id: str, rule_id: str, user: User, **kwargs):
    """Update a correlation rule on a case

    Allows updating individual fields on a rule: enabled, query, destination, timeframe.

    Variables:
    id        => The id of the case
    rule_id   => The id of the rule to update

    Arguments:
    None

    Data Block:
    {
        "enabled": false
    }

    Result Example:
    {
        ...case     # The updated case data
    }
    """
    body = request.json

    if not body or not isinstance(body, dict):
        return bad_request(err="Request body must be a JSON object with fields to update.")

    try:
        return ok(case_service.update_case_rule(id, rule_id, body, user))
    except NotFoundException as e:
        return not_found(err=str(e))
    except InvalidDataException as e:
        return bad_request(err=str(e))
