# Triage Analysts

Howler is designed to consolidate alerts from all sources, and differentiates those that require triage from those that might not. Detection engineers are expected to normalize the alerts, so that they can all be looked up and compared with a common schema: Elastic Common Schema (ECS). By putting all of the alerts in one place under one schema, it's much easier to find correlating events that warrant scrutiny from a triage analyst. For example, an analyst can easily find all alerts related to a given source IP with a single filter criteria regardless of the schema of the original telemetry.

Howler demands that detection engineers explicitly outline the the who, what, when, where and why for each alert they produce. This means that triage analysts aren't presented with cryptic alerts that provide no clue how to validate them. For example, the *threat* and *target* fields make it clear who is attacking whom.

The next big improvement offered by Howler is customization. Each type of event can have a custom presentation, so we don't flood the triage analyst's screen with unimportant information or leave important details tucked away behind multiple clicks. For example, with some alerts, the HTTP referrer field might be critical, but in others it may be meaningless.

Howler supports automation through matching alerts to filters. If a new alert matches the prepared filter, the specified actions will automatically be carried out. These include prioritization, tagging and assessments to name a few. If an analyst keeps seeing alerts for the same sys-admin script that they know is legitimate activity, they might add an action to apply a "sys-admin" tag to alerts that match a carefully tailored filter. Then, they might decide to automatically assess any alert with a "sys-admin" tag as "legitimate" to avoid wasting effort triaging them.

All of these capabilities combine to provide triage teams with a comprehensive suite of tools that enable them to process more alerts in greater detail.

## Hits

A lot of detected events are only weak-indicators and aren't worth the effort to triage individually, so we refer to them as **hits**. Howler uses the term **alert** to describe the subset that should be triaged. Any that are assessed as inaccurate (false-positive) can be demoted to **miss** while those that are assess as accurate are promoted to **evidence**.

Their continuum of escalation is as such: **miss** -> **hit** -> **alert** -> **evidence**

In most cases, triage analysts are concerned with alerts, which they promote to evidence or demote to a miss. To review alerts, a triage analyst navigates to the **Alerts** page from the left side-bar. There, they are presented with a filter box. The syntax for the filter is Lucene. The schema of the data is Elastic Common Schema (ECS).

To filter for a certain escalation, filter on `howler.escalation`. For example, to look at alerts, write: `howler.escalation: alert`.

## Hit Cards

The Howler UI displays an abbreviated version of each hit as a card. This is designed in a way to reduce the amount of effort required for a triage analyst to understand the nature of the hit and its context.

### Banner

The banner at the top of each hit provides standardized context addressing the who, what, when, where and why.

#### Title

The title on the card is the analytic and detection that created the hit. The software product that created the hit is called the **analytic**. The logic finding and selecting specific events is called the **detection**. One analytic can have many detections. These two concepts are expressed in the `howler.analytic` and `howler.detection` fields.

You can filter for hits belonging to a specific detection. For example, to look at hits produced by a detection called "User Creds Beacon", write: `howler.detection: "User Creds Beacon"`.

#### Icon

The name represents the affected organization, department or team. It is stored in `organization.name`.
The left of the banner is coloured based on the event collection mechanism. This is determined by the `event.provider` field.
The picture represents the Mitre ATT&CK Framework specified in `threat.tactic.id` or `threat.technique.id`.

#### Status

To the right of the banner is the status. This has a timestamp, the user the hit is assigned to and the escalation for the hit. Additionally, if other users are currently reviewing this hit, their icon will appear in this section.

#### Context

The lower part of the banner provides the key aspects of context needed to understand the hit.

##### Threat

The identifier that best represents the attacker. This could be an IP, email address, etc...
Use this to find other hits that appear to come from the same attacker. (`howler.outline.threat`)

##### Target

The identifier that best represents the attacker. This could be an IP, email address, etc...
User this to find other hits that appear to affect the same victim. (`howler.outline.target`)

##### Indicators

A free-form list of indicators of compromise (IoC). These are typically IPs, domains and hashes.
Use this to find related attacks based on their infrastructure and tactics. (`howler.outline.indicators`)

##### Summary

An executive summary explaining the activity that is being detected. When assessing a hit, you are try to corroborate or refute this very statement. (`howler.outline.summary`)

### Details

This section can show additional metadata contained in an alert. The fields shown should be the ones that are most important for making an assessment of that particular detection.

## Templates

Templates are the mechanism used to customize which fields are displayed in a hit card's details section.
On the top right of the details section of a hit card is an icon specifying whether you are currently viewing a global or personal template. Clicking on this icon will allow you to modify the template.

Here you can specify whether you are creating a template for all hits from a given analytic, or optionally, that it is only for hits from a specific detection.

You can make it a personal filter that only affects the hit cards you're seeing. This will override any global filter. If you make your filter global, it will affect the template of any user who hasn't created a personal template.

When designing a template, you can add or delete any field found in the hit's metadata. All those present will be displayed in the details of hits matching from the analytic or detection. Avoid adding fields that aren't necessary for an assessment as they will slow down the rate at which analysts can interpret the hit card.

## Dossier

Clicking on a hit card will open its dossier on the right side of the Howler UI. A series of tabs provide additional information about a given hit. At the top is the same banner found at the top of a hit card. If the detection engineer has provided integration with external tools, their button (image) will appear below the banner.

### Comments

This section allows you to write comments for yourself or colleagues.

### JSON

This will show you a JSON representation of the hit's metadata, including all fields that the detection engineer mapped to ECS.

### Raw Data

This is the raw event that was identified by the detection. This will be a list of events if multiple are involved. Use this if you need to continue your investigation outside of Howler. It will show the original field names before mapping to ECS, so that you're able to build the right queries.

### Worklog

All changes made to a given hit are logged here.

### Related Links

These are provided if they offer additional useful context that couldn't be integrated with Howler.

### Controls

At the bottom of the dossier are a series of controls that allow analysts affect hits in various ways.

#### Manage

- **Promote**: Go from hit to alert
- **Demote**: Go from alert to hit
- **Assign To Me**: Signal to others that you will assess this hit.
- **Delegate**: Signal to an individual or team that they should assess this hit.
- **Release**: Return this hit to unassigned.
- **Pause**: Signal that you are delaying your assessment.
- **Resume**: Signal you are once again working on your assessment.

The options here change based on the current state of a hit, so you will only see a few choices at any given moment.

#### Assess

This is where you can indicate a final verdict for your investigation. (`howler.assessment`)

- **Ambiguous**: There wasn't enough information to make an assessment.
- **Security**: The event is authorized cyber-security activity like training exercises.
- **Development**: The hit is for development purposes and should be ignored.
- **False-Positive**: The event is not indicative of the circumstances the detection is looking for.
- **Legitimate**: The event is authorized activity.
- **Trivial**: The impact of the event is not significant enough to merit mitigation.
- **Recon**: The event represents reconnaissance, but put does not pose an imminent threat.
- **Attempt**: There event represents an attempted attack that doesn't appear to have succeeded.
- **Compromise**: The event represents a successful compromise that must be mitigated.
- **Mitigated**: The event represents a successful compromise for which mitigating action is underway.

**Rationale**: Once you add an assessment, you're asked to provide a rationale as free-form text. This is a quick summary explaining to your colleagues, or your future-self, why you have confidence in that assessment. (`howler.rationale`)

#### Vote

In instances where an analyst doesn't have enough information to make a confident assessment, but they they have a "gut feeling" about the event, they can place a vote. It's up to the triage team to decide how they use the votes, but one suggestions could be that a consensus in votes can be used to make an assessment. (`howler.votes.bening/obscure/malicious`)

## Views

Writing filters can be time consuming. Triage analysts often need to use the same filters for their workflow. Howler streamlines this through views. After writing a filter, click the heart icon to the right of the filter and specify a name. Now that view can be accessed from the **View Manager** on the left side-bar. If you click on the star to the right of a filter here, it will appear under **Saved Views** in the left side-bar.

### Global Views

Members of a teams often rely on the same filters. By specifying a view as **global** during it's creation, other users will see this view in the Global Views page under the GLOBAL filter.

## Bundles

In instances where multiple events appear to be related to each-other, they can be packaged together as a bundle. This is a special type of hit that points to other hits. They can be identified by the `howler.is_bundle:true` filter. The related hits can be found in the `howler.hits` list which contains the `howler.id` value of each.

When a triage analysts clicks on a bundle's card, the banner for the bundle is moved above the filter bar and the bundle hits' cards are displayed under the filter bar. Any filter provided will only apply to the hits associated with the bundle.

Any controls used on the bundle will automatically be propagated to its related hits.

A good example of hits you'd want to bundle would be a sequence of hits occurring on the same host within a short window of time. Individually, those hits might be far too unreliable to consider triaging them, but with the added context that several of them happening on the same host in a short time window, it would be reasonable to automatically promote the bundle to alert to ensure someone triages it. By bundling them, we ensure that not only does a triage analyst review the host, but knows of all other potentially related activity taking place.

### Bundle Summary

Bundles have an additional tab in the bundle's dossier called **Summary**. If you click the Create Summary button, it will count the distinct values of each filed of the hits. Use this to get an idea of the overall situation.
