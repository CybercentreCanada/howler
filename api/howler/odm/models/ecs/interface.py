from typing import Optional

from howler import odm


@odm.model(
    index=True,
    store=True,
    description=(
        "The interface fields are used to record ingress and egress interface information when reported by "
        "an observer (e.g. firewall, router, load balancer) in the context of the observer handling a network "
        "connection."
    ),
)
class Interface(odm.Model):
    id: Optional[int] = odm.Integer(
        description="Interface ID as reported by an observer (typically SNMP interface ID).", optional=True
    )
    name: Optional[str] = odm.Optional(
        odm.Keyword(description="Name of interface"),
    )
