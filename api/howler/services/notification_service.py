import uuid
from typing import Any

from howler.common.exceptions import InvalidDataException, NotFoundException
from howler.common.loader import datastore
from howler.common.logging import get_logger
from howler.datastore.exceptions import SearchException
from howler.odm.models.notification import Notification
from howler.services import comms_service
from howler.utils.str_utils import sanitize_lucene_query

logger = get_logger(__file__)


def create_analytic_comment_notification(analytic_id: str, actor: str) -> Notification | None:
    """Create, persist, and emit a notification for a new analytic comment."""
    try:
        result = datastore().analytic.search(
            f'analytic_id:"{sanitize_lucene_query(analytic_id)}"',
            as_obj=False,
            rows=2,
        )
    except SearchException as error:
        logger.exception("Unable to find analytic %s for notification", analytic_id)
        raise InvalidDataException(str(error)) from error

    analytics = result["items"]
    if not analytics:
        raise NotFoundException(f"Analytic {analytic_id} does not exist.")

    analytic = analytics[0]
    owner = analytic.get("owner")
    if not owner:
        raise InvalidDataException(f"Analytic {analytic_id} does not have an owner.")
    if owner == actor:
        return None

    notification = Notification(
        {
            "notification_id": str(uuid.uuid4()),
            "recipient": owner,
            "sender": actor,
            "resource_type": "analytic",
            "resource_id": analytic["analytic_id"],
            "resource_name": analytic["name"],
            "message": f"{actor} commented on your analytic {analytic['name']}.",
            "url": f"/analytics/{analytic['analytic_id']}",
        }
    )

    datastore().notification.save(notification.notification_id, notification)
    comms_service.emit("notification", notification.as_primitives())
    return notification


def get_user_notifications(username: str, offset: int = 0, rows: int = 25) -> dict[str, Any]:
    """Return a page of the user's notifications, newest first."""
    query = f'recipient:"{sanitize_lucene_query(username)}"'
    try:
        result = datastore().notification.search(
            query,
            as_obj=False,
            offset=offset,
            rows=rows,
            sort="created desc",
            track_total_hits=True,
        )
        unread = datastore().notification.count(query, filters="read:false")["count"]
    except SearchException as error:
        logger.exception("Unable to retrieve notifications for %s", username)
        raise InvalidDataException(str(error)) from error

    return {
        "items": result["items"],
        "offset": result["offset"],
        "rows": result["rows"],
        "total": result["total"],
        "unread": unread,
    }


def _get_user_notification(notification_id: str, username: str) -> dict[str, Any]:
    """Return a notification owned by the user, hiding notifications that belong to other users."""
    notification = datastore().notification.get_if_exists(notification_id, as_obj=False)
    if not notification or notification.get("recipient") != username:
        raise NotFoundException(f"Notification {notification_id} does not exist.")

    return notification


def mark_notification_read(notification_id: str, username: str) -> dict[str, Any]:
    """Mark one of the user's notifications as read and return the updated notification."""
    notification = _get_user_notification(notification_id, username)
    if notification.get("read"):
        return notification

    collection = datastore().notification
    if not collection.update(notification_id, [(collection.UPDATE_SET, "read", True)]):
        raise InvalidDataException(f"Unable to mark notification {notification_id} as read.")

    return {**notification, "read": True}


def delete_notification(notification_id: str, username: str) -> None:
    """Delete one of the user's notifications."""
    _get_user_notification(notification_id, username)

    if not datastore().notification.delete(notification_id):
        raise NotFoundException(f"Notification {notification_id} does not exist.")
