??? success "Auto-Generated Documentation"
    This set of documentation is automatically generated from source, and will help ensure any change to functionality will always be documented and available on release.

# URL

> URL fields provide support for complete or partial URLs, and supports the breaking down into scheme, domain, path, and so on.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| domain | Domain | Domain of the url, such as "www.elastic.co". | :material-minus-box-outline: Optional | `None` |
| extension | Keyword | The field contains the file extension from the original request url, excluding the leading dot. | :material-minus-box-outline: Optional | `None` |
| fragment | Keyword | Portion of the url after the #, such as "top". | :material-minus-box-outline: Optional | `None` |
| full | Keyword | If full URLs are important to your use case, they should be stored in url.full, whether this field is reconstructed or present in the event source. | :material-minus-box-outline: Optional | `None` |
| original | Keyword | Unmodified original url as seen in the event source. | :material-minus-box-outline: Optional | `None` |
| password | Keyword | Password of the request. | :material-minus-box-outline: Optional | `None` |
| path | Keyword | Path of the request, such as "/search". | :material-minus-box-outline: Optional | `None` |
| port | Integer | Port of the request, such as 443. | :material-minus-box-outline: Optional | `None` |
| query | Keyword | The query field describes the query string of the request, such as "q=elasticsearch". | :material-minus-box-outline: Optional | `None` |
| registered_domain | Keyword | The highest registered url domain, stripped of the subdomain. | :material-minus-box-outline: Optional | `None` |
| scheme | Keyword | Scheme of the request, such as "https". | :material-minus-box-outline: Optional | `None` |
| subdomain | Keyword | The subdomain portion of a fully qualified domain name includes all of the names except the host name under the registered_domain. | :material-minus-box-outline: Optional | `None` |
| top_level_domain | Keyword | The effective top level domain (eTLD), also known as the domain suffix, is the last part of the domain name. | :material-minus-box-outline: Optional | `None` |
| username | Keyword | Username of the request. | :material-minus-box-outline: Optional | `None` |
