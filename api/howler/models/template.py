"""Template model."""

from __future__ import annotations

from howler.models import UUID, CaseInsensitiveKeyword, HowlerESModel, Keyword, enum, register_model


@register_model(index=True, store=True, description="Model of templates")
class Template(HowlerESModel):
    """Model of templates."""

    template_id: UUID
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
