"""Sentinel Pydantic model: metadata relating to Microsoft Sentinel.

Mirrors the stored Sentinel fields using the ``howler.models`` Pydantic/DSL foundation.
"""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, keyword, optional, register_model


@register_model(index=True, store=True, description="The Sentinel fields contain any data relating to Sentinel.")
class Sentinel(HowlerEmbeddedModel):
    """The Sentinel fields contain any data relating to Sentinel."""

    id: optional(keyword(), description="The Microsoft Sentinel incident or alert identifier.")
    tenant_id: optional(keyword(), description="The tenant identifier that owns this Sentinel record.")
    record_type: optional(keyword(), description="The Sentinel record kind: incident, alert, or evidence.")
    incident_id: optional(keyword(), description="The parent Microsoft Sentinel incident identifier.")
    alert_id: optional(
        keyword(),
        description="The source Microsoft Sentinel alert identifier for this alert or evidence record.",
    )
    evidence_id: optional(
        keyword(),
        description="A stable key identifying a Sentinel evidence object within its source alert.",
    )
