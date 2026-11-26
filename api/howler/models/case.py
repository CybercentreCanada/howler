"""Case model."""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import model_validator

from howler.config import CLASSIFICATION
from howler.models import (
    UUID,
    Boolean,
    Classification,
    Date,
    HowlerEmbeddedModel,
    HowlerESModel,
    Integer,
    Keyword,
    Text,
    enum,
    metadata,
    register_model,
)
from howler.models.constants import CaseEscalation, HowlerStrEnum, Status


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

    timestamp: Date
    """Timestamp at which the Log event took place."""
    key: Keyword | None = None
    """The key whose value changed."""
    previous_value: Keyword | None = None
    """The value the key is changing from."""
    new_value: Keyword | None = None
    """The value the key is changing to."""
    user: Keyword
    """User ID who created the log event."""
    explanation: Text | None = None
    """A manual description of the changes made."""

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

    id: UUID
    """Unique identifier for this item."""
    parent: Keyword | None = None
    """ID of the parent folder item, or null for root-level items."""
    name: Text | None = None
    """Display name for the item. Optional; the UI falls back to value when absent."""
    type: enum(values=CaseItemTypes)
    """Type of case item."""
    value: Text
    """String reference value for the item (ID, URL, or token), or markdown."""
    visible: Boolean = True
    """Whether the item is visible/accessible in the frontend."""
    classification: Annotated[
        Classification | None,
        metadata(copyto="__text__", optional=True, default=CLASSIFICATION.UNRESTRICTED),
    ]
    """Classification of the related record. Automatically populated for hit and event items."""

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

    rule_id: UUID
    """Unique rule identifier."""
    destination: Keyword
    """Destination case path template."""
    query: Keyword
    """Lucene query used by this rule."""
    author: Keyword
    """Username who created the rule."""
    enabled: Boolean = True
    """Whether the rule is currently active."""
    created_at: Annotated[Date, metadata(default="NOW")]
    """Timestamp when the rule was created."""
    timeframe: Annotated[Integer | None, metadata(ge=1)] = None
    """Number of days the rule stays active. Null means no expiry."""
    expire_after_resolved: Boolean = False
    """When true, the timeframe countdown starts from the case's last resolution time instead of from rule creation."""
    indexes: list[enum(values=RuleIndexTypes)] = [RuleIndexTypes.HIT.value]
    """Indexes to run this rule against (hit, event, or both)."""

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

    id: UUID
    """Task identifier."""
    complete: Boolean = False
    """Whether the task is complete."""
    assignment: Keyword | None = None
    """Assigned discipline or user ID."""
    summary: Text
    """Task summary."""
    item: Keyword | None = None
    """Associated case item id."""


@register_model(
    index=True, store=True, description="Enrichment annotations associated with a case item id.", embedded=True
)
class CaseEnrichment(HowlerEmbeddedModel):
    """Enrichment annotations associated with a case item id."""

    item: Keyword
    """Case item id associated with these annotations."""
    annotations: list[Keyword] = []
    """Annotation IDs associated with the case item id."""


@register_model(index=True, store=True, description="Case model with items, enrichments, rules, and tasks.")
class Case(HowlerESModel):
    """Case model with items, enrichments, rules, and tasks."""

    _include_index = True

    case_id: UUID
    """A unique identifier for this case."""
    classification: Annotated[Classification, metadata(copyto="__text__", default=CLASSIFICATION.UNRESTRICTED)]
    """Maximum classification for the case"""
    title: Text
    """Case title."""
    summary: Text
    """Short case summary."""
    overview: Text | None = None
    """Markdown overview of the case."""
    escalation: enum(values=CaseEscalation, default=CaseEscalation.NORMAL)
    """Escalation of the case."""
    status: enum(values=Status, default=Status.OPEN)
    """Status of the case."""
    created: Annotated[Date | None, metadata(optional=True, default="NOW")]
    """Date/time when the case was created."""
    visible: Boolean = True
    """Whether the case is visible/accessible in the frontend."""
    updated: Date | None = None
    """Date/time when the case was last updated."""
    start: Date | None = None
    """Date/time when telemetry/alerts in this case started."""
    end: Date | None = None
    """Date/time when telemetry/alerts in this case ended."""
    targets: Annotated[list[Keyword] | None, metadata(optional=True)] = []
    """A list of target entities related to this case."""
    threats: Annotated[list[Keyword] | None, metadata(optional=True)] = []
    """A list of known or suspected threat entities related to this case."""
    indicators: Annotated[list[Keyword] | None, metadata(optional=True)] = []
    """A list of indicators relevant to this case."""
    participants: Annotated[list[Keyword] | None, metadata(optional=True)] = []
    """A list of users participating in this case."""
    items: Annotated[list[CaseItem] | None, metadata(optional=True)] = []
    """Path-scoped case items referencing external object IDs or links."""
    enrichments: Annotated[list[CaseEnrichment] | None, metadata(optional=True)] = []
    """Path-scoped enrichment annotations."""
    rules: Annotated[list[CaseRule] | None, metadata(optional=True)] = []
    """Rules for routing matched data into case paths."""
    tasks: Annotated[list[CaseTask] | None, metadata(optional=True)] = []
    """Tasks associated with this case."""
    log: Annotated[list[CaseLog] | None, metadata(optional=True)] = []
    """A list of changes to the case with timestamps and attribution."""
