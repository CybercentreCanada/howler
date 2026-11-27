"""ECS agent field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, Keyword, register_model


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

    id: Keyword | None = None
    """Unique identifier of this agent (if one exists)."""
    name: Keyword | None = None
    """Custom name of the agent."""
    type: Keyword | None = None
    """Type of the agent."""
    version: Keyword | None = None
    """Version of the agent."""
