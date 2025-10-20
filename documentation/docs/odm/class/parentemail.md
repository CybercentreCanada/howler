??? success "Auto-Generated Documentation"
    This set of documentation is automatically generated from source, and will help ensure any change to functionality will always be documented and available on release.

# ParentEmail

> Metadata about the parent email.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| bcc | [Address](/howler-docs/odm/class/address) | The email address of BCC recipient. | :material-minus-box-outline: Optional | `None` |
| cc | [Address](/howler-docs/odm/class/address) | The email address of CC recipient. | :material-minus-box-outline: Optional | `None` |
| from | [Address](/howler-docs/odm/class/address) | The email address of the sender, typically from the RFC 5322 From: header field. | :material-minus-box-outline: Optional | `None` |
| message_id | Keyword | Identifier from the RFC 5322 Message-ID: email header that refers to a particular email message. | :material-minus-box-outline: Optional | `None` |
| origination_timestamp | Date | The date and time the email message was composed. | :material-minus-box-outline: Optional | `None` |
| subject | Keyword | A brief summary of the topic of the message. | :material-minus-box-outline: Optional | `None` |
| to | [Address](/howler-docs/odm/class/address) | The email address of recipient. | :material-minus-box-outline: Optional | `None` |
| source | IP | The ip the email originated from. | :material-minus-box-outline: Optional | `None` |
| destination | IP | The ip the email was sent to. | :material-minus-box-outline: Optional | `None` |
