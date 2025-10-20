??? success "Auto-Generated Documentation"
    This set of documentation is automatically generated from source, and will help ensure any change to functionality will always be documented and available on release.

# Client

> A client is defined as the initiator of a network connection for events regarding sessions, connections, or bidirectional flow records.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| address | Keyword | Some event client addresses are defined ambiguously. The event will sometimes list an IP, a domain or a unix socket. You should always store the raw address in the .address field. | :material-minus-box-outline: Optional | `None` |
| bytes | Integer | Bytes sent from the client to the server. | :material-minus-box-outline: Optional | `None` |
| domain | Domain | The domain name of the client system. | :material-minus-box-outline: Optional | `None` |
| geo | [Geo](/howler-docs/odm/class/geo) | Geo fields can carry data about a specific location related to an event. | :material-minus-box-outline: Optional | `None` |
| ip | IP | IP address of the client (IPv4 or IPv6). | :material-minus-box-outline: Optional | `None` |
| mac | MAC | MAC address of the client. | :material-minus-box-outline: Optional | `None` |
| nat | [Nat](/howler-docs/odm/class/nat) | Translated NAT sessions (e.g. internal client to internet). | :material-minus-box-outline: Optional | `None` |
| packets | Integer | Packets sent from the destination to the source. | :material-minus-box-outline: Optional | `None` |
| port | Integer | Port of the client. | :material-minus-box-outline: Optional | `None` |
