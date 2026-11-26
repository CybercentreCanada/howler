"""ECS observer field set."""

from __future__ import annotations

from typing import Annotated

from howler.models import IP, HowlerEmbeddedModel, Keyword, metadata, register_model
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
    hostname: Keyword | None = None
    """Hostname of the observer"""
    ingress: Ingress | None = None
    """Holds information like interface number, name, vlan, and zone to classify ingress traffic"""
    interface: Interface | None = None
    """Interface being observed"""
    ip: Annotated[list[IP], metadata(default=[])]
    """IP addresses of the observer."""
    mac: list[Keyword] = []
    """Mac addresses of the observer."""
    name: Keyword | None = None
    """Custom name of the observer"""
    product: Keyword | None = None
    """Product name of the observer"""
    serial_number: Keyword | None = None
    """Observer serial number"""
    type: Keyword | None = None
    """Type of the observer the data is coming from"""
    vendor: Keyword | None = None
    """Vendor name of the observer"""
    version: Keyword | None = None
    """Observer version"""
