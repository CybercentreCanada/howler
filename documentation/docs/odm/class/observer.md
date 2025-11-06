??? success "Auto-Generated Documentation"
    This set of documentation is automatically generated from source, and will help ensure any change to functionality will always be documented and available on release.

# Observer

> Observer is defined as a special network, security, or application device used to detect, observe, or create network, sercurity, or application event metrics

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| egress | [Egress](/howler-docs/odm/class/egress) | Holds information like interface number, name, vlan, and zone to classify ingress traffic | :material-minus-box-outline: Optional | `None` |
| hostname | Keyword | Hostname of the observer | :material-minus-box-outline: Optional | `None` |
| ingress | [Ingress](/howler-docs/odm/class/ingress) | Holds information like interface number, name, vlan, and zone to classify ingress traffic | :material-minus-box-outline: Optional | `None` |
| interface | [Interface](/howler-docs/odm/class/interface) | Interface being observed | :material-minus-box-outline: Optional | `None` |
| ip | List [IP] | None | :material-checkbox-marked-outline: Yes | `[]` |
| mac | List [Keyword] | None | :material-checkbox-marked-outline: Yes | `[]` |
| name | Keyword | Custom name of the observer | :material-minus-box-outline: Optional | `None` |
| product | Keyword | Product name of the observer | :material-minus-box-outline: Optional | `None` |
| serial_number | Keyword | Observer serial number | :material-minus-box-outline: Optional | `None` |
| type | Keyword | Type of the observer the data is coming from | :material-minus-box-outline: Optional | `None` |
| vendor | Keyword | Vendor name of the observer | :material-minus-box-outline: Optional | `None` |
| version | Keyword | Observer version | :material-minus-box-outline: Optional | `None` |


