# mypy: ignore-errors
from typing import Optional

from howler import odm
from howler.common.exceptions import HowlerValueError
from howler.odm.howler_enum import HowlerEnum
from howler.odm.models.lead import Lead


class Scrutiny(str, HowlerEnum):
    UNSEEN = "unseen"
    SURVEYED = "surveyed"
    SCANNED = "scanned"
    INSPECTED = "inspected"
    INVESTIGATED = "investigated"

    def __str__(self) -> str:
        return self.value


class HitStatus(str, HowlerEnum):
    OPEN = "open"
    IN_PROGRESS = "in-progress"
    ON_HOLD = "on-hold"
    RESOLVED = "resolved"

    def __str__(self) -> str:
        return self.value


class HitStatusTransition(str, HowlerEnum):
    ASSIGN_TO_ME = "assign_to_me"
    ASSIGN_TO_OTHER = "assign_to_other"
    VOTE = "vote"
    ASSESS = "assess"
    RELEASE = "release"
    START = "start"
    PAUSE = "pause"
    RESUME = "resume"
    RE_EVALUATE = "re_evaluate"
    PROMOTE = "promote"
    DEMOTE = "demote"

    def __str__(self) -> str:
        return self.value


class HitOperationType(str, HowlerEnum):
    APPENDED = "appended"
    REMOVED = "removed"
    SET = "set"

    def __str__(self) -> str:
        return self.value


class Escalation(str, HowlerEnum):
    MISS = "miss"
    HIT = "hit"
    ALERT = "alert"
    EVIDENCE = "evidence"

    def __str__(self) -> str:
        return self.value


class Vote(str, HowlerEnum):
    MALICIOUS = "malicious"
    OBSCURE = "obscure"
    BEINIGN = "benign"

    def __str__(self) -> str:
        return self.value


class Assessment(str, HowlerEnum):
    # Keep this order!
    AMBIGUOUS = "ambiguous"
    SECURITY = "security"
    DEVELOPMENT = "development"
    FALSE_POSITIVE = "false-positive"
    LEGITIMATE = "legitimate"

    TRIVIAL = "trivial"
    RECON = "recon"
    ATTEMPT = "attempt"
    COMPROMISE = "compromise"
    MITIGATED = "mitigated"

    def __str__(self) -> str:
        return self.value


class AssessmentEscalationMap(str, HowlerEnum):
    AMBIGUOUS = Escalation.MISS.value
    ATTEMPT = Escalation.EVIDENCE.value
    COMPROMISE = Escalation.EVIDENCE.value
    DEVELOPMENT = Escalation.MISS.value
    FALSE_POSITIVE = Escalation.MISS.value
    LEGITIMATE = Escalation.MISS.value
    MITIGATED = Escalation.EVIDENCE.value
    RECON = Escalation.EVIDENCE.value
    SECURITY = Escalation.MISS.value
    TRIVIAL = Escalation.EVIDENCE.value

    def __int__(self) -> int:
        return self.value

    def __str__(self) -> str:
        return str(self.value)


@odm.model(index=True, store=True, description="Howler Link definition.")
class Link(odm.Model):
    href = odm.Keyword(description="Timestamp at which the comment was last edited.")
    title = odm.Text(description="The title to use for the link.", optional=True)
    icon = odm.Keyword(
        description=(
            "The icon to show. Either an ID corresponding to an "
            "analytical platform application, or an external link."
        )
    )


@odm.model(index=True, store=True, description="Comment definition.")
class Comment(odm.Model):
    id = odm.UUID(description="A unique ID for the comment.")
    timestamp = odm.Date(description="Timestamp at which the comment took place.", default="NOW")
    modified = odm.Date(description="Timestamp at which the comment was last edited.", default="NOW")
    value = odm.Text(description="The comment itself.")
    user = odm.Keyword(description="User ID who created the comment.")
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
    previous_version = odm.Optional(odm.Keyword(description="The version this action was applied to."))
    new_value = odm.Optional(odm.Keyword(description="The value the key is changing to."))
    type = odm.Optional(odm.Enum(values=HitOperationType, description="The operation performed on the value."))
    previous_value = odm.Optional(odm.Keyword(description="The value the key is changing from."))
    user = odm.Keyword(description="User ID who created the log event.")

    def __init__(self, data: dict = None, *args, **kwargs):
        if "explanation" not in data:
            required_keys = {"key", "new_value", "type", "previous_value"}
            if required_keys.intersection(set(data.keys())) != required_keys:
                raise HowlerValueError(
                    f"If no explanation provided, you must provide the following values: {','.join(required_keys)}"
                )

        super().__init__(data, *args, **kwargs)


@odm.model(index=True, store=True, description="Hit outline header.")
class Header(odm.Model):
    threat: Optional[str] = odm.Optional(odm.Text(description="The IP of the threat."))
    target: Optional[str] = odm.Optional(odm.Text(description="The target of the hit."))
    indicators: list[str] = odm.List(odm.Text(description="Indicators of the hit."), default=[])
    summary: Optional[str] = odm.Optional(odm.Text(description="Summary of the hit."))


@odm.model(index=True, store=True, description="Fields describing the location where this alert has been retained.")
class Incident(odm.Model):
    platform: str = odm.Keyword(description="The name of the platform for this incident.")
    incident_id: Optional[str] = odm.Keyword(description="The ID of the incident.", optional=True)
    url: Optional[str] = odm.Keyword(description="The url where the incident can be found.", optional=True)


@odm.model(index=True, store=True, description="Labels for the hit")
class Label(odm.Model):
    assignments = odm.List(odm.Text(description="List of assignments for the hit."), default=[])
    generic = odm.List(odm.Text(description="List of generic labels for the hit."), default=[])
    insight = odm.List(odm.Text(description="List of insight labels for the hit."), default=[])
    mitigation = odm.List(odm.Text(description="List of mitigation labels for the hit."), default=[])
    victim = odm.List(odm.Text(description="List of victim labels for the hit."), default=[])
    campaign = odm.List(odm.Text(description="List of campaign labels for the hit."), default=[])
    threat = odm.List(odm.Text(description="List of threat labels for the hit."), default=[])
    operation = odm.List(odm.Text(description="List of operation labels for the hit."), default=[])


@odm.model(index=True, store=True, description="Votes for the hit")
class Votes(odm.Model):
    benign: list[str] = odm.List(odm.Keyword(), default=[], description="List of users who voted benign.")
    obscure: list[str] = odm.List(odm.Keyword(), default=[], description="List of users who voted obscure.")
    malicious: list[str] = odm.List(odm.Keyword(), default=[], description="List of users who voted malicious.")


DEFAULT_VOTES = {vote: [] for vote in Vote.list()}
DEFAULT_LABELS = {"assignments": [], "generic": []}
DEFAULT_ASSIGNMENT = "unassigned"


@odm.model(
    index=True,
    store=True,
    description="Howler specific definition of the hit that matches the outline.",
)
class HowlerData(odm.Model):
    id: str = odm.UUID(description="A UUID for this hit.")
    analytic: str = odm.CaseInsensitiveKeyword(description="Title of the analytic.")
    assignment: Optional[str] = odm.Keyword(
        description="Unique identifier of the assigned user.",
        default=DEFAULT_ASSIGNMENT,
    )
    bundles: list[str] = odm.List(
        odm.Keyword(
            description="A list of bundle IDs this hit is a part of. Corresponds to the howler.id of the bundle."
        ),
        default=[],
    )
    data: list[str] = odm.List(
        odm.Keyword(description="Raw telemetry records associated with this hit."),
        default=[],
        store=False,
    )
    links: list[Link] = odm.List(
        odm.Compound(Link),
        default=[],
        description="A list of links associated with this hit.",
    )
    detection: Optional[str] = odm.Optional(
        odm.CaseInsensitiveKeyword(description="The detection that produced this hit.")
    )
    hash: str = odm.HowlerHash(
        description=(
            "A hash of the event used for deduplicating hits. Supports any hexadecimal string between 1 "
            "and 64 characters long."
        )
    )
    hits: list[str] = odm.List(
        odm.Keyword(
            description="A list of hit IDs this bundle represents. Corresponds to the howler.id of the child hit."
        ),
        default=[],
    )
    bundle_size: int = odm.Integer(
        description="Number of hits in bundle",
        default=0,
    )
    is_bundle: bool = odm.Boolean(description="Is this hit a bundle or a normal hit?", default=False)
    related: list[str] = odm.List(
        odm.Keyword(
            description="Related hits grouped by the enrichment that correlated them. Populated by enrichments."
        ),
        default=[],
    )
    reliability: Optional[float] = odm.Optional(
        odm.Float(description="Metric decoupled from the value in the detection information.")
    )
    severity: Optional[float] = odm.Optional(
        odm.Float(description="Metric decoupled from the value in the detection information.")
    )
    volume: Optional[float] = odm.Optional(
        odm.Float(description="Metric decoupled from the value in the detection information.")
    )
    confidence: Optional[float] = odm.Optional(
        odm.Float(description="Metric decoupled from the value in the detection information.")
    )
    score: Optional[float] = odm.Optional(
        odm.Float(description="A score assigned by an enrichment to help prioritize triage.", default=0)
    )
    status = odm.Enum(values=HitStatus, default=HitStatus.OPEN, description="Status of the hit.")
    scrutiny = odm.Enum(
        values=Scrutiny,
        default=Scrutiny.UNSEEN,
        description="Level of scrutiny done to this hit.",
    )
    escalation = odm.Enum(
        values=Escalation,
        default=Escalation.HIT,
        description="Level of escalation of this hit.",
    )
    expiry = odm.Optional(
        odm.Date(
            description="User selected time for hit expiry",
        )
    )
    assessment: Optional[str] = odm.Optional(odm.Enum(values=Assessment, description="Assessment of the hit."))
    rationale: Optional[str] = odm.Optional(
        odm.Text(
            description=(
                "The rationale behind the hit assessment. Allows it to be understood and" " verified by other analysts."
            )
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
        description="A list of changes to the hit with timestamps and attribution.",
    )
    monitored: Optional[str] = odm.Optional(odm.Keyword(description="Link to the incident monitoring dashboard."))
    reported: Optional[str] = odm.Optional(odm.Keyword(description="Link to the incident report."))
    mitigated: Optional[str] = odm.Optional(odm.Keyword(description="Link to the mitigation record (tool dependent)."))
    outline: Optional[Header] = odm.Optional(odm.Compound(Header), description="The user specified header of the hit")
    incidents: list[Incident] = odm.List(
        odm.Compound(Incident), default=[], description="Fields describing an incident associated with this alert."
    )
    labels: Label = odm.Optional(
        odm.Compound(Label),
        default=DEFAULT_LABELS,
        description="List of labels relating to the hit",
    )
    votes: Votes = odm.Optional(
        odm.Compound(Votes),
        default=DEFAULT_VOTES,
        description="Votes relating to the hit",
    )
    dossier: list[Lead] = odm.List(
        odm.Compound(Lead), default=[], description="A list of leads forming the dossier associated with this hit"
    )
    viewers: list[str] = odm.List(
        odm.Keyword(description="A list of users currently viewing the hit"),
        default=[],
    )
