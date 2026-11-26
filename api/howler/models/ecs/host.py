"""ECS host field set."""

from __future__ import annotations

from typing import Annotated

from howler.models import HowlerEmbeddedModel, keyword, metadata, register_model
from howler.models import ip as ip_field


@register_model(index=True, store=True, description="A host is defined as a general computing instance.", embedded=True)
class Host(HowlerEmbeddedModel):
    """A host is defined as a general computing instance."""

    id: keyword(optional=True)
    """Unique host id. Use Agent ID for HBS."""
    ip: Annotated[list[ip_field()], metadata(default=[])]
    """Host ip addresses."""
    mac: list[keyword()] = []
    """Host MAC addresses."""
    name: keyword(optional=True)
    """Name of the host."""
    hostname: keyword(optional=True)
    """Hostname of the host. It normally contains what the hostname command returns on the host machine"""
    domain: keyword(optional=True)
    """Domain the host is a member of."""
    type: keyword(optional=True)
    """As described by CSP."""
