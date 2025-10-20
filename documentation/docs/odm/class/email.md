??? success "Auto-Generated Documentation"
    This set of documentation is automatically generated from source, and will help ensure any change to functionality will always be documented and available on release.

# Email

> Event details relating to an email transaction.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| attachments | List [[Attachment](/howler-docs/odm/class/attachment)] | None | :material-minus-box-outline: Optional | `None` |
| bcc | [Address](/howler-docs/odm/class/address) | The email address of BCC recipient. | :material-minus-box-outline: Optional | `None` |
| cc | [Address](/howler-docs/odm/class/address) | The email address of CC recipient. | :material-minus-box-outline: Optional | `None` |
| content_type | Keyword | Information about how the message is to be displayed. | :material-minus-box-outline: Optional | `None` |
| delivery_timestamp | Date | The date and time when the email message was received by the service or client. | :material-minus-box-outline: Optional | `None` |
| direction | Keyword | The direction of the message based on the sending and receiving domains. | :material-minus-box-outline: Optional | `None` |
| from | [Address](/howler-docs/odm/class/address) | The email address of the sender, typically from the RFC 5322 From: header field. | :material-minus-box-outline: Optional | `None` |
| local_id | Keyword | Unique identifier given to the email by the source that created the event. | :material-minus-box-outline: Optional | `None` |
| message_id | Keyword | Identifier from the RFC 5322 Message-ID: email header that refers to a particular email message. | :material-minus-box-outline: Optional | `None` |
| origination_timestamp | Date | The date and time the email message was composed. | :material-minus-box-outline: Optional | `None` |
| reply_to | [Address](/howler-docs/odm/class/address) | The address that replies should be delivered to based on the value in the RFC 5322 Reply-To: header. | :material-minus-box-outline: Optional | `None` |
| sender | [Address](/howler-docs/odm/class/address) | Per RFC 5322, specifies the address responsible for the actual transmission of the message. | :material-minus-box-outline: Optional | `None` |
| subject | Keyword | A brief summary of the topic of the message. | :material-minus-box-outline: Optional | `None` |
| to | [Address](/howler-docs/odm/class/address) | The email address of recipient. | :material-minus-box-outline: Optional | `None` |
| x_mailer | Keyword | The name of the application that was used to draft and send the original email message. | :material-minus-box-outline: Optional | `None` |
| parent | [ParentEmail](/howler-docs/odm/class/parentemail) | Metadata about the parent email. | :material-minus-box-outline: Optional | `None` |
