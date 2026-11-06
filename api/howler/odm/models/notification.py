from datetime import datetime
from typing import Optional

from howler import odm


@odm.model(index=True, store=True, description="A notification delivered to a Howler user for analytics.")
class Notification(odm.Model):
    notification_id: str = odm.UUID(description="A unique identifier for this notification.")
    resource_type: str = odm.Keyword(description="The type of the event")
    recipient: str = odm.Keyword(description="The username of the notification recipient.")
    resource_id: str = odm.Keyword(description="A unique identifier for the resource.")
    resource_commenter: str = odm.Keyword(description="The username that triggered the notification.")
    created: datetime = odm.Date(description="The time the notification was created.", default="NOW")
    resource_name: str = odm.Keyword(description="The display name of the referenced analytic.")
    message: str = odm.Text(description="The message displayed to the recipient.")
    url: Optional[str] = odm.Optional(odm.Keyword(description="A UI path for the referenced resource."))
