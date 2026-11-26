"""ECS observer field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, compound, ip, keyword, list_field, register_model
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

    egress: compound(
        Egress,
        optional=True,
        description="Holds information like interface number, name, vlan, and zone to classify ingress traffic",
    )
    hostname: keyword(optional=True, description="Hostname of the observer")
    ingress: compound(
        Ingress,
        optional=True,
        description="Holds information like interface number, name, vlan, and zone to classify ingress traffic",
    )
    interface: compound(Interface, optional=True, description="Interface being observed")
    ip: list_field(ip(), default=[], description="IP addresses of the observer.")
    mac: list_field(keyword(), default=[], description="Mac addresses of the observer.")
    name: keyword(optional=True, description="Custom name of the observer")
    product: keyword(optional=True, description="Product name of the observer")
    serial_number: keyword(optional=True, description="Observer serial number")
    type: keyword(optional=True, description="Type of the observer the data is coming from")
    vendor: keyword(optional=True, description="Vendor name of the observer")
    version: keyword(optional=True, description="Observer version")
