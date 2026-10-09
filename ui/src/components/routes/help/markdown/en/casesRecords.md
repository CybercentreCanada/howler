# Adding records to cases

Hits and events can be added as case items without duplicating the underlying record. A hit's current escalation is reflected in the sidebar, and opening an item displays the record in the case workspace.

## Add selected records

From a search or record view, select one or more hits or events, open the context menu, and choose **Add to Case**. Select the destination case, set a clear name for every record, and optionally choose a folder. The dialog supplies a useful default title based on the analytic or event ID, but each title is independently editable.

Choose **Create Case** from the same menu to start a new case with the selected records. Set the case title, summary, escalation, overview, and record names in the creation dialog. Initial records are added at the new case's root; create folders and move them afterward. Folder selection is available only when adding records to an existing case that already has folders.

`add_records`

## Create an event manually

Use **Add event** in the case sidebar to record evidence that is not already ingested. The dialog requires:

- A title and valid event creation date and time.
- A **Source / Provenance** value identifying where the evidence came from.
- An escalation: `hit`, `alert`, or `evidence`.
- At least one target, threat, or indicator.

You can also provide a summary, choose an existing folder, and use the field-name and description search to add optional ECS fields. Enter indicators one per line or separated by commas. The event inherits the case's classification and is ingested as a new record before being attached to the case, so this differs from adding an existing event.

## Evidence relationships

Adding a hit or event creates a case reference on the underlying record as well as an item in the case. Removing it removes that relationship. A record cannot be added twice to the same case, and its source classification is preserved when it is added.

When an existing case is linked as a related case, it is presented at the top of the item tree and in the dashboard's Related Cases panel.
