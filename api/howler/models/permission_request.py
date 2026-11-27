"""Request model for an ownership permission update."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, Keyword, enum, register_model


@register_model(
    index=False,
    store=False,
    description="A permission entry for ownership permission updates",
    embedded=True,
)
class PermissionRequest(HowlerEmbeddedModel):
    """A permission entry for ownership permission updates."""

    privilege: enum(values=["admins", "members", "owner"])
    """The permission level to update"""
    user_id: Keyword
    """The user ID to grant or revoke for the selected privilege."""
