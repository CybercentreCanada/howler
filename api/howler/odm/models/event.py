# mypy: ignore-errors

from howler import odm
from howler.common.logging import get_logger
from howler.odm.howler_enum import HowlerEnum
from howler.odm.mixins import DatastoreMixin
from howler.odm.models.log import Log
from howler.odm.models.record import Record

logger = get_logger(__file__)


class Escalation(str, HowlerEnum):
    HIT = "hit"
    ALERT = "alert"
    EVIDENCE = "evidence"


@odm.model(index=True, store=True, description="Comment definition.")
class Comment(odm.Model):
    id: str = odm.UUID(description="A unique ID for the comment.")
    timestamp = odm.Date(description="Timestamp at which the comment took place.", default="NOW")
    modified = odm.Date(description="Timestamp at which the comment was last edited.", default="NOW")
    value: str = odm.Text(description="The comment itself.")
    user: str = odm.Keyword(description="User ID who created the comment.")
    reactions: dict[str, str] = odm.Mapping(
        odm.Keyword(),
        default={},
        description="A list of reactions to the comment.",
    )


DEFAULT_LABELS = {"assignments": [], "generic": []}


@odm.model(
    index=True,
    store=True,
    description="Event metadata fields, howler specific.",
)
class EventData(odm.Model):
    id: str = odm.UUID(description="A UUID for this event.")
    data: list[str] = odm.List(
        odm.Keyword(description="Raw telemetry records associated with this event."),
        default=[],
        store=False,
    )
    hash: str = odm.HowlerHash(
        description=(
            "A hash of the event used for deduplicating hits. Supports any hexadecimal string between 1 "
            "and 64 characters long."
        )
    )
    related: list[str] = odm.List(
        odm.Keyword(description="Related records."),
        default=[],
    )
    score: float | None = odm.Optional(
        odm.Float(description="A score assigned by an enrichment to help prioritize triage.", default=0)
    )
    escalation = odm.Enum(
        values=Escalation,
        default=Escalation.HIT,
        description="Level of escalation of this event.",
    )
    expiry = odm.Optional(
        odm.Date(
            description="User selected time for event expiry",
        )
    )
    comment: list[Comment] = odm.List(
        odm.Compound(Comment),
        default=[],
        description="A list of comments with timestamps and attribution.",
    )
    log: list[Log] = odm.List(
        odm.Compound(Log),
        default=[],
        description="A list of changes to the event with timestamps and attribution.",
    )


@odm.model(
    index=True,
    store=True,
    description="Event schema which is an extended version of Elastic Common Schema (ECS)",
    id_field="howler.id",
)
class Event(DatastoreMixin["Event"], Record):
    # Howler extended fields. Deviates from ECS
    howler: EventData = odm.Compound(
        EventData,
        description="Howler specific definition of the event",
    )


if __name__ == "__main__":
    from pprint import pprint

    fields = {k: f"{v.__class__.__name__}{' (array)' if v.multivalued else ''}" for k, v in Event.flat_fields().items()}
    pprint(fields)  # noqa: T203
