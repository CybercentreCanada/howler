??? success "Auto-Generated Documentation"
    This set of documentation is automatically generated from source, and will help ensure any change to functionality will always be documented and available on release.

# Host

> A host is defined as a general computing instance.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| id | Keyword | Unique host id. Use Agent ID for HBS. | :material-minus-box-outline: Optional | `None` |
| ip | List [IP] | Host ip addresses. | :material-checkbox-marked-outline: Yes | `[]` |
| mac | List [Keyword] | Host MAC addresses. | :material-checkbox-marked-outline: Yes | `[]` |
| name | Keyword | Name of the host. | :material-minus-box-outline: Optional | `None` |
| domain | Keyword | Domain the host is a member of. | :material-minus-box-outline: Optional | `None` |
| type | Keyword | As described by CSP. | :material-minus-box-outline: Optional | `None` |
