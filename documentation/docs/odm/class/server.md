??? success "Auto-Generated Documentation"
    This set of documentation is automatically generated from source, and will help ensure any change to functionality will always be documented and available on release.

# Server

> A Server is defined as the responder in a network connection for events regarding sessions, connections, or bidirectional flow records.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| ip | IP | IP address of the server (IPv4 or IPv6). | :material-minus-box-outline: Optional | `None` |
| address | Keyword | Some event server addresses are defined ambiguously. The event will sometimes list an IP, a domain or a unix socket. You should always store the raw address in the .address field. | :material-minus-box-outline: Optional | `None` |
| domain | Keyword | The domain name of the server system. | :material-minus-box-outline: Optional | `None` |
