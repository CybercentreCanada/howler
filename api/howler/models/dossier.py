"""Dossier model."""

from __future__ import annotations

from pydantic import Field

from howler.models import UUID, CaseInsensitiveKeyword, HowlerESModel, enum, register_model
from howler.models.lead import Lead
from howler.models.ownership import Ownership
from howler.models.pivot import Pivot
from howler.utils.uid import get_random_id


@register_model(
    index=True,
    store=True,
    description="The dossier object stores individual tabs/fields for a given alert.",
)
class Dossier(Ownership, HowlerESModel):
    """The dossier object stores individual tabs/fields for a given alert."""

    dossier_id: UUID = Field(default_factory=get_random_id)
    """A UUID for this dossier."""
    leads: list[Lead] = []
    """A list of the leads to show when the query matches the given alert."""
    pivots: list[Pivot] = []
    """A list of the pivots to show when the query matches the given alert."""
    title: CaseInsensitiveKeyword
    """The title of this dossier."""
    query: CaseInsensitiveKeyword | None = None
    """The query that controls when this dossier should be shown in the UI."""
    type: enum(values=["personal", "global"])
    """The type of dossier - personal or global."""
