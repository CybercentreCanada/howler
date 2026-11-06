import uuid

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
    # Can two analytics have the same ID?
    if len(analytics) > 1:
        logger.warning("Multiple analytics found for analytic_id %s", analytic_id)

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
            "resource_commenter": actor,
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
