??? success "Auto-Generated Documentation"
    This set of documentation is automatically generated from source, and will help ensure any change to functionality will always be documented and available on release.

# DNS

> Fields describing DNS queries and answers.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| answers | List [[DNSAnswer](/howler-docs/odm/class/dnsanswer)] | An array containing an object for each answer section returned by the server. | :material-minus-box-outline: Optional | `None` |
| header_flags | List [Keyword] | Array of 2 letter DNS header flags. | :material-minus-box-outline: Optional | `None` |
| id | Keyword | The DNS packet identifier assigned by the program that generated the query. | :material-minus-box-outline: Optional | `None` |
| op_code | Keyword | The DNS operation code that specifies the kind of query in the message. | :material-minus-box-outline: Optional | `None` |
| question | [DNSQuestion](/howler-docs/odm/class/dnsquestion) | An object encapsulating the question asked to the server. | :material-minus-box-outline: Optional | `None` |
| resolved_ip | List [IP] | Array containing all IPs seen in answers.data. | :material-minus-box-outline: Optional | `None` |
| response_code | Keyword | The DNS response code. | :material-minus-box-outline: Optional | `None` |
| type | Keyword | The type of DNS event captured, query or answer. | :material-minus-box-outline: Optional | `None` |
