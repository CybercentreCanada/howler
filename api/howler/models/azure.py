"""Azure provider fields."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, keyword, optional, register_model


@register_model(index=True, store=True, description="Fields related to Azure.", embedded=True)
class Azure(HowlerEmbeddedModel):
    """Fields related to Azure."""

    subscription_id: optional(keyword(), description="The unique identifier for the Azure subscription.")
    tenant_id: optional(keyword(), description="The unique identifier for the Azure tenant.")
    resource_group: optional(keyword(), description="The name of the Azure resource group.")
    upn: optional(
        keyword(),
        description="The user principal name (UPN) in Azure, used for authentication. Alias of user.name.",
    )
    resource_id: optional(keyword(), description="The unique Azure Resource Identifier (AzureRI).")
