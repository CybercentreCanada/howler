"""ECS host field set."""

from __future__ import annotations

from typing import Annotated

from howler.models import IP, HowlerEmbeddedModel, Keyword, metadata, register_model


@register_model(index=True, store=True, description="A host is defined as a general computing instance.", embedded=True)
class Host(HowlerEmbeddedModel):
    """A host is defined as a general computing instance."""

    id: Keyword | None = None
    """Unique host id. Use Agent ID for HBS."""
    ip: Annotated[list[IP], metadata(default=[])]
    """Host ip addresses."""
    mac: list[Keyword] = []
    """Host MAC addresses."""
    name: Keyword | None = None
    """Name of the host."""
    hostname: Keyword | None = None
    """Hostname of the host. It normally contains what the hostname command returns on the host machine"""
    domain: Keyword | None = None
    """Domain the host is a member of."""
    type: Keyword | None = None
    """As described by CSP."""
