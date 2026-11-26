"""Analytic model."""

from __future__ import annotations

from typing import Annotated

from howler.models import (
    UUID,
    Boolean,
    CaseInsensitiveKeyword,
    Date,
    HowlerEmbeddedModel,
    HowlerESModel,
    Keyword,
    Text,
    enum,
    mapping,
    metadata,
    register_model,
)
from howler.models.howler_data import Assessment

DEFAULT_TRIAGE = {"skip_rationale": False, "valid_assessments": Assessment.list(), "rationales": []}


@register_model(index=True, store=True, description="Comment definition.", embedded=True)
class Comment(HowlerEmbeddedModel):
    """Comment definition."""

    id: UUID
    """A unique ID for the comment"""
    timestamp: Annotated[Date, metadata(default="NOW")]
    """Timestamp at which the comment took place."""
    modified: Annotated[Date, metadata(default="NOW")]
    """Timestamp at which the comment was last edited."""
    detection: Keyword | None = None
    """The detection the comment applies to, if it applies to a particular detection"""
    value: Text
    """The comment itself."""
    user: Keyword
    """User ID who created the comment."""
    reactions: mapping(Keyword, default={})
    """A list of reactions to the comment"""


@register_model(index=True, store=True, description="Settings for triaging this analytic.", embedded=True)
class TriageOptions(HowlerEmbeddedModel):
    """Settings for triaging this analytic."""

    valid_assessments: Annotated[list[Keyword], metadata(default=DEFAULT_TRIAGE["valid_assessments"])]
    """What list of assessments is valid for this analytic?"""
    skip_rationale: Annotated[Boolean, metadata(default=DEFAULT_TRIAGE["skip_rationale"])]
    """Should traiging alerts under this analytic skip the rationale field?"""
    dossiers: list[Keyword] = []
    """A list of dossiers to present to the user when triaging alerts."""
    rationales: Annotated[list[Keyword], metadata(default=DEFAULT_TRIAGE["rationales"])]
    """A provided list of rationales that will be suggested when triaging alerts."""


@register_model(index=True, store=True, description="Notebook data", embedded=True)
class Notebook(HowlerEmbeddedModel):
    """Notebook data."""

    id: UUID
    """A unique ID for the notebook"""
    detection: Keyword | None = None
    """The detection the notebook applies to, if it applies to a particular detection"""
    value: Keyword
    """The link to the notebook"""
    name: Keyword
    """Name for the analytic"""
    user: Keyword
    """User ID who added the notebook."""


@register_model(index=True, store=True, description="Metadata concerning a howler analytic, including configuration.")
class Analytic(HowlerESModel):
    """Metadata concerning a howler analytic, including configuration."""

    analytic_id: UUID
    """A UUID for this analytic"""
    notebooks: list[Notebook] = []
    """A list of useful notebooks for the analytic"""
    name: CaseInsensitiveKeyword
    """The name of the analytic."""
    owner: Keyword | None = None
    """The username of the user who owns this analytic."""
    contributors: list[Keyword] = []
    """A list of users who have contributed to this analytic."""
    description: Text | None = None
    """A markdown description of the analytic"""
    detections: list[CaseInsensitiveKeyword] = []
    """The detections which this analytic contains."""
    comment: list[Comment] = []
    """A list of comments with timestamps and attribution."""
    rule: Keyword | None = None
    """A rule query"""
    rule_type: enum(values=["lucene", "eql", "sigma"], optional=True)
    """Type of rule"""
    rule_crontab: Keyword | None = None
    """The interval for the rule to run at"""
    triage_settings: Annotated[TriageOptions, metadata(default=DEFAULT_TRIAGE)]
    """Settings for triaging this analytic."""
