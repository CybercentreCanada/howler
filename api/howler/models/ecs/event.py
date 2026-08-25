"""ECS event field set."""

from __future__ import annotations

from howler.models import (
    HowlerEmbeddedModel,
    date,
    enum,
    float_field,
    integer,
    keyword,
    list_field,
    optional,
    register_model,
)

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

    action: optional(keyword(), description="The action captured by the event.")
    category: optional(
        list_field(enum(values=EVENT_CATEGORIES)),
        description='Represents the "big buckets" of ECS categories. For example, filtering on '
        "event.category:process yields all events relating to process activity. This field is closely "
        "related to event.type, which is used as a subcategory.",
    )
    code: optional(keyword(), description="Identification code for this event, if one exists.")
    count: optional(integer(), description="Count of events")
    created: optional(
        date(), description="Contains the date/time when the event was first read by an agent, or by your pipeline."
    )
    dataset: optional(keyword(), description="Name of the dataset.")
    duration: optional(integer(), description="Duration of the event in nanoseconds.")
    end: optional(date(), description="Contains the date when the event ended or when the activity was last observed.")
    hash: optional(
        keyword(),
        description="Hash (perhaps logstash fingerprint) of raw field to be able to demonstrate log integrity.",
    )
    id: optional(keyword(), description="Unique ID to describe the event.")
    ingested: date(default="NOW", description="Timestamp when an event arrived in the central data store.")
    kind: optional(
        enum(values=EVENT_KIND),
        description="Gives high-level information about what type of information the event "
        "contains, without being specific to the contents of the event. ",
    )
    module: optional(keyword(), description="Name of the module this data is coming from.")
    original: optional(
        keyword(),
        description="Raw text message of entire event. Used to demonstrate log integrity or where the "
        "full log message (before splitting it up in multiple parts) may be required, e.g. for reindex.",
    )
    outcome: optional(
        enum(values=EVENT_OUTCOME),
        description="Simply denotes whether the event represents a success or "
        "a failure from the perspective of the entity that produced the event.",
    )
    provider: optional(keyword(), description="Source of the event.")
    reason: optional(keyword(), description="Reason why this event happened, according to the source.")
    reference: optional(keyword(), description="Reference URL linking to additional information about this event.")
    risk_score: optional(float_field(), description="Risk score or priority of the event (e.g. security solutions).")
    risk_score_norm: optional(
        float_field(), description="Normalized risk score or priority of the event, on a scale of 0 to 100."
    )
    sequence: optional(integer(), description="Sequence number of the event.")
    severity: optional(integer(), description="The numeric severity of the event according to your event source.")
    start: optional(
        date(), description="Contains the date when the event started or when the activity was first observed."
    )
    timezone: optional(
        keyword(),
        description="This field should be populated when the event's timestamp does not include timezone "
        "information already (e.g. default Syslog timestamps).",
    )
    type: optional(
        list_field(enum(values=EVENT_TYPE)),
        description='Represents a categorization "sub-bucket" that, when used along with the event.category '
        "field values, enables filtering events down to a level appropriate for single visualization.",
    )
    url: optional(keyword(), description="URL linking to an external system to continue investigation of this event.")
