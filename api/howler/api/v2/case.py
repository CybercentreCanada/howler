from werkzeug.exceptions import UnsupportedMediaType

from howler.api import bad_request, forbidden, make_subapi_blueprint, no_content, not_found, ok, not_implemented, internal_error
from howler.common.loader import datastore
from howler.common.logging import get_logger
from howler.common.swagger import generate_swagger_docs
from howler.odm.models.hit import Hit
from howler.odm.models.user import User
from howler.odm.models.case import CaseItem, Case
from howler.odm.models.observable import Observable
from howler.security import api_login
from flask import request

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

@generate_swagger_docs()
@case_api.route("/<id>/items", methods=["POST"])
@api_login(required_priv=["R", "W"])
def append_item(id: str, user: User, **kwargs):
    """Append to a case

    Variables:
    id => The id of the case to modify

    Optional Arguments:
    None

    Data Block:
    {
        "type": "String type of item to append to case (observable, hit, table, case, lead, reference)"
        "value": "Value for this item (id or url reference, depending on type)"
    }

    Result Example:
    {
        "success": true     # Did the deletion succeed?
    }
    """
    try:
        body = request.json
    except UnsupportedMediaType :
        return bad_request(err="Invalid JSON body")

    if "value" not in body:
        return bad_request(err="Case 'value' is required")

    case: Case | None =  datastore().case.get_if_exists(key=id, as_obj=True)

    if case is None:
        return not_found(err="Case not found")

    if "type" not in body:
        return bad_request(err="Case 'type' missing")

    case_item_data = {}
    backing_obj: Hit | Observable | None = None
    index = str | None

    match(body.get("type", "").lower()):
        case "hit":
            backing_obj: Hit = datastore().hit.get(body["value"]) or None
            index = 'hit'

            if backing_obj is None:
                return not_found(err="Hit not found")

            case_item_data = {
                'path': f'alerts/{backing_obj.howler.analytic} ({backing_obj.howler.id})',
                'type': 'hit',
                'id': body["value"],
                'value': body["value"],
            }

        case "observable":
            backing_obj: Observable = datastore().observable.get(body["value"]) or None
            index = 'observable'

            if backing_obj is None:
                return not_found(err="Observable not found")

            case_item_data = {
                'path': f'observables/{backing_obj.howler.analytic} ({backing_obj.howler.id})',
                'type': 'hit',
                'id': body["value"],
                'value': body["value"],
            }

        case _:
            return not_implemented(err="Case Item type not implemented")

    if not case_item_data:
        return bad_request(err="Unable to construct item to add to Case")

    if any(body['value'] == item["value"] for item in case['items']):
        return bad_request(err="Case item already exists")

    case_item = CaseItem(case_item_data)
    case['items'].append(case_item)

    if not datastore().case.save(case.case_id, case):
        return internal_error(err="Failed to save case with new item")

    if any(case.case_id == related_id for related_id in backing_obj.related.cases):
        return ok()

    backing_obj.related.cases.append(case.case_id)
    datastore()[backing_obj.__class__.__name__.lower()].save(backing_obj.id, backing_obj)

    return ok()


@generate_swagger_docs()
@case_api.route("/<id>/items/<value>", methods=["DELETE"])
@api_login(required_priv=["R", "W"])
def delete_item(id: str, value: str, **kwargs):
    """Delete an item from a case

    Variables:
    id => The id of the case to modify
    value => The value of the item to delete

    Optional Arguments:
    None

    Data Block:
    None

    Result Example:
    {
        "success": true     # Did the deletion succeed?
    }
    """
    if not id:
        return bad_request(err="Case 'id' is required")

    if not value:
        return bad_request(err="Case item 'value' is required")

    case: Case | None = datastore().case.get_if_exists(key=id, as_obj=True)

    if case is None:
        return not_found(err="Case not found")

    case_item = item if (item := next((item for item in case.items if item["value"] == value), None)) else None

    if case_item is None:
        return not_found(err="Case item not found")

    case.items.remove(case_item)
    datastore().case.save(case.case_id, case)

    return ok()