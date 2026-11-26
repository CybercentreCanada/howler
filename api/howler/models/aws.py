"""AWS provider fields."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, keyword, register_model


@register_model(index=True, store=True, description="Cloud account information.", embedded=True)
class Account(HowlerEmbeddedModel):
    """Cloud account information."""

    id: keyword(optional=True)
    """The ID of the AWS Account."""
    name: keyword(optional=True)
    """The name of the AWS Account."""


@register_model(index=True, store=True, description="Organization information.", embedded=True)
class Organization(HowlerEmbeddedModel):
    """Organization information."""

    id: keyword(optional=True)
    """The ID of the AWS Organization."""
    organizational_unit: keyword(optional=True)
    """The Organizational Unit the Account belongs to."""


@register_model(index=True, store=True, description="Fields related to AWS.", embedded=True)
class AWS(HowlerEmbeddedModel):
    """Fields related to AWS."""

    account: Account | None = None
    """AWS account information."""
    organization: Organization | None = None
    """Organization information."""
