from howler import odm


@odm.model(index=True, store=True, description="Cloud account information.")
class Account(odm.Model):
    id = odm.Optional(odm.Keyword(description="The ID of the AWS Account."))
    name = odm.Optional(odm.Keyword(description="The name of the AWS Account."))


@odm.model(index=True, store=True, description="Organization information.")
class Organization(odm.Model):
    id = odm.Optional(odm.Keyword(description="The ID of the AWS Organization."))
    organizational_unit = odm.Optional(odm.Keyword(description="The Organizational Unit the Account belongs to."))


@odm.model(
    index=True,
    store=True,
    description="Fields related to AWS.",
)
class AWS(odm.Model):
    account = odm.Optional(odm.Compound(Account, description="AWS account information."))
    organization = odm.Optional(odm.Compound(Organization, description="Organization information."))
