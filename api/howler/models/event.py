"""Event model — a lightweight ECS record correlated with hits."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from howler.models import (
    UUID,
    Date,
    Float,
    HowlerEmbeddedModel,
    HowlerHash,
    Keyword,
    enum,
    metadata,
    register_model,
)
from howler.models.constants import HowlerStrEnum
from howler.models.header import Header as _Header
from howler.models.howler_data import Comment
from howler.models.log import Log as _Log
from howler.models.mixins import DatastoreMixin
from howler.models.record import Record
from howler.utils.uid import get_random_id


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

    id: UUID = Field(default_factory=get_random_id)
    """A UUID for this event."""
    data: Annotated[list[Keyword], metadata(store=False)] = []
    """Raw telemetry records associated with this event."""
    hash: HowlerHash
    (
        "A hash of the event used for deduplicating hits. Supports any hexadecimal string between 1 and 64 characters "
        "long."
    )
    related: list[Keyword] = []
    """Related records."""
    outline: _Header | None = None
    """The user specified header of the event."""
    score: Annotated[Float | None, metadata(optional=True)] = 0
    """A score assigned by an enrichment to help prioritize triage."""
    escalation: enum(values=Escalation, default=Escalation.HIT)
    """Level of escalation of this event."""
    expiry: Date | None = None
    """User selected time for event expiry"""
    comment: list[Comment] = []
    """A list of comments with timestamps and attribution."""
    log: list[_Log] = []
    """A list of changes to the event with timestamps and attribution."""


@register_model(
    index=True,
    store=True,
    description="Event schema which is an extended version of Elastic Common Schema (ECS)",
    id_field="howler.id",
)
class Event(Record, DatastoreMixin["Event"]):
    """Event schema which is an extended version of Elastic Common Schema (ECS)."""

    # Howler extended fields. Deviates from ECS
    howler: EventData
    """Howler specific definition of the event"""
