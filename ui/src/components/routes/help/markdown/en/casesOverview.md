# Cases overview

Cases collect alerts, events, notes, links, and related investigations in one workspace. They provide a shared structure for tracking an investigation from its initial evidence through to resolution.

## Find a case

The **Cases** page searches case titles, summaries, participants, and task details. Narrow a large list by status, by participants or task assignees, and by the creation date. The assignee filter includes a **Myself** shortcut.

The initial status filter selects **Open** and **In Progress** only. Clear or change that filter to find **On Hold** or **Resolved** cases; a case missing from the initial results may simply be excluded by the filter.

Open a result to enter the case workspace. A case card summarizes its status, evidence-derived targets, indicators, and threats, participants, task progress, and the recorded time span when it is available.

## Create a case

From a hit or event, open the context menu and choose **Create Case**. This is especially useful after selecting multiple records: the creation dialog lets you give the case a title and short summary, select an escalation, and write an initial Markdown overview.

Each selected record has a suggested item title that you can adjust before creating the case. The evidence is added at the new case's root after the case is created; the creation dialog has no folder-placement selector. Create folders in the case sidebar afterward and drag the records into them. When adding records to an existing case with **Add to Case**, you can select an existing folder in that dialog.

## Access to evidence

Each case has its own classification ceiling, which defaults to the deployment's unrestricted classification. Creating a case from selected records does not automatically inherit or raise that classification. The creation dialog has no classification selector; case classification can be set through the case API.

To manually add a hit or event, you must have access to both the case and the source record, and the case's classification must permit that record's classification. A record above the case's classification ceiling is rejected, not simply hidden after addition. Evidence items retain their source classification. You need access to the case itself to open its workspace; within an accessible case, items above your access level are omitted.
