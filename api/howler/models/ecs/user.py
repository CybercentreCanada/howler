"""ECS user field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, compound, email, keyword, list_field, optional, register_model
from howler.models.ecs.group import Group


@register_model(
    index=True,
    store=True,
    description="The user fields describe information about the user that is relevant to the event.",
    embedded=True,
)
class UserNested(HowlerEmbeddedModel):
    """The user fields describe information about the user that is relevant to the event."""

    domain: optional(keyword(), description="Name of the directory the user is a member of.")
    email: optional(email(), description="User email address.")
    full_name: optional(keyword(), description="User's full name, if available.")
    hash: optional(keyword(), description="Unique user hash to correlate information for a user in anonymized form.")
    id: optional(keyword(), description="Unique identifier of the user.")
    name: optional(keyword(), description="Short name or login of the user.")
    roles: optional(list_field(keyword()), default=[], description="Array of user roles at the time of the event.")


@register_model(
    index=True,
    store=True,
    description="The user fields describe information about the user that is relevant to the event.",
    embedded=True,
)
class User(HowlerEmbeddedModel):
    """The user fields describe information about the user that is relevant to the event."""

    domain: optional(keyword(), description="Name of the directory the user is a member of.")
    email: optional(email(), description="User email address.")
    full_name: optional(keyword(), description="User's full name, if available.")
    group: optional(compound(Group), description="User's group relevant to the event.")
    hash: optional(keyword(), description="Unique user hash to correlate information for a user in anonymized form.")
    id: optional(keyword(), description="Unique identifier of the user.")
    name: optional(keyword(), description="Short name or login of the user.")
    roles: optional(list_field(keyword()), default=[], description="Array of user roles at the time of the event.")


@register_model(index=True, store=True, description="Shorter representation of a user.", embedded=True)
class ShortUser(HowlerEmbeddedModel):
    """Shorter representation of a user."""

    id: optional(keyword(), description="Unique identifier of the user.")
    name: optional(keyword(), description="Short name or login of the user.")
    domain: optional(keyword(), description="Name of the directory the user is a member of.")
    email: optional(email(), description="User email address.")
