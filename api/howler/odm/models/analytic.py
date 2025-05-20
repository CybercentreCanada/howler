# mypy: ignore-errors
from typing import Optional

from howler import odm
from howler.odm.models.howler_data import Assessment


@odm.model(index=True, store=True, description="Comment definition.")
class Comment(odm.Model):
    id = odm.UUID(description="A unique ID for the comment")
    timestamp = odm.Date(description="Timestamp at which the comment took place.", default="NOW")
    modified = odm.Date(description="Timestamp at which the comment was last edited.", default="NOW")
    detection: Optional[str] = odm.Keyword(
        description="The detection the comment applies to, if it applies to a particular detection",
        optional=True,
    )
    value = odm.Text(description="The comment itself.")
    user = odm.Keyword(description="User ID who created the comment.")
    reactions: dict[str, str] = odm.Mapping(
        odm.Keyword(),
        default={},
        description="A list of reactions to the comment",
    )


DEFAULT_TRIAGE = {"skip_rationale": False, "valid_assessments": Assessment.list()}


@odm.model(index=True, store=True, description="Settings for triaging this analytic.")
class TriageOptions(odm.Model):
    valid_assessments: list[str] = odm.List(
        odm.Keyword(),
        default=DEFAULT_TRIAGE["valid_assessments"],
        description="What list of assessments is valid for this analytic?",
    )
    skip_rationale: bool = odm.Boolean(
        description="Should traiging alerts under this analytic skip the rationale field?",
        default=DEFAULT_TRIAGE["skip_rationale"],
    )
    dossiers: list[str] = odm.List(
        odm.Keyword(), description="A list of dossiers to present to the user when triaging alerts.", default=[]
    )


@odm.model(index=True, store=True, description="Notebook data")
class Notebook(odm.Model):
    id = odm.UUID(description="A unique ID for the notebook")
    detection: Optional[str] = odm.Keyword(
        description="The detection the notebook applies to, if it applies to a particular detection",
        optional=True,
    )
    value = odm.Text(description="The link to the notebook")
    name = odm.Text(description="Name for the analytic")
    user = odm.Keyword(description="User ID who added the notebook.")


@odm.model(index=True, store=True, description="Metadata concerning a howler analytic, including configuration.")
class Analytic(odm.Model):
    analytic_id: str = odm.UUID(description="A UUID for this analytic")
    notebooks: list[Notebook] = odm.List(
        odm.Compound(Notebook),
        default=[],
        description="A list of useful notebooks for the analytic",
    )
    name: str = odm.Keyword(description="The name of the analytic.")
    owner: Optional[str] = odm.Keyword(description="The username of the user who owns this analytic.", optional=True)
    contributors: list[str] = odm.List(
        odm.Keyword(),
        description="A list of users who have contributed to this analytic.",
        default=[],
    )
    description: Optional[str] = odm.Text(description="A markdown description of the analytic", optional=True)
    detections: list[str] = odm.List(
        odm.Keyword(),
        description="The detections which this analytic contains.",
        default=[],
    )
    comment: list[Comment] = odm.List(
        odm.Compound(Comment),
        default=[],
        description="A list of comments with timestamps and attribution.",
    )
    rule: Optional[str] = odm.Keyword(description="A rule query", optional=True)
    rule_type: Optional[str] = odm.Optional(odm.Enum(values=["lucene", "eql", "sigma"], description="Type of rule"))
    rule_crontab: Optional[str] = odm.Keyword(description="The interval for the rule to run at", optional=True)
    triage_settings: Optional[TriageOptions] = odm.Compound(
        TriageOptions,
        description="Settings for triaging this analytic.",
        default=DEFAULT_TRIAGE,
    )
