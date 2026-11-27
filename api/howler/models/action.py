"""Action model."""

from __future__ import annotations

from pydantic import Field

from howler.models import (
    UUID,
    CaseInsensitiveKeyword,
    HowlerEmbeddedModel,
    HowlerESModel,
    Keyword,
    enum,
    register_model,
)
from howler.models.ownership import Ownership
from howler.utils.uid import get_random_id

VALID_TRIGGERS = ["create", "demote", "promote", "add_label", "remove_label"]


@register_model(index=True, store=True, description="Model of action operations", embedded=True)
class Operation(HowlerEmbeddedModel):
    """Model of action operations."""

    operation_id: Keyword
    """The ID of the action."""
    data_json: Keyword | None = None
    """The data necessary to execute the action, in raw JSON format."""


@register_model(index=True, store=True, description="Model of actions")
class Action(Ownership, HowlerESModel):
    """Model of actions."""

    action_id: UUID = Field(default_factory=get_random_id)
    """A UUID for this action"""
    name: CaseInsensitiveKeyword
    """The name of the action."""
    query: CaseInsensitiveKeyword
    """The query this action is run against."""
    triggers: list[enum(values=VALID_TRIGGERS)] = []
    """A list of events for which trigger this action"""
    operations: list[Operation] = []
    """A list of the operations this action consists of."""
