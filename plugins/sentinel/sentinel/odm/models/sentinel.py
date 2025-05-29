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
        description="The sentinel alert url for a staged alert.",
    )
