# Use Lucene execution modes

When **Lucene Query** is selected, the **Query Method** control determines how Howler executes the query.

`advanced_modes`

## Default

**Default** runs a normal hit search. Use it to inspect matching records, test filters, and then move a successful query into the regular Search page or a saved view.

## Facet

**Facet** counts values for the fields you select. It is useful for answering questions such as which analytics, sources, or statuses occur in a matching set. Select the fields to count; for array fields, each unique value is included in the response and counted once per hit.

## Group By

**Group By** groups matching results by one selected hit field. Select the group field before execution; Howler disables **Execute** until one is chosen. Use it to compare groups without manually sorting a large hit list.

## Explain

**Explain** returns the Elasticsearch explanation for a Lucene query instead of ordinary matching records. It is intended for debugging query behavior and inspecting the request that Howler sends to the cluster, not for triaging a result set.
