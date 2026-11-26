"""ECS server field set (top-level, non-TLS)."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, ip, keyword, register_model


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

    ip: ip(optional=True)
    """IP address of the server (IPv4 or IPv6)."""
    address: keyword(optional=True)
    (
        "Some event server addresses are defined ambiguously. The event will sometimes list an IP, a domain or a unix "
        "socket. You should always store the raw address in the .address field."
    )
    domain: keyword(optional=True)
    """The domain name of the server system."""
