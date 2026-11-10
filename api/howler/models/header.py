"""Record outline header model."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, keyword, list_field, optional, register_model


@register_model(index=True, store=True, description="Record outline header.", embedded=True)
class Header(HowlerEmbeddedModel):
    """Record outline header."""

    threat: optional(keyword(), description="The threat of the record.")
    target: optional(keyword(), description="The target of the record.")
    indicators: list_field(
        keyword(description="Indicators of the record."),
        default=[],
        description="Indicators of the record.",
    )
    summary: optional(keyword(), description="Summary of the record.")
