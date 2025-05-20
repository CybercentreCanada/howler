from typing import Optional

from howler import odm


@odm.model(
    index=True,
    store=True,
    description="Subtype of NEIGHBOURHOODWATCH domains",
)
class DomainsBySubtype(odm.Model):
    emails: Optional[list[str]] = odm.Optional(
        odm.List(
            odm.Text(description="List of email domains"),
        )
    )
    links: Optional[list[str]] = odm.Optional(
        odm.List(
            odm.Text(description="List of link related domains"),
        )
    )
    other: Optional[list[str]] = odm.Optional(
        odm.List(
            odm.Text(description="List of uncategorized domains"),
        )
    )
