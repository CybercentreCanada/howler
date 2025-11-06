??? success "Auto-Generated Documentation"
    This set of documentation is automatically generated from source, and will help ensure any change to functionality will always be documented and available on release.

# Network

> The network is defined as the communication path over which a host or network event happens.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| direction | Keyword | The direction of network traffic relative to the host it was collected on. (values: "OUTBOUND", "INBOUND", "LISTENING", "UNKNOWN") | :material-minus-box-outline: Optional | `None` |
| protocol | Keyword | Application layer protocol in the OSI Model | :material-minus-box-outline: Optional | `None` |
| transport | LowerKeyword | Transport layer protocol of the network traffic. (values: "udp", "udp_listener", "tcp", "tcp_listener", "unknown") | :material-minus-box-outline: Optional | `None` |


