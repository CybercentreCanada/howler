"""View model."""

from __future__ import annotations

from howler.models import (
    HowlerEmbeddedModel,
    HowlerESModel,
    boolean,
    case_insensitive_keyword,
    compound,
    enum,
    integer,
    keyword,
    list_field,
    optional,
    register_model,
    uuid,
)

DEFAULT_INDEXES = ["hit"]


@register_model(
    index=True, store=True, description="The field and width of a column to display in a grid view.", embedded=True
)
class GridColumn(HowlerEmbeddedModel):
    """The field and width of a column to display in a grid view."""

    field: keyword(description="The field key for this column.")
    width: optional(integer(), description="The width of this column in pixels.")


@register_model(index=True, store=True, description="Additional View Settings", embedded=True)
class Settings(HowlerEmbeddedModel):
    """Additional View Settings."""

    advance_on_triage: boolean(
        default=False, description="Should the user advance to the next alert when triage is complete?"
    )
    display: optional(enum(values=["list", "grid"]), description="The layout to use when opening this view")
    columns: optional(list_field(compound(GridColumn, description="The columns to display in this view.")))


@register_model(index=True, store=True, description="Model of views")
class View(HowlerESModel):
    """Model of views."""

    view_id: uuid(description="A UUID for this view")
    indexes: list_field(keyword(), default=DEFAULT_INDEXES, description="What indexes this view applies to.")
    title: case_insensitive_keyword(description="The name of this view.")
    query: keyword(description="The query to run in this view.")
    sort: optional(keyword(), description="The sorting to use with this view.")
    span: optional(keyword(), description="The time span to use by default when opening this view")
    type: enum(values=["personal", "global", "readonly"], description="The type of view")
    owner: optional(keyword(), description="The person to whom this view belongs.")
    settings: compound(Settings, default={"advance_on_triage": False}, description="Additional View Settings")
