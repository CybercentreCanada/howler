??? success "Auto-Generated Documentation"
    This set of documentation is automatically generated from source, and will help ensure any change to functionality will always be documented and available on release.

# Threat

> Fields to classify events and alerts according to a threat taxonomy such as the MITRE ATT&CK® framework.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| feed | [Feed](/howler-docs/odm/class/feed) | Threat feed information. | :material-minus-box-outline: Optional | `None` |
| framework | Keyword | Name of the threat framework used to further categorize and classify the tactic and technique of the reported threat. | :material-minus-box-outline: Optional | `None` |
| group | [Group](/howler-docs/odm/class/group) | Information about the group related to this threat. | :material-minus-box-outline: Optional | `None` |
| indicator | [Indicator](/howler-docs/odm/class/indicator) | Object containing associated indicators enriching the event. | :material-minus-box-outline: Optional | `None` |
| software | [Software](/howler-docs/odm/class/software) | Information about the software used by this threat. | :material-minus-box-outline: Optional | `None` |
| tactic | [Tactic](/howler-docs/odm/class/tactic) | Information about the tactic used by this threat. | :material-minus-box-outline: Optional | `None` |
| technique | [Tactic](/howler-docs/odm/class/tactic) | Information about the technique used by this threat. | :material-minus-box-outline: Optional | `None` |
