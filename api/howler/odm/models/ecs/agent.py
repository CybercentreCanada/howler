# mypy: ignore-errors
from typing import Optional

from howler import odm


@odm.model(
    index=True,
    store=True,
    description="The agent fields contain the data about the software entity, "
    "if any, that collects, detects, or observes events on a host, or takes measurements on a host.",
)
class Agent(odm.Model):
    id: Optional[str] = odm.Optional(odm.Keyword(description="Unique identifier of this agent (if one exists)."))
    name: Optional[str] = odm.Optional(odm.Keyword(description="Custom name of the agent."))
    type: Optional[str] = odm.Optional(odm.Keyword(description="Type of the agent."))
    version: Optional[str] = odm.Optional(odm.Keyword(description="Version of the agent."))
