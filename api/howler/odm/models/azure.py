from howler import odm


@odm.model(
    index=True,
    store=True,
    description="Fields related to Azure.",
)
class Azure(odm.Model):
    subscription_id = odm.Optional(odm.Keyword(description="The unique identifier for the Azure subscription."))
    tenant_id = odm.Optional(odm.Keyword(description="The unique identifier for the Azure tenant."))
    resource_group = odm.Optional(odm.Keyword(description="The name of the Azure resource group."))
    upn = odm.Optional(
        odm.Keyword(description="The user principal name (UPN) in Azure, used for authentication. Alias of user.name.")
    )
    resource_id = odm.Optional(odm.Keyword(description="The unique Azure Resource Identifier (AzureRI)."))
