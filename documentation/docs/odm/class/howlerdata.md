??? success "Auto-Generated Documentation"
    This set of documentation is automatically generated from source, and will help ensure any change to functionality will always be documented and available on release.

# HowlerData

> Howler specific definition of the hit that matches the outline.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| id | UUID | A UUID for this hit. | :material-checkbox-marked-outline: Yes | `None` |
| analytic | CaseInsensitiveKeyword | Title of the analytic. | :material-checkbox-marked-outline: Yes | `None` |
| assignment | Keyword | Unique identifier of the assigned user. | :material-checkbox-marked-outline: Yes | `unassigned` |
| bundles | List [Keyword] | None | :material-checkbox-marked-outline: Yes | `[]` |
| data | List [Keyword] | None | :material-checkbox-marked-outline: Yes | `[]` |
| links | List [[Link](/howler/odm/class/link)] | A list of links associated with this hit. | :material-checkbox-marked-outline: Yes | `[]` |
| detection | CaseInsensitiveKeyword | The detection that produced this hit. | :material-minus-box-outline: Optional | `None` |
| hash | HowlerHash | A hash of the event used for deduplicating hits. Supports any hexadecimal string between 1 and 64 characters long. | :material-checkbox-marked-outline: Yes | `None` |
| hits | List [Keyword] | None | :material-checkbox-marked-outline: Yes | `[]` |
| bundle_size | Integer | Number of hits in bundle | :material-checkbox-marked-outline: Yes | `0` |
| is_bundle | Boolean | Is this hit a bundle or a normal hit? | :material-checkbox-marked-outline: Yes | `False` |
| related | List [Keyword] | None | :material-checkbox-marked-outline: Yes | `[]` |
| reliability | Float | Metric decoupled from the value in the detection information. | :material-minus-box-outline: Optional | `None` |
| severity | Float | Metric decoupled from the value in the detection information. | :material-minus-box-outline: Optional | `None` |
| volume | Float | Metric decoupled from the value in the detection information. | :material-minus-box-outline: Optional | `None` |
| confidence | Float | Metric decoupled from the value in the detection information. | :material-minus-box-outline: Optional | `None` |
| score | Float | A score assigned by an enrichment to help prioritize triage. | :material-minus-box-outline: Optional | `0` |
| status | Enum | Status of the hit.<br>Values:<br>`"in-progress", "on-hold", "open", "resolved"` | :material-checkbox-marked-outline: Yes | `open` |
| scrutiny | Enum | Level of scrutiny done to this hit.<br>Values:<br>`"inspected", "investigated", "scanned", "surveyed", "unseen"` | :material-checkbox-marked-outline: Yes | `unseen` |
| escalation | Enum | Level of escalation of this hit.<br>Values:<br>`"alert", "evidence", "hit", "miss"` | :material-checkbox-marked-outline: Yes | `hit` |
| expiry | Date | User selected time for hit expiry | :material-minus-box-outline: Optional | `None` |
| assessment | Enum | Assessment of the hit.<br>Values:<br>`"ambiguous", "attempt", "compromise", "development", "false-positive", "legitimate", "mitigated", "recon", "security", "trivial"` | :material-minus-box-outline: Optional | `None` |
| rationale | Text | The rationale behind the hit assessment. Allows it to be understood and verified by other analysts. | :material-minus-box-outline: Optional | `None` |
| comment | List [[Comment](/howler/odm/class/comment)] | A list of comments with timestamps and attribution. | :material-checkbox-marked-outline: Yes | `[]` |
| log | List [[Log](/howler/odm/class/log)] | A list of changes to the hit with timestamps and attribution. | :material-checkbox-marked-outline: Yes | `[]` |
| monitored | Keyword | Link to the incident monitoring dashboard. | :material-minus-box-outline: Optional | `None` |
| reported | Keyword | Link to the incident report. | :material-minus-box-outline: Optional | `None` |
| mitigated | Keyword | Link to the mitigation record (tool dependent). | :material-minus-box-outline: Optional | `None` |
| outline | [Header](/howler/odm/class/header) | The user specified header of the hit | :material-minus-box-outline: Optional | `None` |
| incidents | List [[Incident](/howler/odm/class/incident)] | Fields describing an incident associated with this alert. | :material-checkbox-marked-outline: Yes | `[]` |
| labels | [Label](/howler/odm/class/label) | List of labels relating to the hit | :material-minus-box-outline: Optional | See [Label](/howler/odm/class/label) for more details. |
| votes | [Votes](/howler/odm/class/votes) | Votes relating to the hit | :material-minus-box-outline: Optional | See [Votes](/howler/odm/class/votes) for more details. |
| dossier | List [[Lead](/howler/odm/class/lead)] | A list of leads forming the dossier associated with this hit | :material-checkbox-marked-outline: Yes | `[]` |
| viewers | List [Keyword] | None | :material-checkbox-marked-outline: Yes | `[]` |
