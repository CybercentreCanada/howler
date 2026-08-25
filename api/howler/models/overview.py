"""Overview model."""

from __future__ import annotations

from howler.models import HowlerESModel, keyword, optional, register_model, uuid


@register_model(index=True, store=True, description="Model of overviews")
class Overview(HowlerESModel):
    """Model of overviews."""

    overview_id: uuid(description="A UUID for this overview")
    analytic: keyword(description="The analytic which this overview applies to.")
    detection: optional(keyword(), description="The detection which this overview applies to.")
    owner: optional(keyword(), description="The person to whom this overview belongs.")
    content: keyword(description="The markdown to show when this overview is used.")
