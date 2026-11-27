"""Template model."""

from __future__ import annotations

from pydantic import Field

from howler.models import UUID, CaseInsensitiveKeyword, HowlerESModel, Keyword, enum, register_model
from howler.utils.uid import get_random_id


@register_model(index=True, store=True, description="Model of templates")
class Template(HowlerESModel):
    """Model of templates."""

    template_id: UUID = Field(default_factory=get_random_id)
    """A UUID for this template"""
    analytic: CaseInsensitiveKeyword
    """The analytic which this template applies to."""
    detection: CaseInsensitiveKeyword | None = None
    """The detection which this template applies to."""
    type: enum(values=["personal", "global"])
    """The type of template - personal or global?"""
    owner: Keyword | None = None
    """The person to whom this template belongs. Applies to personal templates only."""
    keys: list[Keyword] = []
    """The list of fields to show when this template is used."""
