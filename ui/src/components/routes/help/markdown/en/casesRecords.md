# Adding records to cases

Hits and events can be added as case items without duplicating the underlying record. Their current escalation is reflected in the sidebar, and opening an item displays the record in the case workspace.

## Add selected records

From a search or record view, select one or more hits or events, open the context menu, and choose **Add to Case**. Select the destination case, set a clear name for every record, and optionally choose a folder. The dialog supplies a useful default title based on the analytic or event ID, but each title is independently editable.

Choose **Create Case** from the same menu to start a new case with the selected records. The creation flow adds the case title, summary, escalation, overview, and placement choices in one step.

`add_records`

## Evidence relationships

Adding a hit or event creates a case reference on the underlying record as well as an item in the case. Removing it removes that relationship. A record cannot be added twice to the same case, and its source classification is preserved when it is added.

When an existing case is linked as a related case, it is presented at the top of the item tree and in the dashboard's Related Cases panel.
