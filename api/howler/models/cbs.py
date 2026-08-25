"""CBS provider fields."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, compound, email, keyword, optional, register_model


@register_model(index=True, store=True, embedded=True)
class SharepointUser(HowlerEmbeddedModel):
    """A Sharepoint user reference."""

    email: optional(email(), description="The email of the sharepoint user associated with this item.")
    full_name: optional(keyword(), description="The full name of the sharepoint user associated with this item.")
    id: optional(keyword(), description="The id of the sharepoint user associated with this item.")


@register_model(index=True, store=True, embedded=True)
class SharepointData(HowlerEmbeddedModel):
    """Sharepoint application/user metadata."""

    application: optional(keyword(), description="The associated application.")
    user: optional(keyword(), description="The associated application.")


@register_model(index=True, store=True, embedded=True)
class Sharepoint(HowlerEmbeddedModel):
    """Sharepoint creation/modification metadata."""

    created: optional(compound(SharepointData), description="Information about how the item was created.")
    modified: optional(compound(SharepointData), description="Information about how the item was modified.")


@register_model(
    index=True,
    store=True,
    description="The cbs fields contain any data obtained from CBS relating to the alert.",
    embedded=True,
)
class CBS(HowlerEmbeddedModel):
    """The cbs fields contain any data obtained from CBS relating to the alert."""

    sharepoint: optional(compound(Sharepoint), description="Sharepoint metadata")
