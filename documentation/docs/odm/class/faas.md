??? success "Auto-Generated Documentation"
    This set of documentation is automatically generated from source, and will help ensure any change to functionality will always be documented and available on release.

# FAAS

> The user fields describe information about the function as a service (FaaS) that is relevant to the event.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| coldstart | Boolean | Boolean value indicating a cold start of a function. | :material-minus-box-outline: Optional | `None` |
| execution | Keyword | The execution ID of the current function execution. | :material-minus-box-outline: Optional | `None` |
| id | Keyword | The unique identifier of a serverless function. | :material-minus-box-outline: Optional | `None` |
| name | Keyword | The name of a serverless function. | :material-minus-box-outline: Optional | `None` |
| trigger | [Trigger](/howler-docs/odm/class/trigger) | Details about the function trigger. | :material-minus-box-outline: Optional | `None` |
| version | Keyword | The version of a serverless function. | :material-minus-box-outline: Optional | `None` |
