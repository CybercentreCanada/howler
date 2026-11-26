"""Overview model."""

from __future__ import annotations

from howler.models import HowlerESModel, case_insensitive_keyword, keyword, register_model, text, uuid


@register_model(index=True, store=True, description="Model of overviews")
class Overview(HowlerESModel):
    """Model of overviews."""

    overview_id: uuid()
    """A UUID for this overview"""
    analytic: case_insensitive_keyword()
    """The analytic which this overview applies to."""
    detection: case_insensitive_keyword(optional=True)
    """The detection which this overview applies to."""
    owner: keyword(optional=True)
    """The person to whom this overview belongs."""
    content: text()
    """The markdown to show when this overview is used."""
