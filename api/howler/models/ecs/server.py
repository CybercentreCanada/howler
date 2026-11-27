"""ECS server field set (top-level, non-TLS)."""

from __future__ import annotations

from howler.models import IP, HowlerEmbeddedModel, Keyword, register_model


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

    ip: IP | None = None
    """IP address of the server (IPv4 or IPv6)."""
    address: Keyword | None = None
    (
        "Some event server addresses are defined ambiguously. The event will sometimes list an IP, a domain or a unix "
        "socket. You should always store the raw address in the .address field."
    )
    domain: Keyword | None = None
    """The domain name of the server system."""
