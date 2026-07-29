from typing import Literal

from howler import odm


@odm.model(index=False, store=False, description="Request payload for ownership permission updates")
class PermissionRequest(odm.Model):
    privilege: Literal["admins", "members", "owner"] = odm.Enum(
        values=["admins", "members", "owner"],
        description="The permission level to update",
    )
    user_ids: list[str] = odm.List(
        odm.Keyword(),
        description="The group administrator for this object.",
        default=[],
        optional=False,
    )
