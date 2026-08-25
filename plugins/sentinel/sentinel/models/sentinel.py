"""Sentinel Pydantic model: metadata relating to Microsoft Sentinel.

Mirrors ``sentinel.odm.models.sentinel.Sentinel`` field-for-field, built on the new
``howler.models`` Pydantic/DSL foundation. The legacy ``odm`` module keeps running unchanged
until the Step 8 consumer/runtime cutover.
"""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, keyword, optional, register_model


@register_model(index=True, store=True, description="The Sentinel fields contain any data relating to Sentinel.")
class Sentinel(HowlerEmbeddedModel):
    """The Sentinel fields contain any data relating to Sentinel."""

    id: optional(keyword(), description="The sentinel alert url for a staged alert.")
