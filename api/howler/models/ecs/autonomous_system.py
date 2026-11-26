"""ECS autonomous system field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, Integer, Keyword, register_model


@register_model(
    index=True,
    store=True,
    description=(
        "Observer is defined as a special network, security, or application device used to detect, observe, "
        "or create network, sercurity, or application event metrics"
    ),
    embedded=True,
)
class AS(HowlerEmbeddedModel):
    """Fields describing an autonomous system (Internet routing prefix)."""

    number: Integer | None = None
    """Unique number allocated to the autonomous system"""
    organization_name: Keyword | None = None
    """Organization name"""
