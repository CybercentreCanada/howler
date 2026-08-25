"""ECS agent field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, keyword, optional, register_model


@register_model(
    index=True,
    store=True,
    description="The agent fields contain the data about the software entity, "
    "if any, that collects, detects, or observes events on a host, or takes measurements on a host.",
    embedded=True,
)
class Agent(HowlerEmbeddedModel):
    """The agent fields contain data about the software entity that observes events.

    If any, that collects, detects, or observes events on a host, or takes measurements on a host.
    """

    id: optional(keyword(), description="Unique identifier of this agent (if one exists).")
    name: optional(keyword(), description="Custom name of the agent.")
    type: optional(keyword(), description="Type of the agent.")
    version: optional(keyword(), description="Version of the agent.")
