"""Event model — a lightweight ECS record correlated with hits."""

from __future__ import annotations

from howler.models import (
    HowlerEmbeddedModel,
    date,
    enum,
    float_field,
    howler_hash,
    keyword,
    list_field,
    register_model,
    uuid,
)
from howler.models.constants import HowlerStrEnum
from howler.models.header import Header as _Header
from howler.models.howler_data import Comment
from howler.models.log import Log as _Log
from howler.models.record import Record


class Escalation(HowlerStrEnum):
    """Level of escalation of an event."""

    HIT = "hit"
    ALERT = "alert"
    EVIDENCE = "evidence"


@register_model(
    index=True,
    store=True,
    description="Event metadata fields, howler specific.",
    embedded=True,
)
class EventData(HowlerEmbeddedModel):
    """Event metadata fields, howler specific."""

    id: uuid()
    """A UUID for this event."""
    data: list_field(keyword(), default=[], store=False)
    """Raw telemetry records associated with this event."""
    hash: howler_hash()
    (
        "A hash of the event used for deduplicating hits. Supports any hexadecimal string between 1 and 64 characters "
        "long."
    )
    related: list_field(keyword(), default=[])
    """Related records."""
    outline: _Header | None = None
    """The user specified header of the event."""
    score: float_field(optional=True, default=0)
    """A score assigned by an enrichment to help prioritize triage."""
    escalation: enum(values=Escalation, default=Escalation.HIT)
    """Level of escalation of this event."""
    expiry: date(optional=True)
    """User selected time for event expiry"""
    comment: list_field(Comment, default=[])
    """A list of comments with timestamps and attribution."""
    log: list_field(_Log, default=[])
    """A list of changes to the event with timestamps and attribution."""


@register_model(
    index=True,
    store=True,
    description="Event schema which is an extended version of Elastic Common Schema (ECS)",
    id_field="howler.id",
)
class Event(Record):
    """Event schema which is an extended version of Elastic Common Schema (ECS)."""

    # Howler extended fields. Deviates from ECS
    howler: EventData
    """Howler specific definition of the event"""
