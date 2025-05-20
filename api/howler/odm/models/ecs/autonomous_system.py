from typing import Optional

from howler import odm


@odm.model(
    index=True,
    store=True,
    description=(
        "Observer is defined as a special network, security, or application device used to detect, observe, "
        "or create network, sercurity, or application event metrics"
    ),
)
class AS(odm.Model):
    number: Optional[int] = odm.Optional(odm.Integer(description="Unique number allocated to the autonomous system"))
    organization_name: Optional[str] = odm.Optional(odm.Keyword(description="Organization name"))
