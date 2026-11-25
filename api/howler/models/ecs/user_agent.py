"""ECS user_agent field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, compound, keyword, optional, register_model
from howler.models.ecs.os import OS


@register_model(index=True, store=True, description="Information about the device.", embedded=True)
class Device(HowlerEmbeddedModel):
    """Information about the device."""

    name: optional(keyword(), description="Name of the device.")


@register_model(
    index=True,
    store=True,
    description="The user_agent fields normally come from a browser request.",
    embedded=True,
)
class UserAgent(HowlerEmbeddedModel):
    """The user_agent fields normally come from a browser request."""

    device: optional(compound(Device), description="Information about the device.")
    name: optional(keyword(), description="Name of the user agent.")
    original: optional(keyword(), description="Unparsed user_agent string.")
    os: optional(compound(OS), description="OS fields contain information about the operating system.")
    version: optional(keyword(), description="Version of the user agent.")
