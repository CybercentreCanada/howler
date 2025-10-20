??? success "Auto-Generated Documentation"
    This set of documentation is automatically generated from source, and will help ensure any change to functionality will always be documented and available on release.

# Indicator

> Object containing associated indicators enriching the event.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| confidence | Keyword | Identifies the vendor-neutral confidence rating using the None/Low/Medium/High scale defined in Appendix A of the STIX 2.1 framework. Vendor-specific confidence scales may be added as custom fields. | :material-minus-box-outline: Optional | `None` |
| description | Text | Describes the type of action conducted by the threat. | :material-minus-box-outline: Optional | `None` |
| email | [Email](/howler-docs/odm/class/email) | None | :material-minus-box-outline: Optional | `None` |
| provider | Keyword | The name of the indicator’s provider. | :material-minus-box-outline: Optional | `None` |
| reference | Keyword | Reference URL linking to additional information about this indicator. | :material-minus-box-outline: Optional | `None` |
| scanner_stats | Integer | Count of AV/EDR vendors that successfully detected malicious file or URL. | :material-minus-box-outline: Optional | `None` |
| sightings | Integer | Number of times this indicator was observed conducting threat activity. | :material-minus-box-outline: Optional | `None` |
| ip | IP | Identifies a threat indicator as an IP address (irrespective of direction). | :material-minus-box-outline: Optional | `None` |
| type | Keyword | Type of indicator as represented by Cyber Observable in STIX 2.0. | :material-minus-box-outline: Optional | `None` |
| first_seen | Date | The date and time when intelligence source first reported sighting this indicator. | :material-minus-box-outline: Optional | `None` |
| last_seen | Date | The date and time when intelligence source last reported sighting this indicator. | :material-minus-box-outline: Optional | `None` |
