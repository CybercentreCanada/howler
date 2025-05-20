from typing import Optional

from howler import odm


@odm.model(
    index=True,
    store=True,
    description=(
        "A Server is defined as the responder in a network connection for events regarding sessions, "
        "connections, or bidirectional flow records."
    ),
)
class Server(odm.Model):
    ip: Optional[str] = odm.Optional(odm.IP(description="IP address of the server (IPv4 or IPv6)."))
    address: Optional[str] = odm.Optional(
        odm.Keyword(
            description=(
                "Some event server addresses are defined ambiguously. The event will sometimes list an IP, a "
                "domain or a unix socket. You should always store the raw address in the .address field."
            )
        )
    )
    domain: Optional[str] = odm.Optional(odm.Keyword(description="The domain name of the server system."))
