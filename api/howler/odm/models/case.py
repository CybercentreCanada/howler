from typing import Any, Literal, Optional

from howler import odm
from howler.common.exceptions import HowlerValueError
from howler.config import CLASSIFICATION
from howler.odm.constants import CaseEscalation, Status
from howler.odm.mixins import DatastoreMixin
from howler.utils.compat import StrEnum

CASE_ITEM_TYPES = {"event", "hit", "case", "lead", "reference", "folder", "markdown"}

RULE_INDEX_TYPES = {"hit", "event"}


class RuleIndexTypes(StrEnum):
    """Enumeration of valid index types for case rules.

    Determines which Elasticsearch indexes a case rule query runs against
    during correlation.
    """

    HIT = "hit"
    EVENT = "event"


class CaseItemTypes(StrEnum):
    """Enumeration of valid case item types.

    Case items represent different types of objects that can be associated with a case.
    Each item type corresponds to a specific kind of entity or reference that provides
    context, evidence, or relationships for the case investigation.

    Attributes:
        EVENT: A suspicious or noteworthy event (network connection, process execution, etc.) that
            has been identified and tracked in the system.
        HIT: An alert or detection hit from an analytic that triggered on specific
            telemetry or behavior patterns.
        TABLE: A structured data table containing organized information relevant to
            the case (e.g., timeline, correlation matrix).
        CASE: A reference to another related case, enabling case-to-case relationships
            for tracking linked investigations.
        LEAD: An investigative lead or hypothesis that requires follow-up action or
            validation by analysts.
        REFERENCE: An external reference such as a URL, document, or resource that
            provides additional context or evidence.
        FOLDER: An organizational folder for grouping case items hierarchically.
        MARKDOWN: A markdown document whose value contains the markdown content directly.
    """

    EVENT = "event"
    HIT = "hit"
    TABLE = "table"
    CASE = "case"
    LEAD = "lead"
    REFERENCE = "reference"
    FOLDER = "folder"
    MARKDOWN = "markdown"


@odm.model(index=True, store=True, description="Log definition.")
class CaseLog(odm.Model):
    timestamp = odm.Date(description="Timestamp at which the Log event took place.")
    key = odm.Optional(odm.Keyword(description="The key whose value changed."))
    previous_value = odm.Optional(odm.Keyword(description="The value the key is changing from."))
    new_value = odm.Optional(odm.Keyword(description="The value the key is changing to."))
    user = odm.Keyword(description="User ID who created the log event.")
    explanation = odm.Optional(odm.Text(description="A manual description of the changes made."))

    def __init__(self, data: dict = None, *args, **kwargs):
        if "explanation" not in data:
            required_keys = {"timestamp", "new_value", "user"}
            if required_keys.intersection(set(data.keys())) != required_keys:
                raise HowlerValueError(
                    f"If no explanation provided, you must provide the following values: {','.join(required_keys)}"
                )

        super().__init__(data, *args, **kwargs)


@odm.model(index=True, store=True, description="An item included in a case.")
class CaseItem(odm.Model):
    id: str = odm.UUID(description="Unique identifier for this item.")
    parent: Optional[str] = odm.Optional(
        odm.Keyword(description="ID of the parent folder item, or null for root-level items."),
        default=None,
    )
    name: Optional[str] = odm.Optional(
        odm.Keyword(description="Display name for the item. Optional; the UI falls back to value when absent."),
        default=None,
    )
    type: str = odm.Enum(values=CaseItemTypes, description="Type of case item.")
    value: str = odm.Keyword(description="String reference value for the item (ID, URL, or token).")
    visible: bool = odm.Boolean(default=True, description="Whether the item is visible/accessible in the frontend.")
    classification: Optional[str] = odm.Optional(
        odm.Classification(
            is_user_classification=False,
            copyto="__text__",
            default=CLASSIFICATION.UNRESTRICTED,
            description="Classification of the related record. Automatically populated for hit and event items.",
        )
    )

    def __init__(self, data: dict = None, *args, **kwargs):
        # Enforce: case items must be root-level (parent=null).
        if data and data.get("type") == CaseItemTypes.CASE and data.get("parent") is not None:
            raise HowlerValueError("Case items must be root-level (parent must be null)")
        super().__init__(data, *args, **kwargs)


@odm.model(index=True, store=True, description="Rule used to place/query data into case paths.")
class CaseRule(odm.Model):
    rule_id: str = odm.UUID(description="Unique rule identifier.")
    destination: str = odm.Keyword(description="Destination case path template.")
    query: str = odm.Keyword(description="Lucene query used by this rule.")
    author: str = odm.Keyword(description="Username who created the rule.")
    enabled: bool = odm.Boolean(default=True, description="Whether the rule is currently active.")
    created_at: str = odm.Date(
        default="NOW",
        description="Timestamp when the rule was created.",
    )
    timeframe: Optional[int] = odm.Optional(
        odm.Integer(min=1, description="Number of days the rule stays active. Null means no expiry."),
        default=None,
    )
    expire_after_resolved: bool = odm.Boolean(
        default=False,
        description="When true, the timeframe countdown starts from the case's last "
        "resolution time instead of from rule creation.",
    )
    indexes: list[str] = odm.List(
        odm.Enum(values=RuleIndexTypes),
        default=[RuleIndexTypes.HIT],
        description="Indexes to run this rule against (hit, event, or both).",
    )

    def __init__(self, data: dict = None, *args, **kwargs):
        timeframe = data.get("timeframe") if data else None
        if timeframe is not None and (isinstance(timeframe, bool) or not isinstance(timeframe, int) or timeframe <= 0):
            raise HowlerValueError("Rule timeframe must be a positive integer or None")
        elif timeframe is None and data.get("expire_after_resolved", False):
            raise HowlerValueError("Rule cannot expire after resolved when no timeframe is set")

        super().__init__(data, *args, **kwargs)


@odm.model(index=True, store=True, description="Task associated with a case item path.")
class CaseTask(odm.Model):
    id: str = odm.UUID(description="Task identifier.")
    complete: bool = odm.Boolean(default=False, description="Whether the task is complete.")
    assignment: str | None = odm.Keyword(description="Assigned discipline or user ID.", optional=True)
    summary: str = odm.Text(description="Task summary.")
    path: str = odm.Keyword(description="Associated case item path.", optional=True)


@odm.model(index=True, store=True, description="Enrichment annotations associated with a case path.")
class CaseEnrichment(odm.Model):
    path: str = odm.Keyword(description="Case item path associated with these annotations.")
    annotations: list[str] = odm.List(
        odm.Keyword(),
        default=[],
        description="Annotation IDs associated with the path.",
    )


@odm.model(index=True, store=True, description="Case model with path-based items, enrichments, rules, and tasks.")
class Case(DatastoreMixin["Case"], odm.Model):
    case_id: str = odm.UUID(description="A unique identifier for this case.")
    classification: str = odm.Classification(
        is_user_classification=False,
        copyto="__text__",
        default=CLASSIFICATION.UNRESTRICTED,
        description="Maximum classification for the case",
    )
    title: str = odm.Keyword(description="Case title.")
    summary: str = odm.Text(description="Short case summary.")
    overview: str = odm.Optional(odm.Text(description="Markdown overview of the case."))
    escalation: Literal["normal", "focus", "crisis"] = odm.Enum(
        values=CaseEscalation, default=CaseEscalation.NORMAL, description="Escalation of the case."
    )
    status: str = odm.Enum(values=Status, default=Status.OPEN, description="Status of the case.")
    created: str = odm.Optional(odm.Date(default="NOW", description="Date/time when the case was created."))
    visible: bool = odm.Boolean(default=True, description="Whether the case is visible/accessible in the frontend.")
    updated: Optional[str] = odm.Optional(
        odm.Date(description="Date/time when the case was last updated."),
        default=None,
    )
    start: Optional[str] = odm.Optional(
        odm.Date(description="Date/time when telemetry/alerts in this case started."),
        default=None,
    )
    end: Optional[str] = odm.Optional(
        odm.Date(description="Date/time when telemetry/alerts in this case ended."),
        default=None,
    )
    targets: list[str] = odm.Optional(
        odm.List(
            odm.Keyword(),
            default=[],
            description="A list of target entities related to this case.",
        )
    )
    threats: list[str] = odm.Optional(
        odm.List(
            odm.Keyword(),
            default=[],
            description="A list of known or suspected threat entities related to this case.",
        )
    )
    indicators: list[str] = odm.Optional(
        odm.List(
            odm.Keyword(),
            default=[],
            description="A list of indicators relevant to this case.",
        )
    )
    participants: list[str] = odm.Optional(
        odm.List(
            odm.Keyword(),
            default=[],
            description="A list of users participating in this case.",
        )
    )
    items: list[CaseItem] = odm.Optional(
        odm.List(
            odm.Compound(CaseItem),
            default=[],
            description="Path-scoped case items referencing external object IDs or links.",
        )
    )
    enrichments: list[CaseEnrichment] = odm.Optional(
        odm.List(
            odm.Compound(CaseEnrichment),
            default=[],
            description="Path-scoped enrichment annotations.",
        )
    )
    rules: list[CaseRule] = odm.Optional(
        odm.List(
            odm.Compound(CaseRule),
            default=[],
            description="Rules for routing matched data into case paths.",
        )
    )
    tasks: list[CaseTask] = odm.Optional(
        odm.List(
            odm.Compound(CaseTask),
            default=[],
            description="Tasks associated with this case.",
        )
    )
    log: list[CaseLog] = odm.Optional(
        odm.List(
            odm.Compound(CaseLog),
            default=[],
            description="A list of changes to the case with timestamps and attribution.",
        )
    )

    def as_primitives(self, hidden_fields=False, strip_null=True) -> dict[str, Any]:
        result = super().as_primitives(hidden_fields, strip_null)

        result["__index"] = self.__class__.__name__.lower()

        return result
