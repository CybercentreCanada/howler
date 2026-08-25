"""Analytic model."""

from __future__ import annotations

from howler.models import (
    HowlerEmbeddedModel,
    HowlerESModel,
    boolean,
    case_insensitive_keyword,
    compound,
    date,
    enum,
    keyword,
    list_field,
    mapping,
    optional,
    register_model,
    text,
    uuid,
)
from howler.models.howler_data import Assessment

DEFAULT_TRIAGE = {"skip_rationale": False, "valid_assessments": Assessment.list(), "rationales": []}


@register_model(index=True, store=True, description="Comment definition.", embedded=True)
class Comment(HowlerEmbeddedModel):
    """Comment definition."""

    id: uuid(description="A unique ID for the comment")
    timestamp: date(default="NOW", description="Timestamp at which the comment took place.")
    modified: date(default="NOW", description="Timestamp at which the comment was last edited.")
    detection: optional(
        keyword(), description="The detection the comment applies to, if it applies to a particular detection"
    )
    value: text(description="The comment itself.")
    user: keyword(description="User ID who created the comment.")
    reactions: mapping(keyword(), default={}, description="A list of reactions to the comment")


@register_model(index=True, store=True, description="Settings for triaging this analytic.", embedded=True)
class TriageOptions(HowlerEmbeddedModel):
    """Settings for triaging this analytic."""

    valid_assessments: list_field(
        keyword(),
        default=DEFAULT_TRIAGE["valid_assessments"],
        description="What list of assessments is valid for this analytic?",
    )
    skip_rationale: boolean(
        description="Should traiging alerts under this analytic skip the rationale field?",
        default=DEFAULT_TRIAGE["skip_rationale"],
    )
    dossiers: list_field(
        keyword(), description="A list of dossiers to present to the user when triaging alerts.", default=[]
    )
    rationales: list_field(
        keyword(),
        default=DEFAULT_TRIAGE["rationales"],
        description="A provided list of rationales that will be suggested when triaging alerts.",
    )


@register_model(index=True, store=True, description="Notebook data", embedded=True)
class Notebook(HowlerEmbeddedModel):
    """Notebook data."""

    id: uuid(description="A unique ID for the notebook")
    detection: optional(
        keyword(), description="The detection the notebook applies to, if it applies to a particular detection"
    )
    value: keyword(description="The link to the notebook")
    name: keyword(description="Name for the analytic")
    user: keyword(description="User ID who added the notebook.")


@register_model(index=True, store=True, description="Metadata concerning a howler analytic, including configuration.")
class Analytic(HowlerESModel):
    """Metadata concerning a howler analytic, including configuration."""

    analytic_id: uuid(description="A UUID for this analytic")
    notebooks: list_field(compound(Notebook), default=[], description="A list of useful notebooks for the analytic")
    name: case_insensitive_keyword(description="The name of the analytic.")
    owner: optional(keyword(), description="The username of the user who owns this analytic.")
    contributors: list_field(
        keyword(), description="A list of users who have contributed to this analytic.", default=[]
    )
    description: optional(text(), description="A markdown description of the analytic")
    detections: list_field(
        case_insensitive_keyword(), description="The detections which this analytic contains.", default=[]
    )
    comment: list_field(
        compound(Comment), default=[], description="A list of comments with timestamps and attribution."
    )
    rule: optional(keyword(), description="A rule query")
    rule_type: optional(enum(values=["lucene", "eql", "sigma"]), description="Type of rule")
    rule_crontab: optional(keyword(), description="The interval for the rule to run at")
    triage_settings: compound(TriageOptions, description="Settings for triaging this analytic.", default=DEFAULT_TRIAGE)
