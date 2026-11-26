"""Analytic model."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from howler.models import (
    HowlerEmbeddedModel,
    HowlerESModel,
    boolean,
    case_insensitive_keyword,
    date,
    enum,
    keyword,
    list_field,
    mapping,
    register_model,
    text,
    uuid,
)
from howler.models.howler_data import Assessment

DEFAULT_TRIAGE = {"skip_rationale": False, "valid_assessments": Assessment.list(), "rationales": []}


@register_model(index=True, store=True, description="Comment definition.", embedded=True)
class Comment(HowlerEmbeddedModel):
    """Comment definition."""

    id: uuid()
    """A unique ID for the comment"""
    timestamp: date(default="NOW")
    """Timestamp at which the comment took place."""
    modified: date(default="NOW")
    """Timestamp at which the comment was last edited."""
    detection: keyword(optional=True)
    """The detection the comment applies to, if it applies to a particular detection"""
    value: text()
    """The comment itself."""
    user: keyword()
    """User ID who created the comment."""
    reactions: mapping(keyword(), default={})
    """A list of reactions to the comment"""


@register_model(index=True, store=True, description="Settings for triaging this analytic.", embedded=True)
class TriageOptions(HowlerEmbeddedModel):
    """Settings for triaging this analytic."""

    valid_assessments: list_field(keyword(), default=DEFAULT_TRIAGE["valid_assessments"])
    """What list of assessments is valid for this analytic?"""
    skip_rationale: boolean(default=DEFAULT_TRIAGE["skip_rationale"])
    """Should traiging alerts under this analytic skip the rationale field?"""
    dossiers: list_field(keyword(), default=[])
    """A list of dossiers to present to the user when triaging alerts."""
    rationales: list_field(keyword(), default=DEFAULT_TRIAGE["rationales"])
    """A provided list of rationales that will be suggested when triaging alerts."""


@register_model(index=True, store=True, description="Notebook data", embedded=True)
class Notebook(HowlerEmbeddedModel):
    """Notebook data."""

    id: uuid()
    """A unique ID for the notebook"""
    detection: keyword(optional=True)
    """The detection the notebook applies to, if it applies to a particular detection"""
    value: keyword()
    """The link to the notebook"""
    name: keyword()
    """Name for the analytic"""
    user: keyword()
    """User ID who added the notebook."""


@register_model(index=True, store=True, description="Metadata concerning a howler analytic, including configuration.")
class Analytic(HowlerESModel):
    """Metadata concerning a howler analytic, including configuration."""

    analytic_id: uuid()
    """A UUID for this analytic"""
    notebooks: list_field(Notebook, default=[])
    """A list of useful notebooks for the analytic"""
    name: case_insensitive_keyword()
    """The name of the analytic."""
    owner: keyword(optional=True)
    """The username of the user who owns this analytic."""
    contributors: list_field(keyword(), default=[])
    """A list of users who have contributed to this analytic."""
    description: text(optional=True)
    """A markdown description of the analytic"""
    detections: list_field(case_insensitive_keyword(), default=[])
    """The detections which this analytic contains."""
    comment: list_field(Comment, default=[])
    """A list of comments with timestamps and attribution."""
    rule: keyword(optional=True)
    """A rule query"""
    rule_type: enum(values=["lucene", "eql", "sigma"], optional=True)
    """Type of rule"""
    rule_crontab: keyword(optional=True)
    """The interval for the rule to run at"""
    triage_settings: Annotated[TriageOptions, Field(default=DEFAULT_TRIAGE)]
    """Settings for triaging this analytic."""
