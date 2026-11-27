"""Overview model."""

from __future__ import annotations

from pydantic import Field

from howler.models import UUID, CaseInsensitiveKeyword, HowlerESModel, Keyword, Text, register_model
from howler.utils.uid import get_random_id


@register_model(index=True, store=True, description="Model of overviews")
class Overview(HowlerESModel):
    """Model of overviews."""

    overview_id: UUID = Field(default_factory=get_random_id)
    """A UUID for this overview"""
    analytic: CaseInsensitiveKeyword
    """The analytic which this overview applies to."""
    detection: CaseInsensitiveKeyword | None = None
    """The detection which this overview applies to."""
    owner: Keyword | None = None
    """The person to whom this overview belongs."""
    content: Text
    """The markdown to show when this overview is used."""
