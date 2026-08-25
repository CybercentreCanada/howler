"""Template model."""

from __future__ import annotations

from howler.models import HowlerESModel, enum, keyword, list_field, optional, register_model, uuid


@register_model(index=True, store=True, description="Model of templates")
class Template(HowlerESModel):
    """Model of templates."""

    template_id: uuid(description="A UUID for this template")
    analytic: keyword(description="The analytic which this template applies to.")
    detection: optional(keyword(), description="The detection which this template applies to.")
    type: enum(values=["personal", "global"], description="The type of template - personal or global?")
    owner: optional(
        keyword(),
        description="The person to whom this template belongs. Applies to personal templates only.",
    )
    keys: list_field(keyword(), default=[], description="The list of fields to show when this template is used.")
