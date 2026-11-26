"""ECS network field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, Keyword, LowerKeyword, register_model


@register_model(
    index=True,
    store=True,
    description="The network is defined as the communication path over which a host or network event happens.",
    embedded=True,
)
class Network(HowlerEmbeddedModel):
    """The network is defined as the communication path over which a host or network event happens."""

    direction: Keyword | None = None
    (
        'The direction of network traffic relative to the host it was collected on. (values: "OUTBOUND", "INBOUND", '
        '"LISTENING", "UNKNOWN")'
    )
    protocol: Keyword | None = None
    """Application layer protocol in the OSI Model"""
    transport: LowerKeyword | None = None
    (
        'Transport layer protocol of the network traffic. (values: "udp", "udp_listener", "tcp", "tcp_listener", '
        '"unknown")'
    )
