# Cases overview

Cases collect alerts, events, notes, links, and related investigations in one workspace. They provide a shared structure for tracking an investigation from its initial evidence through to resolution.

## Searching For Cases

The **Cases** page searches case titles, summaries, participants, and task details. Narrow a large list by status, participants, task assignees, or creation date. The assignee filter includes a **Myself** shortcut.

The initial status filter selects **Open** and **In Progress** only. Clear or change that filter to find **On Hold** or **Resolved** cases.

Open a result to enter the case workspace. A case card summarizes:

- Status
- Participants
- Task progress
- Recorded time span (when available).

## Create a Case

From a hit or event, open the context menu and choose **Create Case**. This is especially useful after selecting multiple records: the creation dialog lets you give the case a title and short summary, select an escalation, and write an initial Markdown overview.

Each selected record has a suggested item title that you can adjust before creating the case. The evidence is added at the new case's root after the case is created; the creation dialog has no folder-placement selector. Create folders in the case sidebar afterward and drag the records into them. When adding records to an existing case with **Add to Case**, you can select an existing folder in that dialog.

## Access to Evidence

Each case has its own classification ceiling, which defaults to the deployment's unrestricted classification. Creating a case from selected records does not automatically inherit or raise that classification. The creation dialog has no classification selector; case classification can be set through the case API.

To manually add a hit or event, you must have access to both the case and the source record, and the case's classification must permit that record's classification. A record above the case's classification ceiling is rejected, not simply hidden after addition. Evidence items retain their source classification. You need access to the case itself to open its workspace; within an accessible case, items above your access level are omitted.

## Case Workspace Layout

The case workspace is comprised of three sections:

- Navigation and item tree
- Active view in the center
- Case details on the right.

The navigation and case details remain in place while you move between the dashboard, search, observables, timeline, rules, and individual items.
