??? success "Auto-Generated Documentation"
    This set of documentation is automatically generated from source, and will help ensure any change to functionality will always be documented and available on release.

# ELF

> These fields contain Linux Executable Linkable Format (ELF) metadata.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| architecture | Keyword | Machine architecture of the ELF file. | :material-minus-box-outline: Optional | `None` |
| byte_order | Keyword | Byte sequence of ELF file. | :material-minus-box-outline: Optional | `None` |
| cpu_type | Keyword | CPU type of the ELF file. | :material-minus-box-outline: Optional | `None` |
| creation_date | Keyword | Extracted when possible from the file’s metadata. | :material-minus-box-outline: Optional | `None` |
| exports | List [Keyword] | List of exported element names and types. | :material-checkbox-marked-outline: Yes | `[]` |
| header | [Header](/howler-docs/odm/class/header) | Header information about the ELF file. | :material-minus-box-outline: Optional | `None` |
| imports | List [Keyword] | List of imported element names and types. | :material-minus-box-outline: Optional | `None` |
| sections | List [[Section](/howler-docs/odm/class/section)] | None | :material-minus-box-outline: Optional | `None` |
| segments | List [[Section](/howler-docs/odm/class/section)] | None | :material-minus-box-outline: Optional | `None` |
| shared_libraries | List [Keyword] | List of shared libraries used by this ELF object. | :material-minus-box-outline: Optional | `None` |
| telfhash | Keyword | telfhash symbol hash for ELF file. | :material-minus-box-outline: Optional | `None` |
