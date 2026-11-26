"""Record outline header model."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, keyword, list_field, register_model


@register_model(index=True, store=True, description="Record outline header.", embedded=True)
class Header(HowlerEmbeddedModel):
    """Record outline header."""

    threat: keyword(optional=True, description="The threat of the record.")
    target: keyword(optional=True, description="The target of the record.")
    indicators: list_field(
        keyword(description="Indicators of the record."),
        default=[],
        description="Indicators of the record.",
    )
    summary: keyword(optional=True, description="Summary of the record.")
