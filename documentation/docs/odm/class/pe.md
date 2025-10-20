??? success "Auto-Generated Documentation"
    This set of documentation is automatically generated from source, and will help ensure any change to functionality will always be documented and available on release.

# PE

> These fields contain Windows Portable Executable (PE) metadata.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| architecture | Keyword | CPU architecture target for the file. | :material-minus-box-outline: Optional | `None` |
| company | Keyword | Internal company name of the file, provided at compile-time. | :material-minus-box-outline: Optional | `None` |
| description | Keyword | Internal description of the file, provided at compile-time. | :material-minus-box-outline: Optional | `None` |
| file_version | Keyword | Internal version of the file, provided at compile-time. | :material-minus-box-outline: Optional | `None` |
| imphash | Keyword | A hash of the imports in a PE file. | :material-minus-box-outline: Optional | `None` |
| original_file_name | Keyword | Internal name of the file, provided at compile-time. | :material-minus-box-outline: Optional | `None` |
| pehash | Keyword | A hash of the PE header and data from one or more PE sections. | :material-minus-box-outline: Optional | `None` |
| product | Keyword | Internal product name of the file, provided at compile-time. | :material-minus-box-outline: Optional | `None` |
