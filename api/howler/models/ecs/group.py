"""ECS group field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, keyword, optional, register_model


@register_model(
    index=True,
    store=True,
    description="The group fields are meant to represent groups that are relevant to the event.",
    embedded=True,
)
class Group(HowlerEmbeddedModel):
    """The group fields are meant to represent groups that are relevant to the event."""

    domain: optional(keyword(), description="Name of the directory the group is a member of.")
    id: optional(keyword(), description="Unique identifier for the group on the system/platform.")
    name: optional(keyword(), description="Name of the group.")


@register_model(index=True, store=True, description="Shorter representation of a group.", embedded=True)
class ShortGroup(HowlerEmbeddedModel):
    """Shorter representation of a group."""

    id: optional(keyword(), description="Unique identifier for the group on the system/platform.")
    name: optional(keyword(), description="Name of the group.")
