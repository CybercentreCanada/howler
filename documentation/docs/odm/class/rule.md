??? success "Auto-Generated Documentation"
    This set of documentation is automatically generated from source, and will help ensure any change to functionality will always be documented and available on release.

# Rule

> Rule fields are used to capture the specifics of any observer or agent rules that generate alerts or other notable events.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| author | Keyword | Name, organization, or pseudonym of the author or authors who created the rule used to generate this event. | :material-minus-box-outline: Optional | `None` |
| category | Keyword | A categorization value keyword used by the entity using the rule for detection of this event. | :material-minus-box-outline: Optional | `None` |
| description | Keyword | The description of the rule generating the event. | :material-minus-box-outline: Optional | `None` |
| id | Keyword | A rule ID that is unique within the scope of an agent, observer, or other entity using the rule for detection of this event. | :material-minus-box-outline: Optional | `None` |
| license | Keyword | Name of the license under which the rule used to generate this event is made available. | :material-minus-box-outline: Optional | `None` |
| name | Keyword | The name of the rule or signature generating the event. | :material-minus-box-outline: Optional | `None` |
| reference | Keyword | Reference URL to additional information about the rule used to generate this event. | :material-minus-box-outline: Optional | `None` |
| ruleset | Keyword | Name of the ruleset, policy, group, or parent category in which the rule used to generate this event is a member. | :material-minus-box-outline: Optional | `None` |
| uuid | Keyword | A rule ID that is unique within the scope of a set or group of agents, observers, or other entities using the rule for detection of this event. | :material-minus-box-outline: Optional | `None` |
| version | Keyword | The version / revision of the rule being used for analysis. | :material-minus-box-outline: Optional | `None` |
