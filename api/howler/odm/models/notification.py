from datetime import datetime
from typing import Optional

from howler import odm
from howler.odm.constants import RELATIVE_PATH_REGEX


@odm.model(index=True, store=True, description="A notification delivered to a Howler user for analytics.")
class Notification(odm.Model):
    notification_id: str = odm.UUID(description="A unique identifier for this notification.")
    resource_type: str = odm.Keyword(description="The type of the event")
    recipient: str = odm.Keyword(description="The username of the notification recipient.")
    resource_id: str = odm.Keyword(description="A unique identifier for the resource.")
    sender: str = odm.Keyword(description="The username that triggered the notification.")
    created: datetime = odm.Date(description="The time the notification was created.", default="NOW")
    resource_name: str = odm.Keyword(description="The display name of the referenced analytic.")
    read: bool = odm.Boolean(description="Whether the message has been read by recipient.", default=False)
    message: str = odm.Text(description="The message displayed to the recipient.")
    url_path: Optional[str] = odm.Optional(
        odm.ValidatedKeyword(
            RELATIVE_PATH_REGEX,
            description="A UI path for the referenced resource. Must be a relative path, not a full URL.",
        )
    )
