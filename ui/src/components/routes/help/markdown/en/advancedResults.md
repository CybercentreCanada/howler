# Shape and reuse results

Use the row-count slider to limit the response to 1, 5, 25, 50, 100, 250, 500, 1,000, 2,500, or 10,000 rows. Start small while validating a query to keep the JSON response focused and responsive. Explain mode ignores the row limit and selected-field controls.

`advanced_results`

## Choose hit fields

With **Show All Fields** selected, returned hits contain every available field. Clear it to choose a focused field list. If you remove the final selected field, Howler returns to showing all fields. Facet mode always asks for the fields to count; the selected field list is part of the facet request.

The response panel displays the server response as expandable JSON. Its shape depends on the language and execution mode, so inspect aggregate sections as well as individual hit data.

## Open a Lucene query in Search

After any successful Lucene response, **Open in Search** is available. It transfers the normalized Lucene filter to the Search page, where you can continue triage, save a view, or act on the matching hits.

The shortcut transfers the filter only. It does not transfer a facet, group-by, explain configuration, selected fields, or the Advanced Search row limit. It uses the current editor contents, so run the query again after editing it before opening Search. EQL and Sigma responses remain in Advanced Search because they do not map directly to a regular Lucene hit search.
