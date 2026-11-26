"""ECS client field set (client/source/destination)."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, compound, domain, integer, ip, keyword, long, mac, register_model
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

    ip: ip(optional=True, description="Translated IP of source based NAT sessions.")
    port: integer(optional=True, description="Translated port of source based NAT sessions.")


@register_model(
    index=True,
    store=True,
    description="A client is defined as the initiator of a network connection "
    "for events regarding sessions, connections, or bidirectional flow records.",
    embedded=True,
)
class OriginalClient(HowlerEmbeddedModel):
    """The original client in a session that has changed clients."""

    address: keyword(
        optional=True,
        description=(
            "The original client in a session that has changed clients. Some event client addresses "
            "are defined ambiguously. The event will sometimes list an IP, a domain or a unix socket. You should"
            " always store the raw address in the .address field."
        ),
    )
    autonomous_systems: compound(
        AS,
        optional=True,
        description=(
            "The original client in a session that has changed clients. "
            "Collection of connected Internal Protocol routing prefixes"
        ),
    )
    bytes: integer(
        optional=True,
        description=(
            "The original client in a session that has changed clients. Bytes sent from the client to the server."
        ),
    )
    domain: domain(
        optional=True,
        description=(
            "The original client in a session that has changed clients. The domain name of the client system."
        ),
    )
    geo: compound(
        Geo,
        optional=True,
        description=(
            "The original client in a session that has changed clients. Geo fields can carry "
            "data about a specific location related to an event."
        ),
    )
    ip: ip(
        optional=True,
        description=(
            "The original client in a session that has changed clients. IP address of the client (IPv4 or IPv6)."
        ),
    )
    mac: mac(
        optional=True,
        description=("The original client in a session that has changed clients. MAC address of the client."),
    )
    nat: compound(
        Nat,
        optional=True,
        description=(
            "The original client in a session that has changed clients. Translated NAT sessions (e.g. "
            "internal client to internet)."
        ),
    )
    packets: integer(
        optional=True,
        description=(
            "The original client in a session that has changed clients. Packets sent from the "
            "destination to the source."
        ),
    )
    port: integer(
        optional=True, description="The original client in a session that has changed clients. Port of the client."
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

    address: keyword(
        optional=True,
        description="Some event client addresses are defined ambiguously. The event will sometimes list an IP, "
        "a domain or a unix socket. You should always store the raw address in the .address field.",
    )
    autonomous_systems: compound(
        AS, optional=True, description="Collection of connected Internal Protocol routing prefixes"
    )
    bytes: long(optional=True, description="Bytes sent from the client to the server.")
    domain: keyword(optional=True, description="The domain name of the client system.")
    geo: compound(
        Geo, optional=True, description="Geo fields can carry data about a specific location related to an event."
    )
    ip: ip(optional=True, description="IP address of the client (IPv4 or IPv6).")
    mac: mac(optional=True, description="MAC address of the client.")
    nat: compound(Nat, optional=True, description="Translated NAT sessions (e.g. internal client to internet).")
    packets: integer(optional=True, description="Packets sent from the destination to the source.")
    port: integer(optional=True, description="Port of the client.")
    user: compound(
        User,
        optional=True,
        description="The user fields describe information about the user that is relevant to the event.",
    )
    original: compound(OriginalClient, optional=True, description="Original Client Data.")
