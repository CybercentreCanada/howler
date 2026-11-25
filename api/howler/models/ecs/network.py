"""ECS network field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, keyword, lower_keyword, optional, register_model


@register_model(
    index=True,
    store=True,
    description="The network is defined as the communication path over which a host or network event happens.",
    embedded=True,
)
class Network(HowlerEmbeddedModel):
    """The network is defined as the communication path over which a host or network event happens."""

    direction: optional(
        keyword(),
        description="The direction of network traffic relative to the host it was collected on. "
        '(values: "OUTBOUND", "INBOUND", "LISTENING", "UNKNOWN")',
    )
    protocol: optional(keyword(), description="Application layer protocol in the OSI Model")
    transport: optional(
        lower_keyword(),
        description="Transport layer protocol of the network traffic. "
        '(values: "udp", "udp_listener", "tcp", "tcp_listener", "unknown")',
    )
