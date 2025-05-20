from typing import Optional

from howler import odm


@odm.model(
    index=True,
    store=True,
    description=("A host is defined as a general computing instance."),
)
class Host(odm.Model):
    id: Optional[str] = odm.Optional(odm.Keyword(description="Unique host id. Use Agent ID for HBS."))
    ip: list[str] = odm.List(odm.IP(), default=[], description="Host ip addresses.")
    mac: list[str] = odm.List(odm.Keyword(), default=[], description="Host MAC addresses.")
    name: Optional[str] = odm.Optional(odm.Keyword(description="Name of the host."))
    domain: Optional[str] = odm.Optional(odm.Keyword(description="Domain the host is a member of."))
    type: Optional[str] = odm.Optional(odm.Keyword(description="As described by CSP."))
