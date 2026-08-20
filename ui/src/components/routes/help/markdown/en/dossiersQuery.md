# Define the matching query

The title and query determine what a dossier is and where it appears. Give the dossier a recognizable title, select its scope, and write a Lucene query that selects the hits which should receive its guidance.

`dossier_query`

## Validate before saving

Use the query control to run the search and inspect its match count. The editor requires a title, a type, a query, and a completed query validation before it enables **Save**. Editing the query makes the previous validation stale, so run it again before saving.

The query is evaluated against each hit, not just against the current result list. Keep it precise enough that the dossier does not appear on unrelated investigations. Opening a dossier card in Search is a useful way to review its current matches.

## Practical query design

Start with stable fields such as `howler.analytic`, `howler.detection`, `event.dataset`, or an ECS field that identifies the intended telemetry. Add status, escalation, or time-related conditions only when they genuinely define the workflow.

For example, `howler.analytic:"VPN Monitor" AND howler.status:open` provides context only while an open VPN Monitor hit is being investigated. Prefer a narrowly scoped global dossier over a broad rule with many unrelated leads or pivots.
