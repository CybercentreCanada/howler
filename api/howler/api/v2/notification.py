from typing import Any

from flask import request

from howler.api import bad_request, make_subapi_blueprint, not_found, ok
from howler.common.exceptions import InvalidDataException, NotFoundException
from howler.common.swagger import generate_swagger_docs
from howler.security.login import api_login
from howler.services import notification_service

SUB_API = "notification"
notification_api = make_subapi_blueprint(SUB_API, api_version=2)
notification_api._doc = "Send user notifications"  # type: ignore[attr-defined]


@generate_swagger_docs()
@notification_api.route("/notify", methods=["POST"])
@api_login(required_priv=["W"])
def notify_user(user: dict[str, Any], **kwargs):
    """Notifies user that a comment has been made on their analytic.

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
        "type": "analytic_comment",
        "recipient": "analytic-owner",
        "actor": "analyst",
        "analytic_id": "d23e8c2d-0f09-4a60-a50d-aac7db97b10a",
        "analytic_name": "Suspicious Login",
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
