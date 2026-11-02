# Shape and reuse results

Use the row-count slider to choose a response limit of 1, 5, 25, 50, 100, 250, 500, 1,000, 2,500, or 10,000. The initial setting is 5. What the limit counts depends on the query language and mode:

- **Default** and **Sigma Rule**: returned hits.
- **EQL**: returned events or sequences, depending on the query.
- **Facet**: returned value buckets per selected field; counts use the matching set, not just that many hits.
- **Group By**: returned groups, each with one representative hit by default.

Start small while validating a query to keep the JSON response focused and responsive. Explain mode ignores the row limit and selected-field controls.

`advanced_results`

## Choose hit fields

For ordinary Lucene and Sigma searches, **Show All Fields** returns every available field. Clear it to choose a focused field list. If you remove the final selected field, Howler reselects **Show All Fields**. Facet mode always asks for the fields to count; the selected field list is part of the facet request.

**EQL is an exception:** with **Show All Fields** selected, the current implementation returns only `howler.id` for each event. Clear the checkbox and explicitly select the fields you need to inspect EQL event or sequence details. Removing the final selected field reselects the checkbox and returns EQL results to the ID-only default.

The response panel displays the server response as expandable JSON. Its shape depends on the language and execution mode, so inspect aggregate sections as well as individual hit data.

## Open a Lucene query in Search

After any successful Lucene response, **Open in Search** is available. It transfers the normalized Lucene filter to the Search page, where you can continue triage, save a view, or act on the matching hits.

The shortcut transfers the filter only. It does not transfer a facet, group-by, explain configuration, selected fields, or the Advanced Search row limit. It uses the current editor contents, so run the query again after editing it before opening Search. EQL and Sigma responses remain in Advanced Search because they do not map directly to a regular Lucene hit search.
