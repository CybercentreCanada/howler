??? success "Auto-Generated Documentation"
    This set of documentation is automatically generated from source, and will help ensure any change to functionality will always be documented and available on release.

# OS

> The OS fields contain information about the operating system.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| family | Keyword | OS family (such as redhat, debian, freebsd, windows). | :material-minus-box-outline: Optional | `None` |
| full | Keyword | Operating system name, including the version or code name. | :material-minus-box-outline: Optional | `None` |
| kernel | Keyword | Operating system kernel version as a raw string. | :material-minus-box-outline: Optional | `None` |
| name | Keyword | Operating system name, without the version. | :material-minus-box-outline: Optional | `None` |
| platform | Keyword | Operating system platform (such centos, ubuntu, windows). | :material-minus-box-outline: Optional | `None` |
| type | Keyword | Use the os.type field to categorize the operating system into one of the broad commercial families. | :material-minus-box-outline: Optional | `None` |
| version | Keyword | Operating system version as a raw string. | :material-minus-box-outline: Optional | `None` |
