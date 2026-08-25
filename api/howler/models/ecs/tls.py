"""ECS TLS field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, compound, keyword, optional, register_model


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
    """TLS server fields."""

    ja3s: optional(
        keyword(), description="A hash that identifies servers based on how they perform an SSL/TLS handshake."
    )


@register_model(
    index=True,
    store=True,
    description=(
        "A Server is defined as the responder in a network connection for events regarding sessions, "
        "connections, or bidirectional flow records."
    ),
    embedded=True,
)
class Client(HowlerEmbeddedModel):
    """TLS client fields."""

    server_name: optional(
        keyword(),
        description=(
            "Also called an SNI, this tells the server which hostname to which the client is "
            "attempting to connect to. When this value is available, it should get copied to destination.domain."
        ),
    )
    ja3: optional(
        keyword(), description="A hash that identifies clients based on how they perform an SSL/TLS handshake."
    )


@register_model(
    index=True,
    store=True,
    description=(
        "A Server is defined as the responder in a network connection for events regarding sessions, "
        "connections, or bidirectional flow records."
    ),
    embedded=True,
)
class TLS(HowlerEmbeddedModel):
    """Fields related to a TLS connection."""

    version: optional(keyword(), description="Numeric part of the version parsed from the original string.")
    version_protocol: optional(keyword(), description="Normalized lowercase protocol name parsed from original string.")
    client: optional(compound(Client))
    server: optional(compound(Server))
