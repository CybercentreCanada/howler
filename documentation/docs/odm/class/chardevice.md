??? success "Auto-Generated Documentation"
    This set of documentation is automatically generated from source, and will help ensure any change to functionality will always be documented and available on release.

# CharDevice

> Information about the char device.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| major | Integer | The major number identifies the driver associated with the device. | :material-minus-box-outline: Optional | `None` |
| minor | Integer | The minor number is used only by the driver specified by the major number; other parts of the kernel don’t use it, and merely pass it along to the driver. | :material-minus-box-outline: Optional | `None` |
