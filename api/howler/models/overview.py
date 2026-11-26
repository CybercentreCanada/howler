"""Overview model."""

from __future__ import annotations

from howler.models import UUID, CaseInsensitiveKeyword, HowlerESModel, Keyword, Text, register_model


@register_model(index=True, store=True, description="Model of overviews")
class Overview(HowlerESModel):
    """Model of overviews."""

    overview_id: UUID
    """A UUID for this overview"""
    analytic: CaseInsensitiveKeyword
    """The analytic which this overview applies to."""
    detection: CaseInsensitiveKeyword | None = None
    """The detection which this overview applies to."""
    owner: Keyword | None = None
    """The person to whom this overview belongs."""
    content: Text
    """The markdown to show when this overview is used."""
