# mypy: ignore-errors
from typing import Optional

from howler import odm
from howler.odm.models.ecs.autonomous_system import AS
from howler.odm.models.ecs.geo import Geo
from howler.odm.models.ecs.user import User


@odm.model(
    index=True,
    store=True,
    description="Translated NAT sessions (e.g. internal client to internet).",
)
class Nat(odm.Model):
    ip = odm.Optional(odm.IP(description="Translated IP of source based NAT sessions."))
    port = odm.Optional(odm.Integer(description="Translated port of source based NAT sessions."))


@odm.model(
    index=True,
    store=True,
    description="A client is defined as the initiator of a network connection "
    "for events regarding sessions, connections, or bidirectional flow records.",
)
class OriginalClient(odm.Model):
    address: Optional[str] = odm.Optional(
        odm.Keyword(
            description=(
                "The original client in a session that has changed clients. Some event client addresses "
                "are defined ambiguously. The event will sometimes list an IP, a domain or a unix socket. You should"
                " always store the raw address in the .address field."
            )
        )
    )
    autonomous_systems: AS = odm.Optional(
        odm.Compound(
            AS,
            description=(
                "The original client in a session that has changed clients. "
                "Collection of connected Internal Protocol routing prefixes"
            ),
        )
    )
    bytes: Optional[int] = odm.Optional(
        odm.Integer(
            description=(
                "The original client in a session that has changed clients. "
                "Bytes sent from the client to the server."
            )
        )
    )
    domain: Optional[str] = odm.Optional(
        odm.Domain(
            description=(
                "The original client in a session that has changed clients. " "The domain name of the client system."
            )
        )
    )
    geo: Geo = odm.Optional(
        odm.Compound(
            Geo,
            description=(
                "The original client in a session that has changed clients. Geo fields can carry "
                "data about a specific location related to an event."
            ),
        )
    )
    ip: Optional[str] = odm.Optional(
        odm.IP(
            description=(
                "The original client in a session that has changed clients. IP address of the " "client (IPv4 or IPv6)."
            )
        )
    )
    mac: Optional[str] = odm.Optional(
        odm.MAC(description=("The original client in a session that has changed clients. MAC address of the client."))
    )
    nat: Nat = odm.Optional(
        odm.Compound(
            Nat,
            description=(
                "The original client in a session that has changed clients. Translated NAT sessions (e.g. "
                "internal client to internet)."
            ),
        )
    )
    packets: Optional[int] = odm.Optional(
        odm.Integer(
            description=(
                "The original client in a session that has changed clients. Packets sent from the "
                "destination to the source."
            )
        )
    )
    port: Optional[int] = odm.Optional(
        odm.Integer(description="The original client in a session that has changed clients. Port of the client.")
    )


@odm.model(
    index=True,
    store=True,
    description="A client is defined as the initiator of a network connection "
    "for events regarding sessions, connections, or bidirectional flow records.",
)
class Client(odm.Model):
    address: Optional[str] = odm.Optional(
        odm.Keyword(
            description="Some event client addresses are defined ambiguously. The event will sometimes list an IP, "
            "a domain or a unix socket. You should always store the raw address in the .address field."
        )
    )
    autonomous_systems: AS = odm.Optional(
        odm.Compound(
            AS,
            description="Collection of connected Internal Protocol routing prefixes",
        )
    )
    bytes: Optional[int] = odm.Optional(odm.Integer(description="Bytes sent from the client to the server."))
    domain: Optional[str] = odm.Optional(odm.Keyword(description="The domain name of the client system."))
    geo: Geo = odm.Optional(
        odm.Compound(
            Geo,
            description="Geo fields can carry data about a specific location related to an event.",
        )
    )
    ip: Optional[str] = odm.Optional(odm.IP(description="IP address of the client (IPv4 or IPv6)."))
    mac: Optional[str] = odm.Optional(odm.MAC(description="MAC address of the client."))
    nat: Nat = odm.Optional(
        odm.Compound(
            Nat,
            description="Translated NAT sessions (e.g. internal client to internet).",
        )
    )
    packets: Optional[int] = odm.Optional(odm.Integer(description="Packets sent from the destination to the source."))
    port: Optional[int] = odm.Optional(odm.Integer(description="Port of the client."))
    user: User = odm.Optional(
        odm.Compound(
            User,
            description="The user fields describe information about the user that is relevant to the event.",
        )
    )
    original: OriginalClient = odm.Optional(
        odm.Compound(
            OriginalClient,
            description="Original Client Data.",
        )
    )
