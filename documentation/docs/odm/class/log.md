??? success "Auto-Generated Documentation"
    This set of documentation is automatically generated from source, and will help ensure any change to functionality will always be documented and available on release.

# Log

> Log definition.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| timestamp | Date | Timestamp at which the Log event took place. | :material-checkbox-marked-outline: Yes | `None` |
| key | Keyword | The key whose value changed. | :material-minus-box-outline: Optional | `None` |
| explanation | Text | A manual description of the changes made. | :material-minus-box-outline: Optional | `None` |
| previous_version | Keyword | The version this action was applied to. | :material-minus-box-outline: Optional | `None` |
| new_value | Keyword | The value the key is changing to. | :material-minus-box-outline: Optional | `None` |
| type | Enum | The operation performed on the value.<br>Values:<br>`"appended", "removed", "set"` | :material-minus-box-outline: Optional | `None` |
| previous_value | Keyword | The value the key is changing from. | :material-minus-box-outline: Optional | `None` |
| user | Keyword | User ID who created the log event. | :material-checkbox-marked-outline: Yes | `None` |
