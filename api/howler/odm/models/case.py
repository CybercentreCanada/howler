from typing import Optional

from howler import odm

CASE_ITEM_TYPES = {"observable", "table", "case", "lead", "reference"}


@odm.model(index=False, store=True, description="Core metadata for a case.")
class CaseData(odm.Model):
    id: str = odm.Keyword(description="A unique identifier for this case.")
    title: str = odm.Keyword(description="Case title.")
    summary: str = odm.Text(description="Short case summary.")
    overview: str = odm.Text(description="Markdown overview of the case.")
    targets: list[str] = odm.List(
        odm.Keyword(),
        default=[],
        description="A list of target entities related to this case.",
    )
    threats: list[str] = odm.List(
        odm.Keyword(),
        default=[],
        description="A list of known or suspected threat entities related to this case.",
    )
    indicators: list[str] = odm.List(
        odm.Keyword(),
        default=[],
        description="A list of indicators relevant to this case.",
    )
    participants: list[str] = odm.List(
        odm.Keyword(),
        default=[],
        description="A list of users participating in this case.",
    )


@odm.model(index=False, store=True, description="A path-scoped item included in a case.")
class CaseItem(odm.Model):
    path: str = odm.Keyword(description="Path of the item in the case hierarchy.")
    type: str = odm.Enum(values=CASE_ITEM_TYPES, description="Type of case item.")
    id: Optional[str] = odm.Optional(
        odm.Keyword(description="Identifier for the backing object when available."),
        default=None,
    )
    value: str = odm.Keyword(description="String reference value for the item (ID, URL, or token).")


@odm.model(index=False, store=True, description="Rule used to place/query data into case paths.")
class CaseRule(odm.Model):
    destination: str = odm.Keyword(description="Destination case path template.")
    query: str = odm.Keyword(description="Lucene query used by this rule.")


@odm.model(index=False, store=True, description="Task associated with a case item path.")
class CaseTask(odm.Model):
    id: str = odm.Keyword(description="Task identifier.")
    complete: bool = odm.Boolean(default=False, description="Whether the task is complete.")
    assignment: str = odm.Keyword(description="Assigned discipline or user ID.")
    summary: str = odm.Text(description="Task summary.")
    path: str = odm.Keyword(description="Associated case item path.")


@odm.model(index=False, store=True, description="Enrichment annotations associated with a case path.")
class CaseEnrichment(odm.Model):
    path: str = odm.Keyword(description="Case item path associated with these annotations.")
    annotations: list[str] = odm.List(
        odm.Keyword(),
        default=[],
        description="Annotation IDs associated with the path.",
    )


@odm.model(index=True, store=True, description="Case model with path-based items, enrichments, rules, and tasks.")
class Case(odm.Model):
    case: CaseData = odm.Compound(CaseData, description="Core case metadata.")
    items: list[CaseItem] = odm.List(
        odm.Compound(CaseItem),
        default=[],
        description="Path-scoped case items referencing external object IDs or links.",
    )
    enrichments: list[CaseEnrichment] = odm.List(
        odm.Compound(CaseEnrichment),
        default=[],
        description="Path-scoped enrichment annotations.",
    )
    rules: list[CaseRule] = odm.List(
        odm.Compound(CaseRule),
        default=[],
        description="Rules for routing matched data into case paths.",
    )
    tasks: list[CaseTask] = odm.List(
        odm.Compound(CaseTask),
        default=[],
        description="Tasks associated with this case.",
    )
