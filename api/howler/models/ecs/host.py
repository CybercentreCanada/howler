"""ECS host field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, ip, keyword, list_field, optional, register_model


@register_model(index=True, store=True, description="A host is defined as a general computing instance.", embedded=True)
class Host(HowlerEmbeddedModel):
    """A host is defined as a general computing instance."""

    id: optional(keyword(), description="Unique host id. Use Agent ID for HBS.")
    ip: list_field(ip(), default=[], description="Host ip addresses.")
    mac: list_field(keyword(), default=[], description="Host MAC addresses.")
    name: optional(keyword(), description="Name of the host.")
    hostname: optional(
        keyword(),
        description="Hostname of the host. It normally contains what the hostname command returns on the host machine",
    )
    domain: optional(keyword(), description="Domain the host is a member of.")
    type: optional(keyword(), description="As described by CSP.")
