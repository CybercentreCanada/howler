??? success "Auto-Generated Documentation"
    This set of documentation is automatically generated from source, and will help ensure any change to functionality will always be documented and available on release.

# Event

> The event fields are used for context information about the log or metric event itself.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| action | Keyword | The action captured by the event. | :material-minus-box-outline: Optional | `None` |
| category | List [Enum] | Represents the "big buckets" of ECS categories. For example, filtering on event.category:process yields all events relating to process activity. This field is closely related to event.type, which is used as a subcategory. | :material-minus-box-outline: Optional | `None` |
| code | Keyword | Identification code for this event, if one exists. | :material-minus-box-outline: Optional | `None` |
| created | Date | Contains the date/time when the event was first read by an agent, or by your pipeline. | :material-minus-box-outline: Optional | `None` |
| dataset | Keyword | Name of the dataset. | :material-minus-box-outline: Optional | `None` |
| duration | Integer | Duration of the event in nanoseconds. | :material-minus-box-outline: Optional | `None` |
| end | Date | Contains the date when the event ended or when the activity was last observed. | :material-minus-box-outline: Optional | `None` |
| hash | Keyword | Hash (perhaps logstash fingerprint) of raw field to be able to demonstrate log integrity. | :material-minus-box-outline: Optional | `None` |
| id | Keyword | Unique ID to describe the event. | :material-minus-box-outline: Optional | `None` |
| ingested | Date | Timestamp when an event arrived in the central data store. | :material-checkbox-marked-outline: Yes | `NOW` |
| kind | Enum | Gives high-level information about what type of information the event contains, without being specific to the contents of the event. <br>Values:<br>`"alert", "enrichment", "event", "metric", "pipeline_error", "signal", "state"` | :material-minus-box-outline: Optional | `None` |
| module | Keyword | Name of the module this data is coming from. | :material-minus-box-outline: Optional | `None` |
| original | Keyword | Raw text message of entire event. Used to demonstrate log integrity or where the full log message (before splitting it up in multiple parts) may be required, e.g. for reindex. | :material-minus-box-outline: Optional | `None` |
| outcome | Enum | Simply denotes whether the event represents a success or a failure from the perspective of the entity that produced the event.<br>Values:<br>`"failure", "success", "unknown"` | :material-minus-box-outline: Optional | `None` |
| provider | Keyword | Source of the event. | :material-minus-box-outline: Optional | `None` |
| reason | Keyword | Reason why this event happened, according to the source. | :material-minus-box-outline: Optional | `None` |
| reference | Keyword | Reference URL linking to additional information about this event. | :material-minus-box-outline: Optional | `None` |
| risk_score | Float | Risk score or priority of the event (e.g. security solutions). | :material-minus-box-outline: Optional | `None` |
| risk_score_norm | Float | Normalized risk score or priority of the event, on a scale of 0 to 100. | :material-minus-box-outline: Optional | `None` |
| sequence | Integer | Sequence number of the event. | :material-minus-box-outline: Optional | `None` |
| severity | Integer | The numeric severity of the event according to your event source. | :material-minus-box-outline: Optional | `None` |
| start | Date | Contains the date when the event started or when the activity was first observed. | :material-minus-box-outline: Optional | `None` |
| timezone | Keyword | This field should be populated when the event’s timestamp does not include timezone information already (e.g. default Syslog timestamps). | :material-minus-box-outline: Optional | `None` |
| type | List [Enum] | Represents a categorization "sub-bucket" that, when used along with the event.category field values, enables filtering events down to a level appropriate for single visualization. | :material-minus-box-outline: Optional | `None` |
| url | Keyword | URL linking to an external system to continue investigation of this event. | :material-minus-box-outline: Optional | `None` |
