"""Record outline header model."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, keyword, register_model


@register_model(index=True, store=True, description="Record outline header.", embedded=True)
class Header(HowlerEmbeddedModel):
    """Record outline header."""

    threat: keyword(optional=True)
    """The threat of the record."""
    target: keyword(optional=True)
    """The target of the record."""
    indicators: list[keyword(description="Indicators of the record.")] = []
    """Indicators of the record."""
    summary: keyword(optional=True)
    """Summary of the record."""
