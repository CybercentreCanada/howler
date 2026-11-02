# Investigate evidence

The case navigation provides three complementary evidence views. They only use the hits and events currently attached to the case, so organize evidence first when you want a focused investigation.

`investigation_views`

## Search within the case

The **Search** view runs a fuzzy search scoped to the current case and directly related cases. Use it to find matching hits, events, or related cases without leaving the workspace. Select an index to limit the result type, then use the search terms and pagination to work through the evidence.

## Explore observables

The **Observables** view deduplicates values from the related fields of case hits and events, including hashes, hosts, IP addresses, users, IDs, URIs, and signatures. Filter by observable type, source origin, role, or escalation, and search values directly.

Each observable shows the role Howler derived for it, its source count, the source items, and their escalation. Source links preserve the item path and return you to the evidence that produced the value.

## Read the timeline

The **Timeline** view displays case hits and events in chronological order. Filter it by MITRE ATT&CK tactic or technique and escalation. It initially selects the Evidence escalation level; clear or change that filter to broaden the view. Selecting an entry opens that record in its case-item context.
