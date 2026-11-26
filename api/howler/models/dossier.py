"""Dossier model."""

from __future__ import annotations

from howler.models import HowlerESModel, case_insensitive_keyword, enum, list_field, register_model, uuid
from howler.models.lead import Lead
from howler.models.ownership import Ownership
from howler.models.pivot import Pivot


@register_model(
    index=True,
    store=True,
    description="The dossier object stores individual tabs/fields for a given alert.",
)
class Dossier(Ownership, HowlerESModel):
    """The dossier object stores individual tabs/fields for a given alert."""

    dossier_id: uuid()
    """A UUID for this dossier."""
    leads: list_field(Lead, default=[])
    """A list of the leads to show when the query matches the given alert."""
    pivots: list_field(Pivot, default=[])
    """A list of the pivots to show when the query matches the given alert."""
    title: case_insensitive_keyword()
    """The title of this dossier."""
    query: case_insensitive_keyword(optional=True, default=None)
    """The query that controls when this dossier should be shown in the UI."""
    type: enum(values=["personal", "global"])
    """The type of dossier - personal or global."""
