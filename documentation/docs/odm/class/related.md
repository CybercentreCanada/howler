??? success "Auto-Generated Documentation"
    This set of documentation is automatically generated from source, and will help ensure any change to functionality will always be documented and available on release.

# Related

> This field set is meant to facilitate pivoting around a piece of data.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| hash | List [Keyword] | All the hashes seen on your event. Populating this field, then using it to search for hashes can help in situations where you're unsure what the hash algorithm is (and therefore which key name to search). | :material-checkbox-marked-outline: Yes | `[]` |
| hosts | List [Keyword] | All hostnames or other host identifiers seen on your event. Example identifiers include FQDNs, domain names, workstation names, or aliases. | :material-checkbox-marked-outline: Yes | `[]` |
| ip | List [IP] | All of the IPs seen on your event. | :material-checkbox-marked-outline: Yes | `[]` |
| user | List [Keyword] | All the user names or other user identifiers seen on the event. | :material-checkbox-marked-outline: Yes | `[]` |
| id | Keyword | The id related to the event. | :material-minus-box-outline: Optional | `None` |
| uri | List [URI] | All of the URIs related to the event. | :material-minus-box-outline: Optional | `None` |
| signature | List [Keyword] | All the signatures/rules that were triggered by the event. | :material-minus-box-outline: Optional | `None` |
