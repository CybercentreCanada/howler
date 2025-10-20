??? success "Auto-Generated Documentation"
    This set of documentation is automatically generated from source, and will help ensure any change to functionality will always be documented and available on release.

# HowlerData

> Howler specific definition of the hit that matches the outline.

| Field | Type | Description | Required | Default |
| :--- | :--- | :--- | :--- | :--- |
| id | UUID | A UUID for this hit. | :material-checkbox-marked-outline: Yes | `None` |
| analytic | Keyword | Title of the analytic. | :material-checkbox-marked-outline: Yes | `None` |
| assignment | Keyword | Unique identifier of the assigned user. | :material-checkbox-marked-outline: Yes | `unassigned` |
| bundles | List [Keyword] | A list of bundle IDs this hit is a part of. Corresponds to the howler.id of the bundle. | :material-checkbox-marked-outline: Yes | `[]` |
| data | List [Keyword] | Raw telemetry records associated with this hit. | :material-checkbox-marked-outline: Yes | `[]` |
| links | List [[Link](/howler-docs/odm/class/link)] | A list of links associated with this hit. | :material-checkbox-marked-outline: Yes | `[]` |
| detection | Keyword | The detection that produced this hit. | :material-minus-box-outline: Optional | `None` |
| hash | SHA256 | A hash of the event used for deduplicating hits. | :material-checkbox-marked-outline: Yes | `None` |
| hits | List [Keyword] | A list of hit IDs this bundle represents. Corresponds to the howler.id of the child hit. | :material-checkbox-marked-outline: Yes | `[]` |
| is_bundle | Boolean | Is this hit a bundle or a normal hit? | :material-checkbox-marked-outline: Yes | `False` |
| related | List [Keyword] | Related hits grouped by the enrichment that correlated them. Populated by enrichments. | :material-checkbox-marked-outline: Yes | `[]` |
| reliability | Float | Metric decoupled from the value in the detection information. | :material-minus-box-outline: Optional | `None` |
| severity | Float | Metric decoupled from the value in the detection information. | :material-minus-box-outline: Optional | `None` |
| volume | Float | Metric decoupled from the value in the detection information. | :material-minus-box-outline: Optional | `None` |
| confidence | Float | Metric decoupled from the value in the detection information. | :material-minus-box-outline: Optional | `None` |
| score | Float | A score assigned by an enrichment to help prioritize triage. | :material-checkbox-marked-outline: Yes | `None` |
| status | Enum | Status of the hit.<br>Values:<br>`"in-progress", "on-hold", "open", "resolved"` | :material-checkbox-marked-outline: Yes | `open` |
| scrutiny | Enum | Level of scrutiny done to this hit.<br>Values:<br>`"inspected", "investigated", "scanned", "surveyed", "unseen"` | :material-checkbox-marked-outline: Yes | `unseen` |
| escalation | Enum | Level of escalation of this hit.<br>Values:<br>`"alert", "evidence", "hit", "miss"` | :material-checkbox-marked-outline: Yes | `hit` |
| assessment | Enum | Assessment of the hit.<br>Values:<br>`"ambiguous", "attempt", "compromise", "development", "false-positive", "legitimate", "mitigated", "recon", "security", "trivial"` | :material-minus-box-outline: Optional | `None` |
| rationale | Text | The rationale behind the hit assessment. Allows it to be understood and verified by other analysts. | :material-minus-box-outline: Optional | `None` |
| comment | List [[Comment](/howler-docs/odm/class/comment)] | A list of comments with timestamps and attribution. | :material-checkbox-marked-outline: Yes | `[]` |
| log | List [[Log](/howler-docs/odm/class/log)] | A list of changes to the hit with timestamps and attribution. | :material-checkbox-marked-outline: Yes | `[]` |
| retained | Keyword | If the hit was retained, this is a link to it in Alfred. | :material-minus-box-outline: Optional | `None` |
| monitored | Keyword | Link to the incident monitoring dashboard. | :material-minus-box-outline: Optional | `None` |
| reported | Keyword | Link to the incident report. | :material-minus-box-outline: Optional | `None` |
| mitigated | Keyword | Link to the mitigation record (tool dependent). | :material-minus-box-outline: Optional | `None` |
| outline | [Header](/howler-docs/odm/class/header) | The user specified header of the hit | :material-minus-box-outline: Optional | `None` |
| labels | [Label](/howler-docs/odm/class/label) | List of labels relating to the hit | :material-minus-box-outline: Optional | See [Label](/howler-docs/odm/class/label) for more details. |
| votes | [Votes](/howler-docs/odm/class/votes) | Votes relating to the hit | :material-minus-box-outline: Optional | See [Votes](/howler-docs/odm/class/votes) for more details. |
| dossier | FlattenedObject | Raw data provided by the different sources. | :material-minus-box-outline: Optional | `None` |
| viewers | List [Keyword] | A list of users currently viewing the hit | :material-checkbox-marked-outline: Yes | `[]` |
