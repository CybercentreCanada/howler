from typing import Any

from flask import request

from howler.api import bad_request, make_subapi_blueprint, not_found, ok
from howler.common.loader import datastore
from howler.common.logging import get_logger
from howler.common.swagger import generate_swagger_docs
from howler.datastore.exceptions import SearchException
from howler.security.login import api_login
from howler.services import comms_service
from howler.utils.str_utils import sanitize_lucene_query

SUB_API = "notification"
notification_api = make_subapi_blueprint(SUB_API, api_version=2)
notification_api._doc = "Send user notifications"  # type: ignore[attr-defined]

logger = get_logger(__file__)


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
        result = datastore().analytic.search(
            f'analytic_id:"{sanitize_lucene_query(analytic_id)}"',
            as_obj=False,
            rows=2,
        )
    except SearchException as error:
        logger.exception("Unable to find analytic %s for notification", analytic_id)
        return bad_request(err=str(error))

    analytics = result["items"]
    if not analytics:
        return not_found(err=f"Analytic {analytic_id} does not exist.")
    if len(analytics) > 1:
        logger.warning("Multiple analytics found for analytic_id %s", analytic_id)

    analytic = analytics[0]
    owner = analytic.get("owner")
    if not owner:
        return bad_request(err=f"Analytic {analytic_id} does not have an owner.")

    notification = {
        "type": "analytic_comment",
        "recipient": owner,
        "actor": commenter,
        "analytic_id": analytic["analytic_id"],
        "analytic_name": analytic["name"],
        "message": f"{commenter} commented on your analytic {analytic['name']}.",
    }

    comms_service.emit("notification", notification)
    return ok(notification)
