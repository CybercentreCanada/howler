"""ECS user field set."""

from __future__ import annotations

from typing import Annotated

from howler.models import HowlerEmbeddedModel, email, keyword, metadata, register_model
from howler.models.ecs.group import Group


@register_model(
    index=True,
    store=True,
    description="The user fields describe information about the user that is relevant to the event.",
    embedded=True,
)
class UserNested(HowlerEmbeddedModel):
    """The user fields describe information about the user that is relevant to the event."""

    domain: keyword(optional=True)
    """Name of the directory the user is a member of."""
    email: email(optional=True)
    """User email address."""
    full_name: keyword(optional=True)
    """User's full name, if available."""
    hash: keyword(optional=True)
    """Unique user hash to correlate information for a user in anonymized form."""
    id: keyword(optional=True)
    """Unique identifier of the user."""
    name: keyword(optional=True)
    """Short name or login of the user."""
    roles: Annotated[list[keyword()] | None, metadata(optional=True)] = []
    """Array of user roles at the time of the event."""


@register_model(
    index=True,
    store=True,
    description="The user fields describe information about the user that is relevant to the event.",
    embedded=True,
)
class User(HowlerEmbeddedModel):
    """The user fields describe information about the user that is relevant to the event."""

    domain: keyword(optional=True)
    """Name of the directory the user is a member of."""
    email: email(optional=True)
    """User email address."""
    full_name: keyword(optional=True)
    """User's full name, if available."""
    group: Group | None = None
    """User's group relevant to the event."""
    hash: keyword(optional=True)
    """Unique user hash to correlate information for a user in anonymized form."""
    id: keyword(optional=True)
    """Unique identifier of the user."""
    name: keyword(optional=True)
    """Short name or login of the user."""
    roles: Annotated[list[keyword()] | None, metadata(optional=True)] = []
    """Array of user roles at the time of the event."""


@register_model(index=True, store=True, description="Shorter representation of a user.", embedded=True)
class ShortUser(HowlerEmbeddedModel):
    """Shorter representation of a user."""

    id: keyword(optional=True)
    """Unique identifier of the user."""
    name: keyword(optional=True)
    """Short name or login of the user."""
    domain: keyword(optional=True)
    """Name of the directory the user is a member of."""
    email: email(optional=True)
    """User email address."""
