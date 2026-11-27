"""CBS provider fields."""

from __future__ import annotations

from howler.models import Email, HowlerEmbeddedModel, Keyword, register_model


@register_model(index=True, store=True, embedded=True)
class SharepointUser(HowlerEmbeddedModel):
    """A Sharepoint user reference."""

    email: Email | None = None
    """The email of the sharepoint user associated with this item."""
    full_name: Keyword | None = None
    """The full name of the sharepoint user associated with this item."""
    id: Keyword | None = None
    """The id of the sharepoint user associated with this item."""


@register_model(index=True, store=True, embedded=True)
class SharepointData(HowlerEmbeddedModel):
    """Sharepoint application/user metadata."""

    application: Keyword | None = None
    """The associated application."""
    user: Keyword | None = None
    """The associated application."""


@register_model(index=True, store=True, embedded=True)
class Sharepoint(HowlerEmbeddedModel):
    """Sharepoint creation/modification metadata."""

    created: SharepointData | None = None
    """Information about how the item was created."""
    modified: SharepointData | None = None
    """Information about how the item was modified."""


@register_model(
    index=True,
    store=True,
    description="The cbs fields contain any data obtained from CBS relating to the alert.",
    embedded=True,
)
class CBS(HowlerEmbeddedModel):
    """The cbs fields contain any data obtained from CBS relating to the alert."""

    sharepoint: Sharepoint | None = None
    """Sharepoint metadata"""
