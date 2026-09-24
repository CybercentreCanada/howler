??? success "Auto-Generated Documentation"
    This set of documentation is automatically generated from source, and will help ensure any change to functionality will always be documented and available on release.

# DNSQuestion

> An object encapsulating the question asked to the server.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| class | Keyword | The class of records being queried. | :material-minus-box-outline: Optional | `None` |
| name | Keyword | The name being queried. | :material-minus-box-outline: Optional | `None` |
| registered_domain | Domain | The highest registered domain, stripped of the subdomain. | :material-minus-box-outline: Optional | `None` |
| subdomain | Keyword | The subdomain is all of the labels under the registered_domain. | :material-minus-box-outline: Optional | `None` |
| top_level_domain | Keyword | The effective top level domain (eTLD), also known as the domain suffix, is the last part of the domain name. | :material-minus-box-outline: Optional | `None` |
| type | Keyword | The type of record being queried. | :material-minus-box-outline: Optional | `None` |
