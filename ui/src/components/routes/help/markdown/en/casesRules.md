# Correlation and automation

Correlation rules automatically place newly ingested matching records into a case. Open **Rules** from the case sidebar to create, review, enable, disable, or delete the rules owned by that case.

## Create a correlation rule

A rule has a Lucene match query, a destination path, and one or both supported indexes: **hit** and **event**. Use the search control in the dialog to test the query before creating the rule.

The destination is a Mustache template for the case item path. For example, `alerts/{{howler.analytic}}` creates or uses an `alerts` folder and names the matched item from its analytic. Folders in a rendered destination are created when needed. The rule table shows the destination, query, indexes, author, expiry, and enabled state.

`correlation_rule`

## Set the rule lifetime

Rules are enabled by default. A finite expiry is measured in days from rule creation. Choose **No expiry** to keep a rule active indefinitely.

**Start expiry after case is resolved** is available only when the rule has a finite expiry. With it enabled, the countdown begins at the case's most recent resolution; if the case has never been resolved, the timer has not started. Toggle a rule off to pause matching without deleting its configuration.

## Automate an existing search

The **Add to Case** action is available to authorized automation users. It runs a hit query against the selected case and uses a Mustache destination such as `related/{{howler.analytic}} ({{howler.id}})`. This is useful for adding an existing group of matching alerts and organizing them into generated folders, while correlation rules handle records as they are ingested.
