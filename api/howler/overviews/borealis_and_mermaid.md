This is an example overview with a detail panel outlining salient details (including enrichment through borealis) of the alert, as well as a basic mermaid diagram.

| **Details** | |
| --- | --- |
| Date Range | <p style="background-color: #d3d3d354;padding: 4px;margin:-10px;width: fit-content;border-radius: 15px;">{{event.start}} TO {{event.end}}</p> |
| Threat Domain | <p style="background-color: #d91c2554;padding: 4px;margin:-10px;width: fit-content;border-radius: 15px;">{{borealis "domain" howler.outline.threat}}</p> |
| Threat IP | <p style="background-color: #d91c2554;padding: 4px;margin:-10px;width: fit-content;border-radius: 15px;">{{borealis "ip" destination.ip}}</p> |
| Affected User | <p style="background-color: #1c92d938;padding: 4px;margin:-10px;width: fit-content;border-radius: 15px;">{{borealis "eml_address" howler.outline.target}}</p> |
| User Agent |  <p style="background-color: #d3d3d354;padding: 4px;margin:-10px;width: fit-content;border-radius: 15px;">{{user_agent.original}}</p> |
| Application | <p style="background-color: #d3d3d354;padding: 4px;margin:-10px;width: fit-content;border-radius: 15px;">{{cloud.service.name}}</p> |
| Error | <p style="background-color: #d3d3d354;padding: 4px;margin:-10px;width: fit-content;border-radius: 15px;">{{error.code}} --> {{error.message}}</p> |

</br>

| **Actions** | |
| --- | --- |
| Search for `{{howler.outline.threat}}` | <https://example.com> |
| Look for Emails to `{{howler.outline.target}}` | <https://example.com> |
| Triage Help | <https://example.com> |

</br>

#### Visualization

```mermaid
sequenceDiagram
    actor User
    User->>MITM Actor - {{howler.outline.threat}} ({{destination.ip}}): Connects to AiTM Site
    MITM Actor - {{howler.outline.threat}} ({{destination.ip}})->>Entra ID: Starts login on bahalf of the user
    Entra ID->>MITM Actor - {{howler.outline.threat}} ({{destination.ip}}): Returns Login Page
    MITM Actor - {{howler.outline.threat}} ({{destination.ip}})->>User: Shows User the Entra Login Page
    User->>MITM Actor - {{howler.outline.threat}} ({{destination.ip}}): User Enters Username/Password
    MITM Actor - {{howler.outline.threat}} ({{destination.ip}})->>Entra ID: Proxies Username/Password
    Entra ID->>MITM Actor - {{howler.outline.threat}} ({{destination.ip}}): Returns MFA Prompt
    MITM Actor - {{howler.outline.threat}} ({{destination.ip}})->>User: Shows User the MFA Prompt
    User->>MITM Actor - {{howler.outline.threat}} ({{destination.ip}}): User Completes MFA
    MITM Actor - {{howler.outline.threat}} ({{destination.ip}})->>Entra ID: Proxies completed MFA
    Entra ID->>MITM Actor - {{howler.outline.threat}} ({{destination.ip}}): Returns Error Code (If an error occured)
    Entra ID->>MITM Actor - {{howler.outline.threat}} ({{destination.ip}}): Returns MFA verified Token (if no error occured)
    MITM Actor - {{howler.outline.threat}} ({{destination.ip}})->>User: Redirects User Somewhere else
```
