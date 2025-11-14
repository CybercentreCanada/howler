??? success "Auto-Generated Documentation"
    This set of documentation is automatically generated from source, and will help ensure any change to functionality will always be documented and available on release.

# OriginalClient

> A client is defined as the initiator of a network connection for events regarding sessions, connections, or bidirectional flow records.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| address | Keyword | The original client in a session that has changed clients. Some event client addresses are defined ambiguously. The event will sometimes list an IP, a domain or a unix socket. You should always store the raw address in the .address field. | :material-minus-box-outline: Optional | `None` |
| autonomous_systems | [AS](/howler/odm/class/as) | The original client in a session that has changed clients. Collection of connected Internal Protocol routing prefixes | :material-minus-box-outline: Optional | `None` |
| bytes | Integer | The original client in a session that has changed clients. Bytes sent from the client to the server. | :material-minus-box-outline: Optional | `None` |
| domain | Domain | The original client in a session that has changed clients. The domain name of the client system. | :material-minus-box-outline: Optional | `None` |
| geo | [Geo](/howler/odm/class/geo) | The original client in a session that has changed clients. Geo fields can carry data about a specific location related to an event. | :material-minus-box-outline: Optional | `None` |
| ip | IP | The original client in a session that has changed clients. IP address of the client (IPv4 or IPv6). | :material-minus-box-outline: Optional | `None` |
| mac | MAC | The original client in a session that has changed clients. MAC address of the client. | :material-minus-box-outline: Optional | `None` |
| nat | [Nat](/howler/odm/class/nat) | The original client in a session that has changed clients. Translated NAT sessions (e.g. internal client to internet). | :material-minus-box-outline: Optional | `None` |
| packets | Integer | The original client in a session that has changed clients. Packets sent from the destination to the source. | :material-minus-box-outline: Optional | `None` |
| port | Integer | The original client in a session that has changed clients. Port of the client. | :material-minus-box-outline: Optional | `None` |
