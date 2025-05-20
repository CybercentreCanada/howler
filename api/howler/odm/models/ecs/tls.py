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
    ja3s: Optional[str] = odm.Optional(
        odm.Keyword(description="A hash that identifies servers based on how they perform an SSL/TLS handshake.")
    )


@odm.model(
    index=True,
    store=True,
    description=(
        "A Server is defined as the responder in a network connection for events regarding sessions, "
        "connections, or bidirectional flow records."
    ),
)
class Client(odm.Model):
    server_name: Optional[str] = odm.Optional(
        odm.Keyword(
            description=(
                "Also called an SNI, this tells the server which hostname to which the client is "
                "attempting to connect to. When this value is available, it should get copied to destination.domain."
            )
        )
    )
    ja3: Optional[str] = odm.Optional(
        odm.Keyword(description="A hash that identifies clients based on how they perform an SSL/TLS handshake.")
    )


@odm.model(
    index=True,
    store=True,
    description=(
        "A Server is defined as the responder in a network connection for events regarding sessions, "
        "connections, or bidirectional flow records."
    ),
)
class TLS(odm.Model):
    version: Optional[str] = odm.Optional(
        odm.Keyword(description="Numeric part of the version parsed from the original string.")
    )
    version_protocol: Optional[str] = odm.Optional(
        odm.Keyword(description="Normalized lowercase protocol name parsed from original string.")
    )
    client: Client = odm.Optional(odm.Compound(Client))
    server: Server = odm.Optional(odm.Compound(Server))
