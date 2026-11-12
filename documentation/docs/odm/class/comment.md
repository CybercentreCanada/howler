??? success "Auto-Generated Documentation"
    This set of documentation is automatically generated from source, and will help ensure any change to functionality will always be documented and available on release.

# Comment

> Comment definition.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| id | UUID | A unique ID for the comment. | :material-checkbox-marked-outline: Yes | `None` |
| timestamp | Date | Timestamp at which the comment took place. | :material-checkbox-marked-outline: Yes | `NOW` |
| modified | Date | Timestamp at which the comment was last edited. | :material-checkbox-marked-outline: Yes | `NOW` |
| value | Text | The comment itself. | :material-checkbox-marked-outline: Yes | `None` |
| user | Keyword | User ID who created the comment. | :material-checkbox-marked-outline: Yes | `None` |
| reactions | Mapping [Keyword] | A list of reactions to the comment. | :material-checkbox-marked-outline: Yes | `{}` |
