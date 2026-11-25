"""ECS server field set (top-level, non-TLS)."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, ip, keyword, optional, register_model


@register_model(
    index=True,
    store=True,
    description=(
        "A Server is defined as the responder in a network connection for events regarding sessions, "
        "connections, or bidirectional flow records."
    ),
    embedded=True,
)
class Server(HowlerEmbeddedModel):
    """A Server is defined as the responder in a network connection."""

    ip: optional(ip(), description="IP address of the server (IPv4 or IPv6).")
    address: optional(
        keyword(),
        description=(
            "Some event server addresses are defined ambiguously. The event will sometimes list an IP, a "
            "domain or a unix socket. You should always store the raw address in the .address field."
        ),
    )
    domain: optional(keyword(), description="The domain name of the server system.")
