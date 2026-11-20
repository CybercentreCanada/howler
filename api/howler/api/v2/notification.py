from typing import Any

from flask import request

from howler.api import bad_request, make_subapi_blueprint, no_content, not_found, ok
from howler.api.v1.utils.params import int_parser, parse_parameters
from howler.common.exceptions import InvalidDataException, NotFoundException
from howler.common.swagger import generate_swagger_docs
from howler.odm.models.user import User
from howler.security.login import api_login
from howler.services import notification_service

SUB_API = "notification"
notification_api = make_subapi_blueprint(SUB_API, api_version=2)
notification_api._doc = "Send user notifications"  # type: ignore[attr-defined]


@generate_swagger_docs()
@notification_api.route("/notify", methods=["POST"])
@api_login(required_priv=["W"])
def notify_user(user: dict[str, Any], **kwargs):
    """Notifies user that a comment has been made on their resource.

    Variables:
    None

    Arguments:
    None

    Data Block:
    {
        "analytic_id": "d23e8c2d-0f09-4a60-a50d-aac7db97b10a",
        "commenter": "analyst"
    }

    Result Example:
    {
        "resource_type": "analytic",
        "recipient": "analytic-owner",
        "sender": "analyst",
        "resource_id": "d23e8c2d-0f09-4a60-a50d-aac7db97b10a",
        "resource_name": "Suspicious Login",
        "message": "analyst commented on your analytic Suspicious Login."
    }
    """
    req_data = request.get_json(silent=True)
    if not isinstance(req_data, dict):
        return bad_request(err="Request body is required.")

    analytic_id = req_data.get("analytic_id")
    commenter = req_data.get("commenter")
    if not isinstance(analytic_id, str) or not analytic_id.strip():
        return bad_request(err="'analytic_id' is required and must be a non-empty string.")
    if not isinstance(commenter, str) or not commenter.strip():
        return bad_request(err="'commenter' is required and must be a non-empty string.")

    analytic_id = analytic_id.strip()
    commenter = commenter.strip()
    if commenter != user["uname"]:
        return bad_request(err="'commenter' must match the authenticated user.")

    try:
        return ok(notification_service.create_analytic_comment_notification(analytic_id, commenter))
    except NotFoundException as error:
        return not_found(err=str(error))
    except InvalidDataException as error:
        return bad_request(err=str(error))


@generate_swagger_docs()
@notification_api.route("/get/user", methods=["GET"])
@api_login(required_priv=["R"])
@parse_parameters(
    offset=int_parser("offset", 0, minimum=0),
    rows=int_parser("rows", 25, minimum=1, maximum=100),
)
def get_user_notifications(user: User, offset: int = 0, rows: int = 25, **kwargs):
    """Return the authenticated user's latest notifications, newest first, with their total unread count.

    Variables:
    None

    Optional Arguments:
    offset  => Zero-based offset of the first notification to return. Defaults to 0.
    rows    => Number of notifications to return, from 1 to 100. Defaults to 25.

    Result Example:
    {
        "items": [
            {
                "notification_id": "0b6f8c1e-6f1c-4c55-9d3e-3c7d6a1f2b9a",
                "recipient": "analytic-owner",
                "sender": "analyst",
                "resource_type": "analytic",
                "resource_id": "d23e8c2d-0f09-4a60-a50d-aac7db97b10a",
                "resource_name": "Suspicious Login",
                "message": "analyst commented on your analytic Suspicious Login.",
                "url": "/analytics/d23e8c2d-0f09-4a60-a50d-aac7db97b10a",
                "created": "2026-11-06T14:00:00.000000Z",
                "read": false
            }
        ],
        "offset": 0,
        "rows": 1,
        "total": 1,
        "unread": 1
    }
    """
    try:
        return ok(notification_service.get_user_notifications(user.uname, offset=offset, rows=rows))
    except InvalidDataException as error:
        return bad_request(err=str(error))


@generate_swagger_docs()
@notification_api.route("/<notification_id>/read", methods=["POST"])
@api_login(required_priv=["W"])
def mark_notification_read(notification_id: str, user: User, **kwargs):
    """Mark one of the authenticated user's notifications as read.

    Variables:
    notification_id => The ID of the notification to mark as read.

    Optional Arguments:
    None

    Data Block:
    None

    Result Example:
    {
        "notification_id": "0b6f8c1e-6f1c-4c55-9d3e-3c7d6a1f2b9a",
        "recipient": "analytic-owner",
        "sender": "analyst",
        "resource_type": "analytic",
        "resource_id": "d23e8c2d-0f09-4a60-a50d-aac7db97b10a",
        "resource_name": "Suspicious Login",
        "message": "analyst commented on your analytic Suspicious Login.",
        "url": "/analytics/d23e8c2d-0f09-4a60-a50d-aac7db97b10a",
        "created": "2026-11-06T14:00:00.000000Z",
        "read": true
    }
    """
    try:
        return ok(notification_service.mark_notification_read(notification_id, user.uname))
    except NotFoundException as error:
        return not_found(err=str(error))
    except InvalidDataException as error:
        return bad_request(err=str(error))


@generate_swagger_docs()
@notification_api.route("/<notification_id>", methods=["DELETE"])
@api_login(required_priv=["W"])
def delete_notification(notification_id: str, user: User, **kwargs):
    """Delete one of the authenticated user's notifications.

    Variables:
    notification_id => The ID of the notification to delete.

    Optional Arguments:
    None

    Data Block:
    None

    Result Example:
    {
        "success": true
    }
    """
    try:
        notification_service.delete_notification(notification_id, user.uname)
        return no_content()
    except NotFoundException as error:
        return not_found(err=str(error))
