# mypy: ignore-errors

from howler import odm
from howler.common.exceptions import HowlerValueError
from howler.common.logging import get_logger
from howler.odm.howler_enum import HowlerEnum
from howler.odm.models.record import Record

logger = get_logger(__file__)


class Escalation(str, HowlerEnum):
    HIT = "hit"
    ALERT = "alert"
    EVIDENCE = "evidence"

    def __str__(self) -> str:
        return self.value


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


@odm.model(index=True, store=True, description="Log definition.")
class Log(odm.Model):
    timestamp = odm.Date(description="Timestamp at which the Log event took place.")
    key = odm.Optional(odm.Keyword(description="The key whose value changed."))
    explanation = odm.Optional(odm.Text(description="A manual description of the changes made."))
    new_value = odm.Optional(odm.Keyword(description="The value the key is changing to."))
    previous_value = odm.Optional(odm.Keyword(description="The value the key is changing from."))
    user = odm.Keyword(description="User ID who created the log event.")

    def __init__(self, data: dict = None, *args, **kwargs):
        if "explanation" not in data:
            required_keys = {"key", "new_value", "previous_value"}
            if required_keys.intersection(set(data.keys())) != required_keys:
                raise HowlerValueError(
                    f"If no explanation provided, you must provide the following values: {','.join(required_keys)}"
                )

        super().__init__(data, *args, **kwargs)


DEFAULT_LABELS = {"assignments": [], "generic": []}


@odm.model(
    index=True,
    store=True,
    description="Observable metadata fields, howler specific.",
)
class ObservableData(odm.Model):
    id: str = odm.UUID(description="A UUID for this observable.")
    data: list[str] = odm.List(
        odm.Keyword(description="Raw telemetry records associated with this observable."),
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
        description="Level of escalation of this observable.",
    )
    expiry = odm.Optional(
        odm.Date(
            description="User selected time for observable expiry",
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
        description="A list of changes to the observable with timestamps and attribution.",
    )
    viewers: list[str] = odm.List(
        odm.Keyword(description="A list of users currently viewing the observable"),
        default=[],
    )


@odm.model(
    index=True,
    store=True,
    description="Observable schema which is an extended version of Elastic Common Schema (ECS)",
)
class Observable(Record):
    # Howler extended fields. Deviates from ECS
    howler: ObservableData = odm.Compound(
        ObservableData,
        description="Howler specific definition of the observable",
    )


if __name__ == "__main__":
    from pprint import pprint

    fields = {
        k: f"{v.__class__.__name__}{' (array)' if v.multivalued else ''}" for k, v in Observable.flat_fields().items()
    }
    pprint(fields)  # noqa: T203
