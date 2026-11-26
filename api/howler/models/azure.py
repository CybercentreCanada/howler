"""Azure provider fields."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, keyword, register_model


@register_model(index=True, store=True, description="Fields related to Azure.", embedded=True)
class Azure(HowlerEmbeddedModel):
    """Fields related to Azure."""

    subscription_id: keyword(optional=True, description="The unique identifier for the Azure subscription.")
    tenant_id: keyword(optional=True, description="The unique identifier for the Azure tenant.")
    resource_group: keyword(optional=True, description="The name of the Azure resource group.")
    upn: keyword(
        optional=True,
        description="The user principal name (UPN) in Azure, used for authentication. Alias of user.name.",
    )
    resource_id: keyword(optional=True, description="The unique Azure Resource Identifier (AzureRI).")
