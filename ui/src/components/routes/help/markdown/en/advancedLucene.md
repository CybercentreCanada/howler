# Use Lucene execution modes

When **Lucene Query** is selected, the **Query Method** control determines how Howler executes the query.

`advanced_modes`

## Default

**Default** runs a normal hit search. Use it to inspect matching records, test filters, and then move a successful query into the Search page or a saved view.

## Facet

**Facet** counts values for the fields you select. It is useful for answering questions such as which analytics, sources, or statuses occur in a matching set. For array fields, each distinct value contributes once per matching hit.

The row-count slider limits the number of value buckets returned for each selected field, not the number of matching hits that contribute to the counts. The initial setting returns up to five buckets per field. If there are more distinct values than the selected limit, some values are omitted; an omitted value does not mean it is absent from the matching data.

## Group By

**Group By** groups matching results by one selected hit field. Select the group field before execution; Howler disables **Execute** until one is chosen. Use it to compare groups without manually sorting a large hit list.

Each returned group includes its value, a matching-hit total, and one representative hit by default. The row-count slider increases the number of groups returned, not the number of hits shown within each group. The response's top-level `total` counts matching hits, not distinct groups.

## Explain

**Explain** uses Elasticsearch's Validate Query API to return query validity and its parsed representation of a Lucene query instead of matching records. Use it to debug query syntax and interpretation. It does not show Howler's complete search request or explain an individual hit's relevance score. The row limit and selected-field controls do not apply in Explain mode.

A response has a structure such as:

```json
{
  "valid": true,
  "explanations": [
    {
      "valid": true,
      "explanation": "ConstantScore(FieldExistsQuery [field=howler.id])"
    }
  ]
}
```
