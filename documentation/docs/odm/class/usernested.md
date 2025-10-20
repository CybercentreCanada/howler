??? success "Auto-Generated Documentation"
    This set of documentation is automatically generated from source, and will help ensure any change to functionality will always be documented and available on release.

# UserNested

> The user fields describe information about the user that is relevant to the event.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| domain | Keyword | Name of the directory the user is a member of. | :material-minus-box-outline: Optional | `None` |
| email | Email | User email address. | :material-minus-box-outline: Optional | `None` |
| full_name | Keyword | User’s full name, if available. | :material-minus-box-outline: Optional | `None` |
| hash | Keyword | Unique user hash to correlate information for a user in anonymized form. | :material-minus-box-outline: Optional | `None` |
| id | Keyword | Unique identifier of the user. | :material-minus-box-outline: Optional | `None` |
| name | Keyword | Short name or login of the user. | :material-minus-box-outline: Optional | `None` |
| roles | List [Keyword] | Array of user roles at the time of the event. | :material-minus-box-outline: Optional | `[]` |
