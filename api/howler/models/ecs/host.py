"""ECS host field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, ip, keyword, list_field, register_model


@register_model(index=True, store=True, description="A host is defined as a general computing instance.", embedded=True)
class Host(HowlerEmbeddedModel):
    """A host is defined as a general computing instance."""

    id: keyword(optional=True)
    """Unique host id. Use Agent ID for HBS."""
    ip: list_field(ip(), default=[])
    """Host ip addresses."""
    mac: list_field(keyword(), default=[])
    """Host MAC addresses."""
    name: keyword(optional=True)
    """Name of the host."""
    hostname: keyword(optional=True)
    """Hostname of the host. It normally contains what the hostname command returns on the host machine"""
    domain: keyword(optional=True)
    """Domain the host is a member of."""
    type: keyword(optional=True)
    """As described by CSP."""
