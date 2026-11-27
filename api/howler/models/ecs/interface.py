"""ECS interface field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, Integer, Keyword, register_model


@register_model(
    index=True,
    store=True,
    description=(
        "The interface fields are used to record ingress and egress interface information when reported by "
        "an observer (e.g. firewall, router, load balancer) in the context of the observer handling a network "
        "connection."
    ),
    embedded=True,
)
class Interface(HowlerEmbeddedModel):
    """Interface fields record ingress and egress interface information reported by an observer."""

    id: Integer | None = None
    """Interface ID as reported by an observer (typically SNMP interface ID)."""
    name: Keyword | None = None
    """Name of interface"""
