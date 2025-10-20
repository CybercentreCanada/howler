??? success "Auto-Generated Documentation"
    This set of documentation is automatically generated from source, and will help ensure any change to functionality will always be documented and available on release.

# Process

> These fields contain information about a process.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| args | List [Keyword] | Array of process arguments, starting with the absolute path to the executable. | :material-minus-box-outline: Optional | `None` |
| args_count | Integer | Length of the process.args array. | :material-minus-box-outline: Optional | `None` |
| command_line | Keyword | Full command line that started the process, including the absolute path to the executable, and all arguments. | :material-minus-box-outline: Optional | `None` |
| end | Date | None | :material-minus-box-outline: Optional | `None` |
| entity_id | Keyword | Unique identifier for the process. | :material-minus-box-outline: Optional | `None` |
| env_vars | Mapping [Keyword] | Environment variables (env_vars) set at the time of the event. May be filtered to protect sensitive information. | :material-minus-box-outline: Optional | `None` |
| executable | Keyword | Absolute path to the process executable. | :material-minus-box-outline: Optional | `None` |
| exit_code | Integer | The exit code of the process, if this is a termination event. | :material-minus-box-outline: Optional | `None` |
| interactive | Boolean | Whether the process is connected to an interactive shell. | :material-minus-box-outline: Optional | `None` |
| name | Keyword | Process name. | :material-minus-box-outline: Optional | `None` |
| parent | List [[ParentProcess](/howler-docs/odm/class/parentprocess)] | Information about the parent process. | :material-minus-box-outline: Optional | `None` |
| pid | Integer | Process id. | :material-minus-box-outline: Optional | `None` |
| same_as_process | Boolean | This boolean is used to identify if a leader process is the same as the top level process. | :material-minus-box-outline: Optional | `None` |
| start | Date | The time the process started. | :material-minus-box-outline: Optional | `None` |
| title | Keyword | Process title. | :material-minus-box-outline: Optional | `None` |
| uptime | Integer | Seconds the process has been up. | :material-minus-box-outline: Optional | `None` |
| user | [ShortUser](/howler-docs/odm/class/shortuser) | The effective user (euid). | :material-minus-box-outline: Optional | `None` |
| working_directory | Keyword | The working directory of the process. | :material-minus-box-outline: Optional | `None` |
