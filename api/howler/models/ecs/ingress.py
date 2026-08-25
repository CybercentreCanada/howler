"""ECS ingress field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, compound, keyword, optional, register_model
from howler.models.ecs.interface import Interface


@register_model(
    index=True,
    store=True,
    description="Holds information like interface number, name, vlan, and zone to classify ingress traffic",
    embedded=True,
)
class Ingress(HowlerEmbeddedModel):
    """Holds information like interface number, name, vlan, and zone to classify ingress traffic."""

    zone: optional(keyword(), description="Network zone of incoming traffic as reported by observer")
    interface: optional(compound(Interface), description="Ingress Interface")
