"""Sentinel Pydantic model: metadata relating to Microsoft Sentinel.

Mirrors the stored Sentinel fields using the ``howler.models`` Pydantic/DSL foundation.
"""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, Keyword, register_model


@register_model(index=True, store=True, description="The Sentinel fields contain any data relating to Sentinel.")
class Sentinel(HowlerEmbeddedModel):
    """The Sentinel fields contain any data relating to Sentinel."""

    id: Keyword | None = None
    """The Microsoft Sentinel incident or alert identifier."""
    tenant_id: Keyword | None = None
    """The tenant identifier that owns this Sentinel record."""
    record_type: Keyword | None = None
    """The Sentinel record kind: incident, alert, or evidence."""
    incident_id: Keyword | None = None
    """The parent Microsoft Sentinel incident identifier."""
    alert_id: Keyword | None = None
    """The source Microsoft Sentinel alert identifier for this alert or evidence record."""
    evidence_id: Keyword | None = None
    """A stable key identifying a Sentinel evidence object within its source alert."""
