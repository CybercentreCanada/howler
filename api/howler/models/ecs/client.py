"""ECS client field set (client/source/destination)."""

from __future__ import annotations

from howler.models import (
    HowlerEmbeddedModel,
    compound,
    domain,
    integer,
    ip,
    keyword,
    long,
    mac,
    optional,
    register_model,
)
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

    ip: optional(ip(), description="Translated IP of source based NAT sessions.")
    port: optional(integer(), description="Translated port of source based NAT sessions.")


@register_model(
    index=True,
    store=True,
    description="A client is defined as the initiator of a network connection "
    "for events regarding sessions, connections, or bidirectional flow records.",
    embedded=True,
)
class OriginalClient(HowlerEmbeddedModel):
    """The original client in a session that has changed clients."""

    address: optional(
        keyword(),
        description=(
            "The original client in a session that has changed clients. Some event client addresses "
            "are defined ambiguously. The event will sometimes list an IP, a domain or a unix socket. You should"
            " always store the raw address in the .address field."
        ),
    )
    autonomous_systems: optional(
        compound(AS),
        description=(
            "The original client in a session that has changed clients. "
            "Collection of connected Internal Protocol routing prefixes"
        ),
    )
    bytes: optional(
        integer(),
        description=(
            "The original client in a session that has changed clients. Bytes sent from the client to the server."
        ),
    )
    domain: optional(
        domain(),
        description=(
            "The original client in a session that has changed clients. The domain name of the client system."
        ),
    )
    geo: optional(
        compound(Geo),
        description=(
            "The original client in a session that has changed clients. Geo fields can carry "
            "data about a specific location related to an event."
        ),
    )
    ip: optional(
        ip(),
        description=(
            "The original client in a session that has changed clients. IP address of the client (IPv4 or IPv6)."
        ),
    )
    mac: optional(
        mac(),
        description=("The original client in a session that has changed clients. MAC address of the client."),
    )
    nat: optional(
        compound(Nat),
        description=(
            "The original client in a session that has changed clients. Translated NAT sessions (e.g. "
            "internal client to internet)."
        ),
    )
    packets: optional(
        integer(),
        description=(
            "The original client in a session that has changed clients. Packets sent from the "
            "destination to the source."
        ),
    )
    port: optional(
        integer(), description="The original client in a session that has changed clients. Port of the client."
    )


@register_model(
    index=True,
    store=True,
    description="A client is defined as the initiator of a network connection "
    "for events regarding sessions, connections, or bidirectional flow records.",
    embedded=True,
)
class Client(HowlerEmbeddedModel):
    """A client is defined as the initiator of a network connection."""

    address: optional(
        keyword(),
        description="Some event client addresses are defined ambiguously. The event will sometimes list an IP, "
        "a domain or a unix socket. You should always store the raw address in the .address field.",
    )
    autonomous_systems: optional(compound(AS), description="Collection of connected Internal Protocol routing prefixes")
    bytes: optional(long(), description="Bytes sent from the client to the server.")
    domain: optional(keyword(), description="The domain name of the client system.")
    geo: optional(compound(Geo), description="Geo fields can carry data about a specific location related to an event.")
    ip: optional(ip(), description="IP address of the client (IPv4 or IPv6).")
    mac: optional(mac(), description="MAC address of the client.")
    nat: optional(compound(Nat), description="Translated NAT sessions (e.g. internal client to internet).")
    packets: optional(integer(), description="Packets sent from the destination to the source.")
    port: optional(integer(), description="Port of the client.")
    user: optional(
        compound(User),
        description="The user fields describe information about the user that is relevant to the event.",
    )
    original: optional(compound(OriginalClient), description="Original Client Data.")
