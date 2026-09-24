??? success "Auto-Generated Documentation"
    This set of documentation is automatically generated from source, and will help ensure any change to functionality will always be documented and available on release.

# RegistryData

> Fields related to data written to Windows Registry.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| bytes | Keyword | Original bytes written with base64 encoding. | :material-minus-box-outline: Optional | `None` |
| strings | List [Keyword] | Content when writing string types. | :material-minus-box-outline: Optional | `None` |
| type | Keyword | Standard registry type for encoding contents. | :material-minus-box-outline: Optional | `None` |
