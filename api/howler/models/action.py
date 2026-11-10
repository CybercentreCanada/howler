"""Action model."""

from __future__ import annotations

from howler.models import (
    HowlerEmbeddedModel,
    HowlerESModel,
    case_insensitive_keyword,
    compound,
    enum,
    keyword,
    list_field,
    optional,
    register_model,
    uuid,
)
from howler.models.ownership import Ownership

VALID_TRIGGERS = ["create", "demote", "promote", "add_label", "remove_label"]


@register_model(index=True, store=True, description="Model of action operations", embedded=True)
class Operation(HowlerEmbeddedModel):
    """Model of action operations."""

    operation_id: keyword(description="The ID of the action.")
    data_json: optional(keyword(), description="The data necessary to execute the action, in raw JSON format.")


@register_model(index=True, store=True, description="Model of actions")
class Action(Ownership, HowlerESModel):
    """Model of actions."""

    action_id: uuid(description="A UUID for this action")
    name: case_insensitive_keyword(description="The name of the action.")
    query: case_insensitive_keyword(description="The query this action is run against.")
    triggers: list_field(
        enum(values=VALID_TRIGGERS), default=[], description="A list of events for which trigger this action"
    )
    operations: list_field(
        compound(Operation), default=[], description="A list of the operations this action consists of."
    )
