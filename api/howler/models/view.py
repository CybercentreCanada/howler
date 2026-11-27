"""View model."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from howler.models import (
    UUID,
    Boolean,
    CaseInsensitiveKeyword,
    HowlerEmbeddedModel,
    HowlerESModel,
    Integer,
    Keyword,
    enum,
    metadata,
    register_model,
)
from howler.models.ownership import Ownership
from howler.utils.uid import get_random_id

DEFAULT_INDEXES = ["hit"]


@register_model(
    index=True, store=True, description="The field and width of a column to display in a grid view.", embedded=True
)
class GridColumn(HowlerEmbeddedModel):
    """The field and width of a column to display in a grid view."""

    field: Keyword
    """The field key for this column."""
    width: Integer | None = None
    """The width of this column in pixels."""


@register_model(index=True, store=True, description="Additional View Settings", embedded=True)
class Settings(HowlerEmbeddedModel):
    """Additional View Settings."""

    advance_on_triage: Boolean = False
    """Should the user advance to the next alert when triage is complete?"""
    display: enum(values=["list", "grid"], optional=True)
    """The layout to use when opening this view"""
    columns: list[Annotated[GridColumn, metadata(description="The columns to display in this view.")]] | None = None


@register_model(index=True, store=True, description="Model of views")
class View(Ownership, HowlerESModel):
    """Model of views."""

    view_id: UUID = Field(default_factory=get_random_id)
    """A UUID for this view"""
    indexes: list[Keyword] = DEFAULT_INDEXES
    """What indexes this view applies to."""
    title: CaseInsensitiveKeyword
    """The name of this view."""
    query: CaseInsensitiveKeyword
    """The query to run in this view."""
    sort: CaseInsensitiveKeyword | None = None
    """The sorting to use with this view."""
    span: Keyword | None = None
    """The time span to use by default when opening this view"""
    type: enum(values=["personal", "global", "readonly"])
    """The type of view"""
    settings: Annotated[Settings, metadata(default={"advance_on_triage": False})]
    """Additional View Settings"""
