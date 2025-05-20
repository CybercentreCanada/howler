from typing import Optional

from howler import odm


@odm.model(
    index=True,
    store=True,
    description="The network is defined as the communication path over which a host or network event happens.",
)
class Network(odm.Model):
    direction: Optional[str] = odm.Keyword(
        description=(
            "The direction of network traffic relative to the host it was collected on. "
            '(values: "OUTBOUND", "INBOUND", "LISTENING", "UNKNOWN")'
        ),
        optional=True,
    )
    protocol = odm.Optional(
        odm.Keyword(
            description="Application layer protocol in the OSI Model",
        )
    )
    transport = odm.LowerKeyword(
        description=(
            "Transport layer protocol of the network traffic. "
            '(values: "udp", "udp_listener", "tcp", "tcp_listener", "unknown")'
        ),
        optional=True,
    )
