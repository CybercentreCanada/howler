"""Case model."""

from __future__ import annotations

from typing import Any

from pydantic import model_validator

from howler.config import CLASSIFICATION
from howler.models import (
    HowlerEmbeddedModel,
    HowlerESModel,
    boolean,
    classification,
    compound,
    date,
    enum,
    integer,
    keyword,
    list_field,
    optional,
    register_model,
    text,
    uuid,
)
from howler.models.base import HowlerModelMixin
from howler.models.constants import CaseEscalation, HowlerStrEnum, Status

RULE_INDEX_TYPES = {"hit", "event"}


class RuleIndexTypes(HowlerStrEnum):
    """Valid index types for case rules.

    Determines which Elasticsearch indexes a case rule query runs against during correlation.
    """

    HIT = "hit"
    EVENT = "event"


class CaseItemTypes(HowlerStrEnum):
    """Valid case item types.

    Case items represent different types of objects that can be associated with a case. Each
    item type corresponds to a specific kind of entity or reference that provides context,
    evidence, or relationships for the case investigation.
    """

    EVENT = "event"
    HIT = "hit"
    CASE = "case"
    REFERENCE = "reference"
    FOLDER = "folder"
    MARKDOWN = "markdown"


@register_model(index=True, store=True, description="Log definition.", embedded=True)
class CaseLog(HowlerEmbeddedModel):
    """Log definition."""

    timestamp: date(description="Timestamp at which the Log event took place.")
    key: optional(keyword(), description="The key whose value changed.")
    previous_value: optional(keyword(), description="The value the key is changing from.")
    new_value: optional(keyword(), description="The value the key is changing to.")
    user: keyword(description="User ID who created the log event.")
    explanation: optional(text(), description="A manual description of the changes made.")

    @model_validator(mode="before")
    @classmethod
    def _require_explanation_or_details(cls, data: Any) -> Any:
        """Mirror the legacy ``CaseLog.__init__`` requirement."""
        if isinstance(data, dict) and "explanation" not in data:
            required_keys = {"timestamp", "new_value", "user"}
            if required_keys.intersection(set(data.keys())) != required_keys:
                raise ValueError(
                    f"If no explanation provided, you must provide the following values: {','.join(required_keys)}"
                )
        return data


@register_model(index=True, store=True, description="An item included in a case.", embedded=True)
class CaseItem(HowlerEmbeddedModel):
    """An item included in a case."""

    id: uuid(description="Unique identifier for this item.")
    parent: optional(keyword(), default=None, description="ID of the parent folder item, or null for root-level items.")
    name: optional(
        text(),
        default=None,
        description="Display name for the item. Optional; the UI falls back to value when absent.",
    )
    type: enum(values=CaseItemTypes, description="Type of case item.")
    value: text(description="String reference value for the item (ID, URL, or token), or markdown.")
    visible: boolean(default=True, description="Whether the item is visible/accessible in the frontend.")
    classification: optional(
        classification(
            is_user_classification=False,
            copyto="__text__",
        ),
        default=CLASSIFICATION.UNRESTRICTED,
        description="Classification of the related record. Automatically populated for hit and event items.",
    )

    @model_validator(mode="before")
    @classmethod
    def _validate_item_shape(cls, data: Any) -> Any:
        """Mirror the legacy ``CaseItem.__init__`` root-level and folder-value rules."""
        if not isinstance(data, dict):
            return data
        data = dict(data)

        # Enforce: case items must be root-level (parent=null).
        if data.get("type") == CaseItemTypes.CASE and data.get("parent") is not None:
            raise ValueError("Case items must be root-level (parent must be null)")

        # Set value equal to name for folder items
        if data.get("type") == CaseItemTypes.FOLDER:
            data["value"] = data.get("name")

        return data


@register_model(index=True, store=True, description="Rule used to place/query data into case paths.", embedded=True)
class CaseRule(HowlerEmbeddedModel):
    """Rule used to place/query data into case paths."""

    rule_id: uuid(description="Unique rule identifier.")
    destination: keyword(description="Destination case path template.")
    query: keyword(description="Lucene query used by this rule.")
    author: keyword(description="Username who created the rule.")
    enabled: boolean(default=True, description="Whether the rule is currently active.")
    created_at: date(default="NOW", description="Timestamp when the rule was created.")
    timeframe: optional(
        integer(min=1), default=None, description="Number of days the rule stays active. Null means no expiry."
    )
    expire_after_resolved: boolean(
        default=False,
        description="When true, the timeframe countdown starts from the case's last "
        "resolution time instead of from rule creation.",
    )
    indexes: list_field(
        enum(values=RuleIndexTypes),
        default=[RuleIndexTypes.HIT.value],
        description="Indexes to run this rule against (hit, event, or both).",
    )

    @model_validator(mode="before")
    @classmethod
    def _validate_timeframe(cls, data: Any) -> Any:
        """Enforce that ``expire_after_resolved=True`` requires a positive ``timeframe``."""
        if not isinstance(data, dict):
            return data
        timeframe = data.get("timeframe")
        if timeframe is not None and (isinstance(timeframe, bool) or not isinstance(timeframe, int) or timeframe <= 0):
            raise ValueError("Rule timeframe must be a positive integer or None")
        if timeframe is None and data.get("expire_after_resolved", False):
            raise ValueError("Rule cannot expire after resolved when no timeframe is set")
        return data


@register_model(index=True, store=True, description="Task associated with a case item path.", embedded=True)
class CaseTask(HowlerEmbeddedModel):
    """Task associated with a case item path."""

    id: uuid(description="Task identifier.")
    complete: boolean(default=False, description="Whether the task is complete.")
    assignment: optional(keyword(), description="Assigned discipline or user ID.")
    summary: text(description="Task summary.")
    item: optional(keyword(), description="Associated case item id.")


@register_model(
    index=True, store=True, description="Enrichment annotations associated with a case item id.", embedded=True
)
class CaseEnrichment(HowlerEmbeddedModel):
    """Enrichment annotations associated with a case item id."""

    item: keyword(description="Case item id associated with these annotations.")
    annotations: list_field(keyword(), default=[], description="Annotation IDs associated with the case item id.")


@register_model(index=True, store=True, description="Case model with items, enrichments, rules, and tasks.")
class Case(HowlerESModel):
    """Case model with items, enrichments, rules, and tasks."""

    case_id: uuid(description="A unique identifier for this case.")
    classification: classification(
        is_user_classification=False,
        copyto="__text__",
        default=CLASSIFICATION.UNRESTRICTED,
        description="Maximum classification for the case",
    )
    title: text(description="Case title.")
    summary: text(description="Short case summary.")
    overview: optional(text(), description="Markdown overview of the case.")
    escalation: enum(values=CaseEscalation, default=CaseEscalation.NORMAL, description="Escalation of the case.")
    status: enum(values=Status, default=Status.OPEN, description="Status of the case.")
    created: optional(date(), default="NOW", description="Date/time when the case was created.")
    visible: boolean(default=True, description="Whether the case is visible/accessible in the frontend.")
    updated: optional(date(), default=None, description="Date/time when the case was last updated.")
    start: optional(date(), default=None, description="Date/time when telemetry/alerts in this case started.")
    end: optional(date(), default=None, description="Date/time when telemetry/alerts in this case ended.")
    targets: optional(list_field(keyword()), default=[], description="A list of target entities related to this case.")
    threats: optional(
        list_field(keyword()),
        default=[],
        description="A list of known or suspected threat entities related to this case.",
    )
    indicators: optional(list_field(keyword()), default=[], description="A list of indicators relevant to this case.")
    participants: optional(list_field(keyword()), default=[], description="A list of users participating in this case.")
    items: optional(
        list_field(compound(CaseItem)),
        default=[],
        description="Path-scoped case items referencing external object IDs or links.",
    )
    enrichments: optional(
        list_field(compound(CaseEnrichment)), default=[], description="Path-scoped enrichment annotations."
    )
    rules: optional(
        list_field(compound(CaseRule)), default=[], description="Rules for routing matched data into case paths."
    )
    tasks: optional(list_field(compound(CaseTask)), default=[], description="Tasks associated with this case.")
    log: optional(
        list_field(compound(CaseLog)),
        default=[],
        description="A list of changes to the case with timestamps and attribution.",
    )

    def as_primitives(self, **kwargs: Any) -> dict[str, Any]:
        """Add the ``__index`` field expected by legacy consumers.

        Uses an explicit base-class call instead of ``super()`` because the DSL/Pydantic
        metaclass rebuilds ``HowlerESModel`` subclasses, which breaks the zero-arg ``super()``
        ``__class__`` cell.
        """
        result = HowlerModelMixin.as_primitives(self, **kwargs)
        result["__index"] = type(self).__name__.lower()
        return result
