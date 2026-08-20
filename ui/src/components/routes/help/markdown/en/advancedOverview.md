# Advanced Query Builder overview

The Advanced Query Builder is a hit-query workbench for testing a query, inspecting its raw response, and choosing a query language or Lucene execution mode. Use it when the regular Search page is not enough for investigating field values, grouped data, EQL sequences, Sigma rules, or the Elasticsearch request behind a Lucene search.

`advanced_languages`

## Run a query

Write or paste the query into the left editor, configure the controls above it, then select **Execute**. You can also use **Ctrl+Enter** on Windows and Linux or **Cmd+Enter** on macOS while the editor is focused.

`advanced_execute`

The response appears as JSON in the right panel. Errors are shown below the editor, so correct the syntax or query configuration before running it again. Drag the divider between the editor and result to give either side more space.

The built-in examples are starting points only. Replace them with a query that is appropriate for the classifications and retention policies of the data you are investigating.
