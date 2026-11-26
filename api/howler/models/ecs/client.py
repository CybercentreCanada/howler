"""ECS client field set (client/source/destination)."""

from __future__ import annotations

from howler.models import IP, MAC, Domain, HowlerEmbeddedModel, Integer, Keyword, Long, register_model
from howler.models.ecs.autonomous_system import AS
from howler.models.ecs.geo import Geo
from howler.models.ecs.user import User


@register_model(
    index=True,
    store=True,
    description="Translated NAT sessions (e.g. internal client to internet).",
    embedded=True,
)
class Nat(HowlerEmbeddedModel):
    """Translated NAT sessions (e.g. internal client to internet)."""

    ip: IP | None = None
    """Translated IP of source based NAT sessions."""
    port: Integer | None = None
    """Translated port of source based NAT sessions."""


@register_model(
    index=True,
    store=True,
    description="A client is defined as the initiator of a network connection "
    "for events regarding sessions, connections, or bidirectional flow records.",
    embedded=True,
)
class OriginalClient(HowlerEmbeddedModel):
    """The original client in a session that has changed clients."""

    address: Keyword | None = None
    (
        "The original client in a session that has changed clients. Some event client addresses are defined "
        "ambiguously. The event will sometimes list an IP, a domain or a unix socket. You should always store the raw "
        "address in the .address field."
    )
    autonomous_systems: AS | None = None
    (
        "The original client in a session that has changed clients. Collection of connected Internal Protocol routing "
        "prefixes"
    )
    bytes: Integer | None = None
    """The original client in a session that has changed clients. Bytes sent from the client to the server."""
    domain: Domain | None = None
    """The original client in a session that has changed clients. The domain name of the client system."""
    geo: Geo | None = None
    (
        "The original client in a session that has changed clients. Geo fields can carry data about a specific "
        "location related to an event."
    )
    ip: IP | None = None
    """The original client in a session that has changed clients. IP address of the client (IPv4 or IPv6)."""
    mac: MAC | None = None
    """The original client in a session that has changed clients. MAC address of the client."""
    nat: Nat | None = None
    (
        "The original client in a session that has changed clients. Translated NAT sessions (e.g. internal client to "
        "internet)."
    )
    packets: Integer | None = None
    """The original client in a session that has changed clients. Packets sent from the destination to the source."""
    port: Integer | None = None
    """The original client in a session that has changed clients. Port of the client."""


@register_model(
    index=True,
    store=True,
    description="A client is defined as the initiator of a network connection "
    "for events regarding sessions, connections, or bidirectional flow records.",
    embedded=True,
)
class Client(HowlerEmbeddedModel):
    """A client is defined as the initiator of a network connection."""

    address: Keyword | None = None
    (
        "Some event client addresses are defined ambiguously. The event will sometimes list an IP, a domain or a unix "
        "socket. You should always store the raw address in the .address field."
    )
    autonomous_systems: AS | None = None
    """Collection of connected Internal Protocol routing prefixes"""
    bytes: Long | None = None
    """Bytes sent from the client to the server."""
    domain: Keyword | None = None
    """The domain name of the client system."""
    geo: Geo | None = None
    """Geo fields can carry data about a specific location related to an event."""
    ip: IP | None = None
    """IP address of the client (IPv4 or IPv6)."""
    mac: MAC | None = None
    """MAC address of the client."""
    nat: Nat | None = None
    """Translated NAT sessions (e.g. internal client to internet)."""
    packets: Integer | None = None
    """Packets sent from the destination to the source."""
    port: Integer | None = None
    """Port of the client."""
    user: User | None = None
    """The user fields describe information about the user that is relevant to the event."""
    original: OriginalClient | None = None
    """Original Client Data."""
