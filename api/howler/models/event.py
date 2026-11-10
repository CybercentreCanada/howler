"""Event model — a lightweight ECS record correlated with hits."""

from __future__ import annotations

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
from howler.models.header import Header as _Header
from howler.models.log import Log as _Log
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
    outline: optional(compound(_Header), description="The user specified header of the event.")
    score: optional(
        float_field(), default=0, description="A score assigned by an enrichment to help prioritize triage."
    )
    escalation: enum(values=Escalation, default=Escalation.HIT, description="Level of escalation of this event.")
    expiry: optional(date(), description="User selected time for event expiry")
    comment: list_field(
        compound(Comment), default=[], description="A list of comments with timestamps and attribution."
    )
    log: list_field(
        compound(_Log), default=[], description="A list of changes to the event with timestamps and attribution."
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
