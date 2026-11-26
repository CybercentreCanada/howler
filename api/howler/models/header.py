"""Record outline header model."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, Keyword, register_model


@register_model(index=True, store=True, description="Record outline header.", embedded=True)
class Header(HowlerEmbeddedModel):
    """Record outline header."""

    threat: Keyword | None = None
    """The threat of the record."""
    target: Keyword | None = None
    """The target of the record."""
    indicators: list[Keyword] = []
    """Indicators of the record."""
    summary: Keyword | None = None
    """Summary of the record."""
