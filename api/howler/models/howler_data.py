"""Howler-specific hit metadata model."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from howler.models import (
    UUID,
    CaseInsensitiveKeyword,
    Date,
    Float,
    HowlerEmbeddedModel,
    HowlerHash,
    Keyword,
    Text,
    enum,
    mapping,
    metadata,
    register_model,
)
from howler.models.constants import HowlerStrEnum, Status
from howler.models.header import Header as _Header
from howler.models.lead import Lead
from howler.models.log import Log as _Log
from howler.utils.isotime import now_as_datetime
from howler.utils.uid import get_random_id


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


@register_model(index=True, store=True, description="Howler Link definition.", embedded=True)
class Link(HowlerEmbeddedModel):
    """Howler Link definition."""

    href: Keyword
    """Timestamp at which the comment was last edited."""
    title: Keyword | None = None
    """The title to use for the link."""
    icon: Keyword | None = None
    """The icon to show. Either an ID corresponding to an analytical platform application, or an external link."""


@register_model(index=True, store=True, description="Comment definition.", embedded=True)
class Comment(HowlerEmbeddedModel):
    """Comment definition."""

    id: UUID = Field(default_factory=get_random_id)
    """A unique ID for the comment."""
    timestamp: Date = Field(default_factory=now_as_datetime)
    """Timestamp at which the comment took place."""
    modified: Date = Field(default_factory=now_as_datetime)
    """Timestamp at which the comment was last edited."""
    value: Text
    """The comment itself."""
    user: Keyword
    """User ID who created the comment."""
    reactions: mapping(Keyword, default={})
    """A list of reactions to the comment."""


@register_model(
    index=True,
    store=True,
    description="Fields describing the location where this alert has been retained.",
    embedded=True,
)
class Incident(HowlerEmbeddedModel):
    """Fields describing the location where this alert has been retained."""

    platform: Keyword
    """The name of the platform for this incident."""
    incident_id: Keyword | None = None
    """The ID of the incident."""
    url: Keyword | None = None
    """The url where the incident can be found."""


@register_model(index=True, store=True, description="Labels for the hit", embedded=True)
class Label(HowlerEmbeddedModel):
    """Labels for the hit."""

    assignments: list[Keyword] = []
    """List of assignments for the hit."""
    generic: list[Keyword] = []
    """List of generic labels for the hit."""
    insight: list[Keyword] = []
    """List of insight labels for the hit."""
    mitigation: list[Keyword] = []
    """List of mitigation labels for the hit."""
    victim: list[Keyword] = []
    """List of victim labels for the hit."""
    campaign: list[Keyword] = []
    """List of campaign labels for the hit."""
    threat: list[Keyword] = []
    """List of threat labels for the hit."""
    tuning: list[Keyword] = []
    """List of tuning labels for the hit."""
    operation: list[Keyword] = []
    """List of operation labels for the hit."""


@register_model(index=True, store=True, description="Votes for the hit", embedded=True)
class Votes(HowlerEmbeddedModel):
    """Votes for the hit."""

    benign: list[Keyword] = []
    """List of users who voted benign."""
    obscure: list[Keyword] = []
    """List of users who voted obscure."""
    malicious: list[Keyword] = []
    """List of users who voted malicious."""


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

    id: UUID = Field(default_factory=get_random_id)
    """A UUID for this hit."""
    analytic: CaseInsensitiveKeyword
    """Title of the analytic."""
    assignment: Keyword = DEFAULT_ASSIGNMENT
    """Unique identifier of the assigned user."""
    data: Annotated[list[Keyword], metadata(store=False, sync=False)] = []
    """Raw telemetry records associated with this hit."""
    links: Annotated[list[Link], metadata(sync=False)] = []
    """A list of links associated with this hit."""
    detection: CaseInsensitiveKeyword | None = None
    """The detection that produced this hit."""
    hash: HowlerHash
    (
        "A hash of the event used for deduplicating hits. Supports any hexadecimal string between 1 and 64 characters "
        "long."
    )
    related: list[Keyword] = []
    """Related records."""
    reliability: Float | None = None
    """Metric decoupled from the value in the detection information."""
    severity: Float | None = None
    """Metric decoupled from the value in the detection information."""
    volume: Float | None = None
    """Metric decoupled from the value in the detection information."""
    confidence: Float | None = None
    """Metric decoupled from the value in the detection information."""
    score: Annotated[Float | None, metadata(optional=True)] = 0
    """A score assigned by an enrichment to help prioritize triage."""
    status: enum(values=Status, default=Status.OPEN)
    """Status of the hit."""
    scrutiny: enum(values=Scrutiny, default=Scrutiny.UNSEEN)
    """Level of scrutiny done to this hit."""
    escalation: enum(values=Escalation, default=Escalation.HIT)
    """Level of escalation of this hit."""
    expiry: Date | None = None
    """User selected time for hit expiry"""
    assessment: enum(values=Assessment, optional=True)
    """Assessment of the hit."""
    rationale: Keyword | None = None
    """The rationale behind the hit assessment. Allows it to be understood and verified by other analysts."""
    triaged: Date | None = None
    """Timestamp at which the hit was triaged."""
    comment: Annotated[list[Comment], metadata(sync=False)] = []
    """A list of comments with timestamps and attribution."""
    log: Annotated[list[_Log], metadata(sync=False)] = []
    """A list of changes to the hit with timestamps and attribution."""
    monitored: Keyword | None = None
    """Link to the incident monitoring dashboard."""
    reported: Keyword | None = None
    """Link to the incident report."""
    mitigated: Keyword | None = None
    """Link to the mitigation record (tool dependent)."""
    outline: _Header | None = None
    """The user specified header of the hit"""
    incidents: list[Incident] = []
    """Fields describing an incident associated with this alert."""
    labels: Annotated[Label | None, metadata(optional=True, default=DEFAULT_LABELS)]
    """List of labels relating to the hit"""
    votes: Annotated[Votes | None, metadata(optional=True, default=DEFAULT_VOTES)]
    """Votes relating to the hit"""
    dossier: Annotated[list[Lead], metadata(sync=False)] = []
    """A list of leads forming the dossier associated with this hit"""
