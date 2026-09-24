"""Sentinel Pydantic model: metadata relating to Microsoft Sentinel.

Mirrors the stored Sentinel fields using the ``howler.models`` Pydantic/DSL foundation.
"""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, keyword, optional, register_model


@register_model(index=True, store=True, description="The Sentinel fields contain any data relating to Sentinel.")
class Sentinel(HowlerEmbeddedModel):
    """The Sentinel fields contain any data relating to Sentinel."""

    id: optional(keyword(), description="The sentinel alert url for a staged alert.")
