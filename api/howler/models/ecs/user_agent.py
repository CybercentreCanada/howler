"""ECS user_agent field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, compound, keyword, register_model
from howler.models.ecs.os import OS


@register_model(index=True, store=True, description="Information about the device.", embedded=True)
class Device(HowlerEmbeddedModel):
    """Information about the device."""

    name: keyword(optional=True, description="Name of the device.")


@register_model(
    index=True,
    store=True,
    description="The user_agent fields normally come from a browser request.",
    embedded=True,
)
class UserAgent(HowlerEmbeddedModel):
    """The user_agent fields normally come from a browser request."""

    device: compound(Device, optional=True, description="Information about the device.")
    name: keyword(optional=True, description="Name of the user agent.")
    original: keyword(optional=True, description="Unparsed user_agent string.")
    os: compound(OS, optional=True, description="OS fields contain information about the operating system.")
    version: keyword(optional=True, description="Version of the user agent.")
