"""Azure provider fields."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, Keyword, register_model


@register_model(index=True, store=True, description="Fields related to Azure.", embedded=True)
class Azure(HowlerEmbeddedModel):
    """Fields related to Azure."""

    subscription_id: Keyword | None = None
    """The unique identifier for the Azure subscription."""
    tenant_id: Keyword | None = None
    """The unique identifier for the Azure tenant."""
    resource_group: Keyword | None = None
    """The name of the Azure resource group."""
    upn: Keyword | None = None
    """The user principal name (UPN) in Azure, used for authentication. Alias of user.name."""
    resource_id: Keyword | None = None
    """The unique Azure Resource Identifier (AzureRI)."""
