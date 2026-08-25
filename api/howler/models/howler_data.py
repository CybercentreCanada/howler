"""Howler-specific hit metadata model."""

from __future__ import annotations

from typing import Any

from pydantic import model_validator

from howler.models import (
    HowlerEmbeddedModel,
    case_insensitive_keyword,
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
from howler.models.constants import HowlerStrEnum, Status
from howler.models.lead import Lead


class Scrutiny(HowlerStrEnum):
    """Level of scrutiny performed on a hit."""

    UNSEEN = "unseen"
    SURVEYED = "surveyed"
    SCANNED = "scanned"
    INSPECTED = "inspected"
    INVESTIGATED = "investigated"


class HitStatusTransition(HowlerStrEnum):
    """Transitions available for the status of a hit."""

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


class HitOperationType(HowlerStrEnum):
    """Type of operation recorded in a hit log entry."""

    APPENDED = "appended"
    REMOVED = "removed"
    SET = "set"


class Escalation(HowlerStrEnum):
    """Level of escalation of a hit."""

    MISS = "miss"
    HIT = "hit"
    ALERT = "alert"
    EVIDENCE = "evidence"


class Vote(HowlerStrEnum):
    """A vote cast on a hit."""

    MALICIOUS = "malicious"
    OBSCURE = "obscure"
    BEINIGN = "benign"


class Assessment(HowlerStrEnum):
    """Assessment applied to a hit. Order matters for UI presentation."""

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


class AssessmentEscalationMap(HowlerStrEnum):
    """Maps an assessment value to its corresponding escalation level."""

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
        return int(self.value)


@register_model(index=True, store=True, description="Howler Link definition.", embedded=True)
class Link(HowlerEmbeddedModel):
    """Howler Link definition."""

    href: keyword(description="Timestamp at which the comment was last edited.")
    title: optional(keyword(), description="The title to use for the link.")
    icon: optional(
        keyword(),
        description=(
            "The icon to show. Either an ID corresponding to an analytical platform application, or an external link."
        ),
    )


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
    previous_version: optional(keyword(), description="The version this action was applied to.")
    new_value: optional(keyword(), description="The value the key is changing to.")
    type: optional(enum(values=HitOperationType), description="The operation performed on the value.")
    previous_value: optional(keyword(), description="The value the key is changing from.")
    user: keyword(description="User ID who created the log event.")

    @model_validator(mode="before")
    @classmethod
    def _require_explanation_or_details(cls, data: Any) -> Any:
        """Mirror the legacy ``Log.__init__`` requirement."""
        if isinstance(data, dict) and "explanation" not in data:
            required_keys = {"key", "new_value", "type", "previous_value"}
            if required_keys.intersection(set(data.keys())) != required_keys:
                raise ValueError(
                    f"If no explanation provided, you must provide the following values: {','.join(required_keys)}"
                )
        return data


@register_model(index=True, store=True, description="Hit outline header.", embedded=True)
class Header(HowlerEmbeddedModel):
    """Hit outline header."""

    threat: optional(keyword(), description="The IP of the threat.")
    target: optional(keyword(), description="The target of the hit.")
    indicators: list_field(keyword(), default=[], description="Indicators of the hit.")
    summary: optional(keyword(), description="Summary of the hit.")


@register_model(
    index=True,
    store=True,
    description="Fields describing the location where this alert has been retained.",
    embedded=True,
)
class Incident(HowlerEmbeddedModel):
    """Fields describing the location where this alert has been retained."""

    platform: keyword(description="The name of the platform for this incident.")
    incident_id: optional(keyword(), description="The ID of the incident.")
    url: optional(keyword(), description="The url where the incident can be found.")


@register_model(index=True, store=True, description="Labels for the hit", embedded=True)
class Label(HowlerEmbeddedModel):
    """Labels for the hit."""

    assignments: list_field(keyword(), default=[], description="List of assignments for the hit.")
    generic: list_field(keyword(), default=[], description="List of generic labels for the hit.")
    insight: list_field(keyword(), default=[], description="List of insight labels for the hit.")
    mitigation: list_field(keyword(), default=[], description="List of mitigation labels for the hit.")
    victim: list_field(keyword(), default=[], description="List of victim labels for the hit.")
    campaign: list_field(keyword(), default=[], description="List of campaign labels for the hit.")
    threat: list_field(keyword(), default=[], description="List of threat labels for the hit.")
    tuning: list_field(keyword(), default=[], description="List of tuning labels for the hit.")
    operation: list_field(keyword(), default=[], description="List of operation labels for the hit.")


@register_model(index=True, store=True, description="Votes for the hit", embedded=True)
class Votes(HowlerEmbeddedModel):
    """Votes for the hit."""

    benign: list_field(keyword(), default=[], description="List of users who voted benign.")
    obscure: list_field(keyword(), default=[], description="List of users who voted obscure.")
    malicious: list_field(keyword(), default=[], description="List of users who voted malicious.")


DEFAULT_VOTES = {vote.value: [] for vote in Vote}
DEFAULT_LABELS = {"assignments": [], "generic": []}
DEFAULT_ASSIGNMENT = "unassigned"


@register_model(
    index=True,
    store=True,
    description="Howler specific definition of the hit that matches the outline.",
    embedded=True,
)
class HowlerData(HowlerEmbeddedModel):
    """Howler specific definition of the hit that matches the outline."""

    id: uuid(description="A UUID for this hit.")
    analytic: case_insensitive_keyword(description="Title of the analytic.")
    assignment: keyword(default=DEFAULT_ASSIGNMENT, description="Unique identifier of the assigned user.")
    data: list_field(
        keyword(),
        default=[],
        store=False,
        sync=False,
        description="Raw telemetry records associated with this hit.",
    )
    links: list_field(compound(Link), default=[], description="A list of links associated with this hit.", sync=False)
    detection: optional(case_insensitive_keyword(), description="The detection that produced this hit.")
    hash: howler_hash(
        description=(
            "A hash of the event used for deduplicating hits. Supports any hexadecimal string between 1 "
            "and 64 characters long."
        )
    )
    related: list_field(keyword(), default=[], description="Related records.")
    reliability: optional(float_field(), description="Metric decoupled from the value in the detection information.")
    severity: optional(float_field(), description="Metric decoupled from the value in the detection information.")
    volume: optional(float_field(), description="Metric decoupled from the value in the detection information.")
    confidence: optional(float_field(), description="Metric decoupled from the value in the detection information.")
    score: optional(
        float_field(), default=0, description="A score assigned by an enrichment to help prioritize triage."
    )
    status: enum(values=Status, default=Status.OPEN, description="Status of the hit.")
    scrutiny: enum(values=Scrutiny, default=Scrutiny.UNSEEN, description="Level of scrutiny done to this hit.")
    escalation: enum(values=Escalation, default=Escalation.HIT, description="Level of escalation of this hit.")
    expiry: optional(date(), description="User selected time for hit expiry")
    assessment: optional(enum(values=Assessment), description="Assessment of the hit.")
    rationale: optional(
        keyword(),
        description=(
            "The rationale behind the hit assessment. Allows it to be understood and verified by other analysts."
        ),
    )
    triaged: optional(date(), description="Timestamp at which the hit was triaged.")
    comment: list_field(
        compound(Comment),
        default=[],
        description="A list of comments with timestamps and attribution.",
        sync=False,
    )
    log: list_field(
        compound(Log),
        default=[],
        description="A list of changes to the hit with timestamps and attribution.",
        sync=False,
    )
    monitored: optional(keyword(), description="Link to the incident monitoring dashboard.")
    reported: optional(keyword(), description="Link to the incident report.")
    mitigated: optional(keyword(), description="Link to the mitigation record (tool dependent).")
    outline: optional(compound(Header), description="The user specified header of the hit")
    incidents: list_field(
        compound(Incident),
        default=[],
        description="Fields describing an incident associated with this alert.",
    )
    labels: optional(compound(Label), default=DEFAULT_LABELS, description="List of labels relating to the hit")
    votes: optional(compound(Votes), default=DEFAULT_VOTES, description="Votes relating to the hit")
    dossier: list_field(
        compound(Lead),
        default=[],
        description="A list of leads forming the dossier associated with this hit",
        sync=False,
    )
