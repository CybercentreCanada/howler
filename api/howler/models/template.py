"""Template model."""

from __future__ import annotations

from howler.models import HowlerESModel, case_insensitive_keyword, enum, keyword, list_field, register_model, uuid


@register_model(index=True, store=True, description="Model of templates")
class Template(HowlerESModel):
    """Model of templates."""

    template_id: uuid()
    """A UUID for this template"""
    analytic: case_insensitive_keyword()
    """The analytic which this template applies to."""
    detection: case_insensitive_keyword(optional=True)
    """The detection which this template applies to."""
    type: enum(values=["personal", "global"])
    """The type of template - personal or global?"""
    owner: keyword(optional=True)
    """The person to whom this template belongs. Applies to personal templates only."""
    keys: list_field(keyword(), default=[])
    """The list of fields to show when this template is used."""
