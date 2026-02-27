<details>
<summary>More details</summary>
Phishing email from <b>john.smith@live.ca</b> (subject: "John Smith Law Corporation") targeting <b>tony.stark@gov.com</b>. The email contained a malicious link to <code>sharefile08.s3.us-east-1.amazonaws.com/document20251021_0101001.html</code>. On host <b>DESKTOP-TONY01</b>, <code>outlook.exe</code> (PID 7344) spawned <code>msedge.exe</code> (PID 10212) to open the SafeLinks-wrapped phishing URL. The attacker attempted to sign in with the stolen credentials but was blocked by Entra ID with error <b>AADSTS50074 – MFA Required</b>.
</details>

<h3>Phishing Email Flow</h3>


```mermaid

sequenceDiagram

  actor Attacker as john.smith@live.ca

  participant Inbox as tony.stark@gov.com

  participant Outlook as outlook.exe (PID 7344)

  participant Edge as msedge.exe (PID 10212)

  participant Phish as sharefile08.s3.us-east-1.amazonaws.com

  participant Entra as Entra ID

  Attacker->>Inbox: Sends phishing email<br/>"John Smith Law Corporation"

  Inbox->>Outlook: User opens email on DESKTOP-TONY01

  Note over Outlook: Parent: explorer.exe (PID 2140)<br/>Host: DESKTOP-TONY01

  Outlook->>Edge: Opens SafeLinks-wrapped URL

  Edge->>Phish: GET /document20251021_0101001.html

  Phish-->>Edge: Phishing page content

  Note over Phish: Credential harvesting page

  Phish->>Entra: Sign-in attempt with<br/>tony.stark@gov.com credentials

  Entra--xPhish: AADSTS50074 – MFA Required

```

<h3>Data</h3>

<table class="table_overview">

<tbody>

<tr>

<td style="padding:8px;font-weight:bold;">Analytic</td>

<td style="padding:8px;">Email Gateway</td>

</tr>

<tr>

<td style="padding:8px;font-weight:bold;">Detection</td>

<td style="padding:8px;">Suspicious Inbound Email</td>

</tr>

<tr>

<td style="padding:8px;font-weight:bold;">Threat</td>

<td style="padding:8px;">john.smith@live.ca</td>

</tr>

<tr>

<td style="padding:8px;font-weight:bold;">Target</td>

<td style="padding:8px;">tony.stark@gov.com</td>

</tr>

<tr>

<td style="padding:8px;font-weight:bold;">Subject</td>

<td style="padding:8px;">John Smith Law Corporation</td>

</tr>

<tr>

<td style="padding:8px;font-weight:bold;">Phishing URL</td>

<td style="padding:8px;">sharefile08.s3.us-east-1.amazonaws.com/document20251021_0101001.html</td>

</tr>

<tr>

<td style="padding:8px;font-weight:bold;">Host</td>

<td style="padding:8px;">DESKTOP-TONY01</td>

</tr>

</tbody>

</table>

<h3>Process Tree &amp; Network</h3>

```mermaid

graph LR

  Edge["msedge.exe<br/>(PID 2140)"] -- spawns --> Outlook["outlook.exe<br/>(PID 7344)"]

  Outlook -- spawns --> Edge["msedge.exe<br/>(PID 10212)"]

  Edge == "SafeLinks redirect" ==> Phish["sharefile08.s3.us-east-1<br/>.amazonaws.com"]

  Phish -. "/document20251021<br/>_0101001.html" .-> Edge

  Phish -- "Sign-in with stolen<br/>tony.stark credentials" --> Entra["Entra ID"]

  Entra -. "AADSTS50074: MFA Required" .-> Phish

  Email["john.smith@live.ca"] -- "Phishing email<br/>Subject: John Smith<br/>Law Corporation" --> Inbox["Email Gateway"]

  Inbox -- delivers --> Inbox["tony.stark@gov.com"]

  classDef red fill:#f96,stroke:#333,stroke-width:2px

  classDef blue fill:#32bedd,stroke:#333,stroke-width:2px

  classDef green fill:#28a745,stroke:#333,stroke-width:2px,color:#fff

  classDef orange fill:#f4a460,stroke:#333,stroke-width:2px

  class Email,Phish red

  class Inbox,Inbox,Entra blue

  class Explorer,Outlook,Edge green

```
