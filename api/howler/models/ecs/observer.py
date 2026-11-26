"""ECS observer field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, ip, keyword, list_field, register_model
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

    egress: Egress | None = None
    """Holds information like interface number, name, vlan, and zone to classify ingress traffic"""
    hostname: keyword(optional=True)
    """Hostname of the observer"""
    ingress: Ingress | None = None
    """Holds information like interface number, name, vlan, and zone to classify ingress traffic"""
    interface: Interface | None = None
    """Interface being observed"""
    ip: list_field(ip(), default=[])
    """IP addresses of the observer."""
    mac: list_field(keyword(), default=[])
    """Mac addresses of the observer."""
    name: keyword(optional=True)
    """Custom name of the observer"""
    product: keyword(optional=True)
    """Product name of the observer"""
    serial_number: keyword(optional=True)
    """Observer serial number"""
    type: keyword(optional=True)
    """Type of the observer the data is coming from"""
    vendor: keyword(optional=True)
    """Vendor name of the observer"""
    version: keyword(optional=True)
    """Observer version"""
