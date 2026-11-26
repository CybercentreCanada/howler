"""ECS user_agent field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, keyword, register_model
from howler.models.ecs.os import OS


@register_model(index=True, store=True, description="Information about the device.", embedded=True)
class Device(HowlerEmbeddedModel):
    """Information about the device."""

    name: keyword(optional=True)
    """Name of the device."""


@register_model(
    index=True,
    store=True,
    description="The user_agent fields normally come from a browser request.",
    embedded=True,
)
class UserAgent(HowlerEmbeddedModel):
    """The user_agent fields normally come from a browser request."""

    device: Device | None = None
    """Information about the device."""
    name: keyword(optional=True)
    """Name of the user agent."""
    original: keyword(optional=True)
    """Unparsed user_agent string."""
    os: OS | None = None
    """OS fields contain information about the operating system."""
    version: keyword(optional=True)
    """Version of the user agent."""
