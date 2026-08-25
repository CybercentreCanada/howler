"""ECS observer field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, compound, ip, keyword, list_field, optional, register_model
from howler.models.ecs.egress import Egress
from howler.models.ecs.ingress import Ingress
from howler.models.ecs.interface import Interface


@register_model(
    index=True,
    store=True,
    description=(
        "Observer is defined as a special network, security, or application device used to detect, observe, "
        "or create network, sercurity, or application event metrics"
    ),
    embedded=True,
)
class Observer(HowlerEmbeddedModel):
    """A special network, security, or application device used to detect, observe, or create metrics."""

    egress: optional(
        compound(Egress),
        description="Holds information like interface number, name, vlan, and zone to classify ingress traffic",
    )
    hostname: optional(keyword(), description="Hostname of the observer")
    ingress: optional(
        compound(Ingress),
        description="Holds information like interface number, name, vlan, and zone to classify ingress traffic",
    )
    interface: optional(compound(Interface), description="Interface being observed")
    ip: list_field(ip(), default=[], description="IP addresses of the observer.")
    mac: list_field(keyword(), default=[], description="Mac addresses of the observer.")
    name: optional(keyword(), description="Custom name of the observer")
    product: optional(keyword(), description="Product name of the observer")
    serial_number: optional(keyword(), description="Observer serial number")
    type: optional(keyword(), description="Type of the observer the data is coming from")
    vendor: optional(keyword(), description="Vendor name of the observer")
    version: optional(keyword(), description="Observer version")
