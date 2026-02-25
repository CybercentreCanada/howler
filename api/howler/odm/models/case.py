from enum import StrEnum
from typing import Optional

from howler import odm
from howler.common.exceptions import HowlerValueError

CASE_ITEM_TYPES = {"observable", "hit", "case", "lead", "reference"}


class CaseItemTypes(StrEnum):
    """Enumeration of valid case item types.

    Case items represent different types of objects that can be associated with a case.
    Each item type corresponds to a specific kind of entity or reference that provides
    context, evidence, or relationships for the case investigation.

    Attributes:
        OBSERVABLE: A suspicious or noteworthy observable (IP, domain, hash, etc.) that
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
    """
    OBSERVABLE = "observable"
    HIT = "hit"
    TABLE = "table"
    CASE = "case"
    LEAD = "lead"
    REFERENCE = "reference"


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


@odm.model(index=True, store=True, description="A path-scoped item included in a case.")
class CaseItem(odm.Model):
    path: str = odm.Keyword(description="Path of the item in the case hierarchy.")
    type: str = odm.Enum(values=CaseItemTypes, description="Type of case item.")
    id: Optional[str] = odm.Optional(
        odm.Keyword(description="Identifier for the backing object when available."),
        default=None,
    )
    value: str = odm.Keyword(description="String reference value for the item (ID, URL, or token).")
    visible: bool = odm.Boolean(default=True, description="Whether the item is visible/accessible in the frontend.")


@odm.model(index=True, store=True, description="Rule used to place/query data into case paths.")
class CaseRule(odm.Model):
    destination: str = odm.Keyword(description="Destination case path template.")
    query: str = odm.Keyword(description="Lucene query used by this rule.")


@odm.model(index=True, store=True, description="Task associated with a case item path.")
class CaseTask(odm.Model):
    id: str = odm.UUID(description="Task identifier.")
    complete: bool = odm.Boolean(default=False, description="Whether the task is complete.")
    assignment: str = odm.Keyword(description="Assigned discipline or user ID.")
    summary: str = odm.Text(description="Task summary.")
    path: str = odm.Keyword(description="Associated case item path.")


@odm.model(index=True, store=True, description="Enrichment annotations associated with a case path.")
class CaseEnrichment(odm.Model):
    path: str = odm.Keyword(description="Case item path associated with these annotations.")
    annotations: list[str] = odm.List(
        odm.Keyword(),
        default=[],
        description="Annotation IDs associated with the path.",
    )


@odm.model(index=True, store=True, description="Case model with path-based items, enrichments, rules, and tasks.")
class Case(odm.Model):
    case_id: str = odm.Keyword(description="A unique identifier for this case.")
    title: str = odm.Keyword(description="Case title.")
    summary: str = odm.Text(description="Short case summary.")
    overview: str = odm.Optional(odm.Text(description="Markdown overview of the case."))
    escalation: str = odm.Optional(odm.Keyword(description="Escalation of the case."))
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
