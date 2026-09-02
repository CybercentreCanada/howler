from typing import Literal

from flask import request
from werkzeug.exceptions import UnsupportedMediaType

from howler.api import bad_request, created, forbidden, internal_error, make_subapi_blueprint, no_content, not_found, ok
from howler.api.v1.utils.etag import add_etag
from howler.api.v1.utils.params import parse_parameters, parse_refresh
from howler.common.exceptions import (
    ForbiddenException,
    HowlerException,
    InvalidDataException,
    NotFoundException,
    ResourceExists,
)
from howler.common.logging import get_logger
from howler.common.swagger import generate_swagger_docs
from howler.datastore.exceptions import DataStoreException
from howler.odm.models.case import Case, CaseItem
from howler.odm.models.user import User
from howler.security.login import api_login
from howler.services import case_service

SUB_API = "case"
case_api = make_subapi_blueprint(SUB_API, api_version=2)
case_api._doc = "Manage the different cases created"  # type: ignore

logger = get_logger(__file__)


@generate_swagger_docs()
@case_api.route("/", methods=["POST"])
@api_login(required_priv=["R", "W"])
@parse_parameters(refresh=parse_refresh)
def create_case(user: User, refresh: Literal["true", "false", "wait_for"] | None = None, **kwargs):
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
        return created(case_service.create_case(case_data, refresh=refresh, user=user))
    except NotFoundException as e:
        return not_found(err=str(e))
    except ForbiddenException as e:
        return forbidden(err=str(e))
    except InvalidDataException as e:
        return bad_request(err=str(e))
    except ResourceExists as e:
        return bad_request(err=str(e))
    except HowlerException as e:  # pragma: no cover
        return bad_request(err=str(e))


@generate_swagger_docs()
@case_api.route("/<id>", methods=["GET"])
@api_login(audit=True, required_priv=["R"])
@add_etag(getter=case_service.get_case)
def get_case(id: str, user: User, record: Case | None = None, server_version: str | None = None, **kwargs):
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
    if not record:
        return not_found(err="Case does not exist")

    case_service.filter_case_items_by_classification(record, user.classification)

    return ok(record)


@generate_swagger_docs()
@case_api.route("/", methods=["DELETE"])
@api_login(required_priv=["W"], required_type=["admin"])
@parse_parameters(refresh=parse_refresh)
def delete_cases(user: User, refresh: Literal["true", "false", "wait_for"] | None = None, **kwargs):
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

    case_service.delete_cases(case_ids, refresh=refresh, user=user)

    return no_content()


@generate_swagger_docs()
@case_api.route("/hide", methods=["POST"])
@api_login(required_priv=["W"])
@parse_parameters(refresh=parse_refresh)
def hide_cases(user: User, refresh: Literal["true", "false", "wait_for"] | None = None, **kwargs):
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

    case_service.hide_cases(case_ids, user=user, refresh=refresh)

    return no_content()


@generate_swagger_docs()
@case_api.route("/<id>", methods=["PUT"])
@api_login(required_priv=["R", "W"])
@parse_parameters(refresh=parse_refresh)
def update_case(id: str, user: User, refresh: Literal["true", "false", "wait_for"] | None = None, **kwargs):
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
        updated_case = case_service.update_case(id, case_data, user, refresh=refresh)

        case_service.filter_case_items_by_classification(updated_case, user.classification)

        return ok(updated_case)
    except NotFoundException as e:
        return not_found(err=str(e))
    except ForbiddenException as e:
        return forbidden(err=str(e))
    except InvalidDataException as e:
        return bad_request(err=str(e))


@generate_swagger_docs()
@case_api.route("/<case_id>/items", methods=["POST"])
@api_login(required_priv=["R", "W"])
@add_etag(getter=case_service.get_case, check_if_match=False)
@parse_parameters(refresh=parse_refresh)
def append_item(  # noqa: C901
    case_id: str,
    user: User,
    record: Case | None = None,
    server_version: str | None = None,
    refresh: Literal["true", "false", "wait_for"] | None = None,
    **kwargs,
):  # noqa: C901
    """Append an item to a case

    This endpoint adds a new item to a case's items list. The item can reference
    different types of objects (hits, events, or other cases). When a hit or
    event is added, a bidirectional relationship is created - the case will
    reference the item, and the item will reference the case in its related.cases list.

    Variables:
    id       => The id of the case to modify

    Arguments:
    None

    Data Block:
    {
        "type": "hit",                  # Type of item: hit, event, case, folder, markdown, reference, table, or lead
        "value": "item-id-123",         # The ID or reference value for the item
        "parent": "folder-uuid"         # Optional: parent folder item ID (null for root)
        "path": "example/path/Title"    # Optional: path to create the item at (will ensure path exists)
    }

    Result Example:
    {
        "success": true     # Did the operation succeed?
    }
    """
    if not record:
        return not_found(f"Case {case_id} does not exist")

    try:
        body = request.json
    except UnsupportedMediaType:
        return bad_request(err="Invalid JSON body")

    if not body or not isinstance(body, dict):
        return bad_request(err="Request body must be a JSON object.")

    for field in ["value", "type", "name"]:
        if field not in body:
            return bad_request(err=f"Field '{field}' is required")

    try:
        if path := body.pop("path", None):
            parent = case_service.get_parent_from_path(record, path, user=user)

            body["parent"] = parent.id if parent else None

        case_service.append_case_item(record, CaseItem(body), user=user)

        record.save(refresh=refresh, version=server_version)

        case_service.filter_case_items_by_classification(record, user.classification)

        return ok(record)
    except DataStoreException as e:
        logger.exception("Save Error")
        return internal_error(err=str(e))
    except ForbiddenException as e:
        return forbidden(err=str(e))
    except NotFoundException as e:  # pragma: no cover
        return not_found(err=str(e))
    except InvalidDataException as e:
        return bad_request(err=str(e))


@generate_swagger_docs()
@case_api.route("/<case_id>/items", methods=["DELETE"])
@api_login(required_priv=["R", "W"])
@add_etag(getter=case_service.get_case, check_if_match=False)
@parse_parameters(refresh=parse_refresh)
def delete_item(
    case_id: str,
    user: User,
    record: Case | None = None,
    server_version: str | None = None,
    refresh: Literal["true", "false", "wait_for"] | None = None,
    **kwargs,
):
    """Delete one or more items from a case

    This endpoint removes items from a case's items list. If an item is a hit or
    event, the bidirectional relationship is cleaned up - the case reference will
    be removed from the backing object's related.cases list.

    Variables:
    case_id       => The id of the case to modify

    Arguments:
    None

    Data Block:
    {
        "ids": ["uuid-1", "uuid-2"],   # The UUIDs of the items to delete
        "force": false                 # Optional: force-delete non-empty folders
    }

    Result Example:
    {
        ...case     # The updated case data
    }
    """
    if not record:
        return not_found(err=f"Case {case_id} not found")

    body = request.json

    if not body or not isinstance(body, dict):
        return bad_request(err="Request body must be a JSON object.")

    force = body.get("force", False)
    if not isinstance(force, bool):
        return bad_request(err="'force' must be a boolean.")

    ids = body.get("ids")
    if not ids or not isinstance(ids, list):
        return bad_request(err="'ids' must be a non-empty list.")
    elif not all(isinstance(item_id, str) for item_id in ids):
        return bad_request(err="All items in 'ids' must be strings.")

    try:
        updated_case = case_service.remove_case_items(
            record, ids, force=force, refresh=refresh, version=server_version, user=user
        )

        case_service.filter_case_items_by_classification(updated_case, user.classification)

        return ok(updated_case)
    except DataStoreException as e:
        logger.exception("Save Error")
        return internal_error(err=str(e))
    except ForbiddenException as e:
        return forbidden(err=str(e))
    except NotFoundException as e:
        return not_found(err=str(e))
    except InvalidDataException as e:
        return bad_request(err=str(e))


@generate_swagger_docs()
@case_api.route("/<case_id>/items", methods=["PUT"])
@api_login(required_priv=["R", "W"])
@add_etag(getter=case_service.get_case, check_if_match=False)
@parse_parameters(refresh=parse_refresh)
def rename_item(
    case_id: str,
    user: User,
    record: Case | None = None,
    server_version: str | None = None,
    refresh: Literal["true", "false", "wait_for"] | None = None,
    **kwargs,
):
    """Move an item within a case

    Updates the parent of a single item identified by its id.

    Variables:
    case_id       => The id of the case to modify

    Arguments:
    None

    Data Block:
    {
        "id": "uuid-of-item",       # The UUID of the item to update
        "parent": "uuid-or-null",   # Move: the UUID of the target folder, or null for root
        "name": "Display Name"      # Rename: the new display name for the item
    }

    Result Example:
    {
        ...case     # The updated case data
    }
    """
    if not record:
        return not_found(err=f"Case {case_id} does not exist")

    body = request.json

    if not body or not isinstance(body, dict):
        return bad_request(err="Request body must be a JSON object.")

    if "id" not in body:
        return bad_request(err="'id' is required.")

    item_id = body["id"]

    try:
        result: Case | None = None
        if "name" in body:
            result = case_service.rename_case_item(
                record,
                item_id,
                body["name"],
                user=user,
            )

        if "parent" in body:
            result = case_service.move_case_item(
                result or record,
                item_id,
                body["parent"],
                user=user,
            )

        if not result:
            return bad_request(err="At least one of 'name' or 'parent' is required.")

        result.save(refresh=refresh, version=server_version)

        case_service.filter_case_items_by_classification(result, user.classification)

        return ok(result)
    except DataStoreException as e:
        logger.exception("Save Error")
        return internal_error(err=str(e))
    except NotFoundException as e:
        return not_found(err=str(e))
    except InvalidDataException as e:
        return bad_request(err=str(e))


@generate_swagger_docs()
@case_api.route("/<id>/rules", methods=["POST"])
@api_login(required_priv=["R", "W"])
@parse_parameters(refresh=parse_refresh)
def add_rule(id: str, user: User, refresh: Literal["true", "false", "wait_for"] | None = None, **kwargs):
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
        "timeframe": 14,                        // optional, days until expiry (null = no expiry)
        "expire_after_resolved": true           // optional, start countdown after case resolution
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
        updated_case = case_service.add_case_rule(id, body, user, refresh=refresh)

        case_service.filter_case_items_by_classification(updated_case, user.classification)

        return ok(updated_case)
    except NotFoundException as e:
        return not_found(err=str(e))
    except InvalidDataException as e:
        return bad_request(err=str(e))


@generate_swagger_docs()
@case_api.route("/<id>/rules/<rule_id>", methods=["DELETE"])
@api_login(required_priv=["R", "W"])
@parse_parameters(refresh=parse_refresh)
def delete_rule(
    id: str, rule_id: str, user: User, refresh: Literal["true", "false", "wait_for"] | None = None, **kwargs
):
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
        updated_case = case_service.remove_case_rule(id, rule_id, user, refresh=refresh)

        case_service.filter_case_items_by_classification(updated_case, user.classification)

        return ok(updated_case)
    except NotFoundException as e:
        return not_found(err=str(e))


@generate_swagger_docs()
@case_api.route("/<id>/rules/<rule_id>", methods=["PUT"])
@api_login(required_priv=["R", "W"])
@parse_parameters(refresh=parse_refresh)
def update_rule(
    id: str, rule_id: str, user: User, refresh: Literal["true", "false", "wait_for"] | None = None, **kwargs
):
    """Update a correlation rule on a case

    Allows updating individual fields on a rule: enabled, query, destination,
    timeframe, expire_after_resolved.

    Variables:
    id        => The id of the case
    rule_id   => The id of the rule to update

    Arguments:
    None

    Data Block:
    {
        "enabled": false,
        "timeframe": 7,                 // days until expiry
        "expire_after_resolved": true   // start countdown after resolution
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
        updated_case = case_service.update_case_rule(id, rule_id, body, user, refresh=refresh)

        case_service.filter_case_items_by_classification(updated_case, user.classification)

        return ok(updated_case)
    except NotFoundException as e:
        return not_found(err=str(e))
    except InvalidDataException as e:
        return bad_request(err=str(e))
