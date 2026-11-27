"""ECS ingress field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, Keyword, register_model
from howler.models.ecs.interface import Interface


@register_model(
    index=True,
    store=True,
    description="Holds information like interface number, name, vlan, and zone to classify ingress traffic",
    embedded=True,
)
class Ingress(HowlerEmbeddedModel):
    """Holds information like interface number, name, vlan, and zone to classify ingress traffic."""

    zone: Keyword | None = None
    """Network zone of incoming traffic as reported by observer"""
    interface: Interface | None = None
    """Ingress Interface"""
