from howler import odm

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


@odm.model(
    index=True,
    store=True,
    description="The event fields are used for context information about the log or metric event itself.",
)
class Event(odm.Model):
    action = odm.Optional(odm.Keyword(description="The action captured by the event."))
    category = odm.Optional(
        odm.List(
            odm.Enum(values=EVENT_CATEGORIES),
            description='Represents the "big buckets" of ECS categories. For example, filtering on '
            "event.category:process yields all events relating to process activity. This field is closely "
            "related to event.type, which is used as a subcategory.",
        )
    )
    code = odm.Optional(odm.Keyword(description="Identification code for this event, if one exists."))
    count = odm.Integer(description="Count of events", optional=True)
    created = odm.Optional(
        odm.Date(description="Contains the date/time when the event was first read by an agent, or by your pipeline.")
    )
    dataset = odm.Optional(odm.Keyword(description="Name of the dataset."))
    duration = odm.Optional(odm.Integer(description="Duration of the event in nanoseconds."))
    end = odm.Optional(
        odm.Date(description="Contains the date when the event ended or when the activity was last observed.")
    )
    hash = odm.Optional(
        odm.Keyword(
            description="Hash (perhaps logstash fingerprint) of raw field to be able to demonstrate log integrity."
        )
    )
    id = odm.Optional(odm.Keyword(description="Unique ID to describe the event."))
    ingested = odm.Date(
        default="NOW",
        description="Timestamp when an event arrived in the central data store.",
    )
    kind = odm.Optional(
        odm.Enum(
            values=EVENT_KIND,
            description="Gives high-level information about what type of information the event "
            "contains, without being specific to the contents of the event. ",
        )
    )
    module = odm.Optional(odm.Keyword(description="Name of the module this data is coming from."))
    original = odm.Optional(
        odm.Keyword(
            description="Raw text message of entire event. Used to demonstrate log integrity or where the "
            "full log message (before splitting it up in multiple parts) may be required, e.g. for reindex."
        )
    )
    outcome = odm.Optional(
        odm.Enum(
            values=EVENT_OUTCOME,
            description="Simply denotes whether the event represents a success or "
            "a failure from the perspective of the entity that produced the event.",
        )
    )
    provider = odm.Optional(odm.Keyword(description="Source of the event."))
    reason = odm.Optional(odm.Keyword(description="Reason why this event happened, according to the source."))
    reference = odm.Optional(
        odm.Keyword(description="Reference URL linking to additional information about this event.")
    )
    risk_score = odm.Optional(odm.Float(description="Risk score or priority of the event (e.g. security solutions)."))
    risk_score_norm = odm.Optional(
        odm.Float(description="Normalized risk score or priority of the event, on a scale of 0 to 100.")
    )
    sequence = odm.Optional(odm.Integer(description="Sequence number of the event."))
    severity = odm.Optional(
        odm.Integer(description="The numeric severity of the event according to your event source.")
    )
    start = odm.Optional(
        odm.Date(description="Contains the date when the event started or when the activity was first observed.")
    )
    timezone = odm.Optional(
        odm.Keyword(
            description="This field should be populated when the event’s timestamp does not include timezone "
            "information already (e.g. default Syslog timestamps)."
        )
    )
    type = odm.Optional(
        odm.List(
            odm.Enum(values=EVENT_TYPE),
            description='Represents a categorization "sub-bucket" that, when used along with the event.category '
            "field values, enables filtering events down to a level appropriate for single visualization.",
        )
    )
    url = odm.Optional(
        odm.Keyword(description="URL linking to an external system to continue investigation of this event.")
    )
