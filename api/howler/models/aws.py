"""AWS provider fields."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, compound, keyword, optional, register_model


@register_model(index=True, store=True, description="Cloud account information.", embedded=True)
class Account(HowlerEmbeddedModel):
    """Cloud account information."""

    id: optional(keyword(), description="The ID of the AWS Account.")
    name: optional(keyword(), description="The name of the AWS Account.")


@register_model(index=True, store=True, description="Organization information.", embedded=True)
class Organization(HowlerEmbeddedModel):
    """Organization information."""

    id: optional(keyword(), description="The ID of the AWS Organization.")
    organizational_unit: optional(keyword(), description="The Organizational Unit the Account belongs to.")


@register_model(index=True, store=True, description="Fields related to AWS.", embedded=True)
class AWS(HowlerEmbeddedModel):
    """Fields related to AWS."""

    account: optional(compound(Account), description="AWS account information.")
    organization: optional(compound(Organization), description="Organization information.")
