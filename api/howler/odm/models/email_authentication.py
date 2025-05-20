from typing import Optional

from howler import odm


@odm.model(
    index=True,
    store=True,
    description="Email authentication results for NEIGHBOURHOODWATCH",
)
class EmailAuthentication(odm.Model):
    dmarc: Optional[str] = odm.Keyword(description="List of DMARC records", optional=True)
    dkim: Optional[str] = odm.Keyword(description="List of DKIM records", optional=True)
    spf: Optional[str] = odm.Keyword(description="List of SPF records", optional=True)
