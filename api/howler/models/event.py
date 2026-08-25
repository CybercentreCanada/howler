"""Event model — a lightweight ECS record correlated with hits."""

from __future__ import annotations

from typing import Any

from pydantic import model_validator

from howler.models import (
    HowlerEmbeddedModel,
    compound,
    date,
    enum,
    float_field,
    howler_hash,
    keyword,
    list_field,
    mapping,
    optional,
    register_model,
    text,
    uuid,
)
from howler.models.constants import HowlerStrEnum
from howler.models.record import Record


class Escalation(HowlerStrEnum):
    """Level of escalation of an event."""

    HIT = "hit"
    ALERT = "alert"
    EVIDENCE = "evidence"


@register_model(index=True, store=True, description="Comment definition.", embedded=True)
class Comment(HowlerEmbeddedModel):
    """Comment definition."""

    id: uuid(description="A unique ID for the comment.")
    timestamp: date(default="NOW", description="Timestamp at which the comment took place.")
    modified: date(default="NOW", description="Timestamp at which the comment was last edited.")
    value: text(description="The comment itself.")
    user: keyword(description="User ID who created the comment.")
    reactions: mapping(keyword(), default={}, description="A list of reactions to the comment.")


@register_model(index=True, store=True, description="Log definition.", embedded=True)
class Log(HowlerEmbeddedModel):
    """Log definition."""

    timestamp: date(description="Timestamp at which the Log event took place.")
    key: optional(keyword(), description="The key whose value changed.")
    explanation: optional(text(), description="A manual description of the changes made.")
    new_value: optional(keyword(), description="The value the key is changing to.")
    previous_value: optional(keyword(), description="The value the key is changing from.")
    user: keyword(description="User ID who created the log event.")

    @model_validator(mode="before")
    @classmethod
    def _require_explanation_or_details(cls, data: Any) -> Any:
        """Mirror the legacy ``Log.__init__`` requirement."""
        if isinstance(data, dict) and "explanation" not in data:
            required_keys = {"key", "new_value", "previous_value"}
            if required_keys.intersection(set(data.keys())) != required_keys:
                raise ValueError(
                    f"If no explanation provided, you must provide the following values: {','.join(required_keys)}"
                )
        return data


DEFAULT_LABELS = {"assignments": [], "generic": []}


@register_model(
    index=True,
    store=True,
    description="Event metadata fields, howler specific.",
    embedded=True,
)
class EventData(HowlerEmbeddedModel):
    """Event metadata fields, howler specific."""

    id: uuid(description="A UUID for this event.")
    data: list_field(
        keyword(), default=[], store=False, description="Raw telemetry records associated with this event."
    )
    hash: howler_hash(
        description=(
            "A hash of the event used for deduplicating hits. Supports any hexadecimal string between 1 "
            "and 64 characters long."
        )
    )
    related: list_field(keyword(), default=[], description="Related records.")
    score: optional(
        float_field(), default=0, description="A score assigned by an enrichment to help prioritize triage."
    )
    escalation: enum(values=Escalation, default=Escalation.HIT, description="Level of escalation of this event.")
    expiry: optional(date(), description="User selected time for event expiry")
    comment: list_field(
        compound(Comment), default=[], description="A list of comments with timestamps and attribution."
    )
    log: list_field(
        compound(Log), default=[], description="A list of changes to the event with timestamps and attribution."
    )


@register_model(
    index=True,
    store=True,
    description="Event schema which is an extended version of Elastic Common Schema (ECS)",
    id_field="howler.id",
)
class Event(Record):
    """Event schema which is an extended version of Elastic Common Schema (ECS)."""

    # Howler extended fields. Deviates from ECS
    howler: compound(EventData, description="Howler specific definition of the event")
