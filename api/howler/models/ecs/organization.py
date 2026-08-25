"""ECS organization field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, keyword, optional, register_model


@register_model(
    index=True,
    store=True,
    description="The organization fields enrich data with information "
    "about the company or entity the data is associated with.",
    embedded=True,
)
class Organization(HowlerEmbeddedModel):
    """The organization fields enrich data with information about the company or entity.

    The data is associated with.
    """

    id: optional(keyword(), description="Unique identifier for the organization.")
    name: keyword(description="Organization name.")
