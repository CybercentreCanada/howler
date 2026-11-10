"""Overview model."""

from __future__ import annotations

from howler.models import HowlerESModel, case_insensitive_keyword, keyword, optional, register_model, text, uuid


@register_model(index=True, store=True, description="Model of overviews")
class Overview(HowlerESModel):
    """Model of overviews."""

    overview_id: uuid(description="A UUID for this overview")
    analytic: case_insensitive_keyword(description="The analytic which this overview applies to.")
    detection: optional(case_insensitive_keyword(), description="The detection which this overview applies to.")
    owner: optional(keyword(), description="The person to whom this overview belongs.")
    content: text(description="The markdown to show when this overview is used.")
