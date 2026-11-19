??? success "Auto-Generated Documentation"
    This set of documentation is automatically generated from source, and will help ensure any change to functionality will always be documented and available on release.

# Interface

> The interface fields are used to record ingress and egress interface information when reported by an observer (e.g. firewall, router, load balancer) in the context of the observer handling a network connection.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| id | Integer | Interface ID as reported by an observer (typically SNMP interface ID). | :material-minus-box-outline: Optional | `None` |
| name | Keyword | Name of interface | :material-minus-box-outline: Optional | `None` |


