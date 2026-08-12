import logging

logger = logging.getLogger(__name__)


def register_prompts(mcp):
    @mcp.prompt(name="whoami")
    def whoami_prompt() -> str:
        """Explain when and how to use the whoami tool."""
        return """Use whoami to identify the authenticated Howler user.

Call it when you need to verify the user's:
- username
- email
- group memberships
- roles

Use it before user-scoped searches, permission checks, or authorization troubleshooting.
After the call, summarize the identity in plain language."""

    @mcp.prompt(name="list_assigned_hits")
    def list_assigned_hits_prompt() -> str:
        """Explain when and how to use the list_assigned_hits tool."""
        return """Use list_assigned_hits to retrieve hits assigned to the authenticated user.

Call it when the user asks for their queue, assigned tickets, or current workload.
After the call:
- report the number of hits returned
- list each hit ID and available context such as status, analytic, and escalation
- ask whether the user wants additional filtering with lucene_query"""

    @mcp.prompt(name="add_comment_to_hit")
    def add_comment_to_hit_prompt() -> str:
        """Explain when and how to use the add_comment_to_hit tool."""
        return """Use add_comment_to_hit to append an analyst note to one hit.

Required arguments:
- hit_id: the hit UUID
- comment: the note to append

Use it to document findings, add triage notes, or record investigation actions.
Before calling, confirm the correct hit_id. After calling, confirm that the comment was added."""

    @mcp.prompt(name="get_field_values")
    def get_field_values_prompt() -> str:
        """Explain when and how to use the get_field_values tool."""
        return """Use get_field_values(field) to retrieve the values present for a Howler hit field and their counts.

Call it before filtering on an enumerated or categorical field, including:
howler.assignment, howler.escalation, howler.assessment, howler.status, and howler.analytic.

Never guess a value's spelling or casing. Use only values returned by this tool.
After the call, summarize the most common values and use the exact selected value in lucene_query."""

    @mcp.prompt(name="get_hit_fields")
    def get_hit_fields_prompt() -> str:
        """Explain when and how to use the get_hit_fields tool."""
        return """Use get_hit_fields to retrieve the authoritative list of fields valid in Howler Lucene queries.

The response includes each field's key, type, list flag, and description.
Call it when a field may not exist or when you need its exact dot-notation name.
Reuse returned field keys verbatim in lucene_query. To discover values for a field, call get_field_values(field)."""

    @mcp.prompt(name="get_label_set_options")
    def get_label_set_options_prompt() -> str:
        """Explain when and how to use the get_label_set_options tool."""
        return """Use get_label_set_options to retrieve the label categories accepted by add_label_to_hit.

Call it when label_set is unknown, ambiguous, misspelled, or needs validation. Possible categories include generic, victim, threat, and mitigation, but treat the tool response as authoritative.

Do not invent categories. If the user's value is invalid, choose the closest valid returned option. Then state the label_set you will use and call add_label_to_hit."""

    @mcp.prompt(name="add_label_to_hit")
    def add_label_to_hit_prompt() -> str:
        """Explain when and how to use the add_label_to_hit tool."""
        return """Use add_label_to_hit to add one or more labels to a Howler hit.

Required arguments:
- hit_id: the target hit identifier
- labels_name: a non-empty list of label values
- label_set: a valid label category

Before calling, confirm hit_id. If label_set is uncertain, call get_label_set_options first and use only a returned category. After calling, report the labels returned for that category and mention any corrected label_set."""

    @mcp.prompt(name="create_dossier")
    def create_dossier_prompt() -> str:
        """Explain when and how to use the create_dossier tool."""
        return """Use create_dossier to save a Lucene query as a new dossier.

Required arguments:
- new_dossier_name: the dossier title
- query: a valid Lucene query that selects hits
- dossier_type: global or personal

Before calling:
- verify field names with get_hit_fields when uncertain
- verify enumerated values with get_field_values(field) when uncertain
- confirm whether the dossier should be global or personal

Use this tool to save a search, create a repeatable triage filter, or share a reusable query as a global dossier.
After the call, confirm creation and report the name, type, and query."""

    @mcp.prompt(name="update_dossier")
    def update_dossier_prompt() -> str:
        """Explain when and how to use the update_dossier tool."""
        return """Use update_dossier to modify an existing dossier by ID.

Required arguments:
- dossier_id: the target dossier identifier
- data_to_update: a partial update object

Only these data_to_update keys are allowed:
title, query, leads, pivots, type, owner.

Before calling, confirm dossier_id and remove all other keys. If query is included, verify field names with get_hit_fields and enumerated values with get_field_values(field) when needed.
Use this tool to rename a dossier, change its query, or update metadata such as type or ownership.
After the call, confirm the update and summarize the changed fields."""

    @mcp.prompt(name="_verify_leads")
    def verify_leads_prompt() -> str:
        """Explain the expected structure for lead validation payloads."""
        return """Use _verify_leads as the local schema reference when building dossier leads for create_dossier or update_dossier.

Each lead must contain exactly:
- icon: a valid Iconify ID string
- label: an object with exactly en and fr keys
- format: a non-empty string
- content: a non-empty string
- metadata: a dictionary, possibly empty

Example:
{"icon": "mdi:file-document", "label": {"en": "Overview", "fr": "Apercu"}, "format": "markdown", "content": "Initial notes", "metadata": {"source": "manual"}}

Do not add keys, use a string for label, or use a non-dictionary metadata value. If the icon is uncertain, validate it with query_iconify or get_iconify_exist."""

    @mcp.prompt(name="_verify_pivots")
    def verify_pivots_prompt() -> str:
        """Explain the expected structure for pivot validation payloads."""
        return """Use _verify_pivots as the local schema reference when building dossier pivots for create_dossier or update_dossier.

Each pivot must contain exactly:
- icon: a valid Iconify ID string
- label: an object with exactly en and fr keys
- value: a non-empty string
- format: a non-empty string
- mappings: the nested mapping configuration

Example:
{"icon": "mdi:open-in-new", "label": {"en": "Pivot Link", "fr": "Lien Pivot"}, "value": "https://example.local?q={ioc}", "format": "link", "mappings": [{"key": "ioc", "field": "howler.outline.indicators"}]}

Do not add keys or use a string for label. Ensure value and format are non-empty. If the icon is uncertain, validate it with query_iconify or get_iconify_exist."""

    @mcp.prompt(name="lucene_query")
    def search_lucene_prompt() -> str:
        """Build a Lucene query from the user's request and search for matching hits."""
        return """Use lucene_query to search Howler hits based on the user's request.

Available tools:
- get_hit_fields: retrieve valid field names and metadata
- get_field_values(field): retrieve accepted values and counts
- lucene_query: execute the final search

Build the query as follows:
- use valid Lucene field:value syntax
- quote values containing spaces
- use AND, OR, NOT, and range syntax as needed
- never invent field names
- never invent enumerated values; verify them first
- search only Howler hits

Call get_hit_fields when a field name is uncertain. Call get_field_values first for categorical fields such as:
howler.detection, howler.escalation, howler.assessment, howler.status, howler.scrutiny, howler.analytic, and howler.assignment.

lucene_query arguments:
- query: required Lucene expression
- fl: required comma-separated list of output fields
- rows: optional result count
- offset: optional pagination offset
- sort: optional sort expression, such as event.created desc

Projection rules:
- always include howler.id in fl
- request only fields the user asked for

Examples:
- IDs only: fl="howler.id"
- IDs and status: fl="howler.id,howler.status"
- IDs, indicators, and threat: fl="howler.id,howler.outline.indicators,howler.outline.threat"

After the search, report the query used, total matches, and returned hits clearly."""
