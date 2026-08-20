# Choose a query language

The **Query Type** control changes the editor language and endpoint used to search hits. Selecting a different language loads an example suited to that syntax.

`advanced_languages`

## Lucene Query

Use **Lucene Query** for the same field-oriented syntax used by Howler's regular hit search. It is the only query language that offers Default, Facet, Group By, and Explain execution modes. Multiline input is normalized before it is sent to the hit-search APIs.

## EQL Query

Use **EQL** (Event Query Language) for event-based sequences and time-series-style queries. EQL has its own syntax and response structure, so inspect the JSON result rather than expecting a regular hit list. Switching to EQL resets the Lucene-only execution mode to Default.

## Sigma Rule

Use **Sigma Rule** for a complete Sigma rule written in YAML. Howler submits the YAML as a Sigma search, including the rule metadata and detection section. Validate the rule with a small result count first, then refine its field selections or condition before expanding the query.
