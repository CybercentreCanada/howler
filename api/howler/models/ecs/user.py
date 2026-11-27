"""ECS user field set."""

from __future__ import annotations

from typing import Annotated

from howler.models import Email, HowlerEmbeddedModel, Keyword, metadata, register_model
from howler.models.ecs.group import Group


@register_model(
    index=True,
    store=True,
    description="The user fields describe information about the user that is relevant to the event.",
    embedded=True,
)
class UserNested(HowlerEmbeddedModel):
    """The user fields describe information about the user that is relevant to the event."""

    domain: Keyword | None = None
    """Name of the directory the user is a member of."""
    email: Email | None = None
    """User email address."""
    full_name: Keyword | None = None
    """User's full name, if available."""
    hash: Keyword | None = None
    """Unique user hash to correlate information for a user in anonymized form."""
    id: Keyword | None = None
    """Unique identifier of the user."""
    name: Keyword | None = None
    """Short name or login of the user."""
    roles: Annotated[list[Keyword], metadata(optional=True)] = []
    """Array of user roles at the time of the event."""


@register_model(
    index=True,
    store=True,
    description="The user fields describe information about the user that is relevant to the event.",
    embedded=True,
)
class User(HowlerEmbeddedModel):
    """The user fields describe information about the user that is relevant to the event."""

    domain: Keyword | None = None
    """Name of the directory the user is a member of."""
    email: Email | None = None
    """User email address."""
    full_name: Keyword | None = None
    """User's full name, if available."""
    group: Group | None = None
    """User's group relevant to the event."""
    hash: Keyword | None = None
    """Unique user hash to correlate information for a user in anonymized form."""
    id: Keyword | None = None
    """Unique identifier of the user."""
    name: Keyword | None = None
    """Short name or login of the user."""
    roles: Annotated[list[Keyword], metadata(optional=True)] = []
    """Array of user roles at the time of the event."""


@register_model(index=True, store=True, description="Shorter representation of a user.", embedded=True)
class ShortUser(HowlerEmbeddedModel):
    """Shorter representation of a user."""

    id: Keyword | None = None
    """Unique identifier of the user."""
    name: Keyword | None = None
    """Short name or login of the user."""
    domain: Keyword | None = None
    """Name of the directory the user is a member of."""
    email: Email | None = None
    """User email address."""
