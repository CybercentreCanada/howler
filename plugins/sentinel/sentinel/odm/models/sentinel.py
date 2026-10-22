from typing import Optional

from howler import odm


@odm.model(
    index=True,
    store=True,
    description="The Sentinel fields contain any data relating to Sentinel.",
)
class Sentinel(odm.Model):
    id: Optional[str] = odm.Keyword(
        optional=True,
        description="The Microsoft Sentinel incident or alert identifier.",
    )
    tenant_id: Optional[str] = odm.Keyword(
        optional=True,
        description="The tenant identifier that owns this Sentinel record.",
    )
    record_type: Optional[str] = odm.Keyword(
        optional=True,
        description="The Sentinel record kind: incident, alert, or evidence.",
    )
    incident_id: Optional[str] = odm.Keyword(
        optional=True,
        description="The parent Microsoft Sentinel incident identifier.",
    )
    alert_id: Optional[str] = odm.Keyword(
        optional=True,
        description="The source Microsoft Sentinel alert identifier for this alert or evidence record.",
    )
    evidence_id: Optional[str] = odm.Keyword(
        optional=True,
        description="A stable key identifying a Sentinel evidence object within its source alert.",
    )
