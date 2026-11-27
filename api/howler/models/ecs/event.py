"""ECS event field set."""

from __future__ import annotations

from pydantic import Field

from howler.models import Date, Float, HowlerEmbeddedModel, Integer, Keyword, enum, register_model
from howler.utils.isotime import now_as_datetime

EVENT_CATEGORIES = [
    "authentication",
    "configuration",
    "database",
    "driver",
    "email",
    "file",
    "host",
    "iam",
    "intrusion_detection",
    "malware",
    "network",
    "package",
    "process",
    "registry",
    "session",
    "threat",
    "web",
]
EVENT_KIND = [
    "alert",
    "enrichment",
    "event",
    "metric",
    "state",
    "pipeline_error",
    "signal",
]
EVENT_TYPE = [
    "access",
    "admin",
    "allowed",
    "change",
    "connection",
    "creation",
    "deletion",
    "denied",
    "end",
    "error",
    "group",
    "indicator",
    "info",
    "installation",
    "protocol",
    "start",
    "user",
]
EVENT_OUTCOME = ["failure", "success", "unknown"]


@register_model(
    index=True,
    store=True,
    description="The event fields are used for context information about the log or metric event itself.",
    embedded=True,
)
class ECSEvent(HowlerEmbeddedModel):
    """The event fields are used for context information about the log or metric event itself."""

    action: Keyword | None = None
    """The action captured by the event."""
    category: list[enum(values=EVENT_CATEGORIES)] | None = None
    (
        'Represents the "big buckets" of ECS categories. For example, filtering on event.category:process yields all '
        "events relating to process activity. This field is closely related to event.type, which is used as a "
        "subcategory."
    )
    code: Keyword | None = None
    """Identification code for this event, if one exists."""
    count: Integer | None = None
    """Count of events"""
    created: Date | None = None
    """Contains the date/time when the event was first read by an agent, or by your pipeline."""
    dataset: Keyword | None = None
    """Name of the dataset."""
    duration: Integer | None = None
    """Duration of the event in nanoseconds."""
    end: Date | None = None
    """Contains the date when the event ended or when the activity was last observed."""
    hash: Keyword | None = None
    """Hash (perhaps logstash fingerprint) of raw field to be able to demonstrate log integrity."""
    id: Keyword | None = None
    """Unique ID to describe the event."""
    ingested: Date = Field(default_factory=now_as_datetime)
    """Timestamp when an event arrived in the central data store."""
    kind: enum(values=EVENT_KIND, optional=True)
    (
        "Gives high-level information about what type of information the event contains, without being specific to the "
        "contents of the event. "
    )
    module: Keyword | None = None
    """Name of the module this data is coming from."""
    original: Keyword | None = None
    (
        "Raw text message of entire event. Used to demonstrate log integrity or where the full log message (before "
        "splitting it up in multiple parts) may be required, e.g. for reindex."
    )
    outcome: enum(values=EVENT_OUTCOME, optional=True)
    (
        "Simply denotes whether the event represents a success or a failure from the perspective of the entity that "
        "produced the event."
    )
    provider: Keyword | None = None
    """Source of the event."""
    reason: Keyword | None = None
    """Reason why this event happened, according to the source."""
    reference: Keyword | None = None
    """Reference URL linking to additional information about this event."""
    risk_score: Float | None = None
    """Risk score or priority of the event (e.g. security solutions)."""
    risk_score_norm: Float | None = None
    """Normalized risk score or priority of the event, on a scale of 0 to 100."""
    sequence: Integer | None = None
    """Sequence number of the event."""
    severity: Integer | None = None
    """The numeric severity of the event according to your event source."""
    start: Date | None = None
    """Contains the date when the event started or when the activity was first observed."""
    timezone: Keyword | None = None
    (
        "This field should be populated when the event's timestamp does not include timezone information already (e.g. "
        "default Syslog timestamps)."
    )
    type: list[enum(values=EVENT_TYPE)] | None = None
    (
        'Represents a categorization "sub-bucket" that, when used along with the event.category field values, enables '
        "filtering events down to a level appropriate for single visualization."
    )
    url: Keyword | None = None
    """URL linking to an external system to continue investigation of this event."""
