"""View model."""

from __future__ import annotations

from typing import Annotated

from howler.models import (
    HowlerEmbeddedModel,
    HowlerESModel,
    boolean,
    case_insensitive_keyword,
    enum,
    integer,
    keyword,
    metadata,
    register_model,
    uuid,
)
from howler.models.ownership import Ownership

DEFAULT_INDEXES = ["hit"]


@register_model(
    index=True, store=True, description="The field and width of a column to display in a grid view.", embedded=True
)
class GridColumn(HowlerEmbeddedModel):
    """The field and width of a column to display in a grid view."""

    field: keyword()
    """The field key for this column."""
    width: integer(optional=True)
    """The width of this column in pixels."""


@register_model(index=True, store=True, description="Additional View Settings", embedded=True)
class Settings(HowlerEmbeddedModel):
    """Additional View Settings."""

    advance_on_triage: boolean(default=False)
    """Should the user advance to the next alert when triage is complete?"""
    display: enum(values=["list", "grid"], optional=True)
    """The layout to use when opening this view"""
    columns: list[Annotated[GridColumn, metadata(description="The columns to display in this view.")]] | None = None


@register_model(index=True, store=True, description="Model of views")
class View(Ownership, HowlerESModel):
    """Model of views."""

    view_id: uuid()
    """A UUID for this view"""
    indexes: list[keyword()] = DEFAULT_INDEXES
    """What indexes this view applies to."""
    title: case_insensitive_keyword()
    """The name of this view."""
    query: case_insensitive_keyword()
    """The query to run in this view."""
    sort: case_insensitive_keyword(optional=True)
    """The sorting to use with this view."""
    span: keyword(optional=True)
    """The time span to use by default when opening this view"""
    type: enum(values=["personal", "global", "readonly"])
    """The type of view"""
    settings: Annotated[Settings, metadata(default={"advance_on_triage": False})]
    """Additional View Settings"""
