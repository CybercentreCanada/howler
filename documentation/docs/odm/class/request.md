??? success "Auto-Generated Documentation"
    This set of documentation is automatically generated from source, and will help ensure any change to functionality will always be documented and available on release.

# Request

> These fields can represent errors of any kind.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| body | [Body](/howler-docs/odm/class/body) | Defines the body of a request | :material-minus-box-outline: Optional | `None` |
| bytes | Integer | Total size in bytes of the request (body and headers). | :material-minus-box-outline: Optional | `None` |
| id | Keyword | A unique identifier for each HTTP request to correlate logs between clients and servers in transactions. | :material-minus-box-outline: Optional | `None` |
| method | Keyword | HTTP request method. | :material-minus-box-outline: Optional | `None` |
| mime_type | Keyword | Mime type of the body of the request. | :material-minus-box-outline: Optional | `None` |
| referrer | Keyword | Referrer for this HTTP request. | :material-minus-box-outline: Optional | `None` |
