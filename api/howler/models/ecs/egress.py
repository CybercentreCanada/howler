"""ECS egress field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, keyword, optional, register_model


@register_model(
    index=True,
    store=True,
    description="Holds information like interface number, name, vlan, and zone to classify egress traffic",
    embedded=True,
)
class Egress(HowlerEmbeddedModel):
    """Holds information like interface number, name, vlan, and zone to classify egress traffic."""

    zone: optional(keyword(), description="Network zone of outbound traffic")
