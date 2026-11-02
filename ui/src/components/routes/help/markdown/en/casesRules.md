# Correlation and automation

Correlation rules automatically place newly ingested matching records into a case. Open **Rules** from the case sidebar to create, review, enable, disable, or delete the rules owned by that case.

## Create a correlation rule

A rule has a Lucene match query, a destination path, and one or both supported indexes: **hit** and **event**. Use the search control in the dialog to test the query before creating the rule.

The destination is a Mustache template for the case item path. For example, `alerts/{{howler.analytic}}` creates or uses an `alerts` folder and names the matched item from its analytic. Folders in a rendered destination are created when needed. The rule table shows the destination, query, indexes, author, expiry, and enabled state.

`correlation_rule`

## Set the rule lifetime

Rules are enabled by default. A finite expiry is measured in days from rule creation. Choose **No expiry** to keep a rule active indefinitely.

**Start expiry after case is resolved** is available only when the rule has a finite expiry. With it enabled, the countdown begins at the case's most recent resolution; if the case has never been resolved, the timer has not started. Toggle a rule off to pause matching without deleting its configuration.

## Backfill historical matches

Creating a rule does not automatically add historical records. To apply it to existing evidence:

1. Enable the rule, then select its history-icon **Backfill rule** control in the rule table.
2. Choose **Alerts since**. The initial boundary is 30 days ago; Howler searches the rule's configured `hit` and/or `event` indexes for accessible matches whose `timestamp` is at or after that boundary. It does not use `event.created` or the ingestion time for this filter.
3. Select **Preview matches** and review the count. Changing the boundary requires a new preview.
4. If there are matches, select **Submit to correlation** to queue them for background processing with that rule's destination template.

Backfill requires an enabled rule, but can explicitly run a rule whose normal expiry has elapsed. The preview count includes all accessible matches, including records already attached to the case; it is not a promise that this many new items will be added. Duplicate records are skipped, and case updates may appear after background processing finishes.

## Automate an existing search

The **Add to Case** action is available to authorized automation users. It runs a hit query against the selected case and uses a Mustache destination such as `related/{{howler.analytic}} ({{howler.id}})`. This is useful for adding an existing group of matching alerts and organizing them into generated folders, while correlation rules handle records as they are ingested or through explicit backfill.

This automation operation retrieves at most **1,000 matching hits per execution**; a larger matching set is not added in full. Narrow the query into separate batches or use rule backfill, which pages through historical matches and supports both hit and event indexes.
