??? success "Auto-Generated Documentation"
    This set of documentation is automatically generated from source, and will help ensure any change to functionality will always be documented and available on release.

# CodeSignature

> These fields contain information about binary code signatures.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| digest_algorithm | Enum | The hashing algorithm used to sign the process.<br>Values:<br>`"md5", "sha1", "sha256", "sha384", "sha512"` | :material-minus-box-outline: Optional | `None` |
| exists | Boolean | Boolean to capture if a signature is present. | :material-minus-box-outline: Optional | `None` |
| signing_id | Keyword | The identifier used to sign the process. | :material-minus-box-outline: Optional | `None` |
| status | Keyword | Additional information about the certificate status. | :material-minus-box-outline: Optional | `None` |
| subject_name | Keyword | Subject name of the code signer. | :material-minus-box-outline: Optional | `None` |
| team_id | Keyword | The team identifier used to sign the process. | :material-minus-box-outline: Optional | `None` |
| timestamp | Date | Date and time when the code signature was generated and signed. | :material-minus-box-outline: Optional | `None` |
| trusted | Boolean | Stores the trust status of the certificate chain. | :material-minus-box-outline: Optional | `None` |
| valid | Boolean | Boolean to capture if the digital signature is verified against the binary content. | :material-minus-box-outline: Optional | `None` |
