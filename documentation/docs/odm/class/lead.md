??? success "Auto-Generated Documentation"
    This set of documentation is automatically generated from source, and will help ensure any change to functionality will always be documented and available on release.

# Lead

> The dossier object stores individual tabs/fields for a given alert.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| icon | Text | An optional icon to use in the tab display for this dossier. | :material-minus-box-outline: Optional | `None` |
| label | [LocalizedLabel](/howler-docs/odm/class/localizedlabel) | Labels for the lead in the UI. | :material-checkbox-marked-outline: Yes | `None` |
| format | Enum | The format of the lead. <br>Values:<br>`"borealis", "markdown"` | :material-checkbox-marked-outline: Yes | `None` |
| content | Text | The data for the content. Could be a link, raw markdown text, or other valid lead format. | :material-checkbox-marked-outline: Yes | `None` |
| metadata | Json | Metadata associated with this dossier. Use varies based on format. | :material-minus-box-outline: Optional | `None` |


