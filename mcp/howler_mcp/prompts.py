import logging

logger = logging.getLogger(__name__)


def register_prompts(mcp):
    @mcp.prompt(name="whoami")
    def whoami_prompt() -> str:
        """Explain when and how to use the whoami tool."""
        return """Use the whoami tool to identify the currently authenticated Howler user.

        Call this tool when you need to confirm:
        - Username
        - Email
        - Group memberships
        - Roles

        Typical use cases:
        - Confirming identity before running user-scoped searches
        - Checking whether the current user has expected permissions
        - Debugging access/authorization issues

        After calling the tool, summarize the identity details in plain language."""

    @mcp.prompt(name="list_assigned_hits")
    def list_assigned_hits_prompt() -> str:
        """Explain when and how to use the list_assigned_hits tool."""
        return """Use the list_assigned_hits tool to retrieve hits currently assigned to the authenticated user.

    Call this tool when the user asks for:
    - Their queue
    - Their assigned tickets
    - Their current workload

    After calling the tool:
    - Report the total number of assigned hits returned
    - Provide hit IDs and key context (status/analytic/escalation if present)
    - Ask if they want follow-up filtering via lucene_query"""

    @mcp.prompt(name="add_comment_to_hit")
    def add_comment_to_hit_prompt() -> str:
        """Explain when and how to use the add_comment_to_hit tool."""
        return """Use add_comment_to_hit to append an analyst comment to a specific hit.

        Required inputs:
        - hit_id: hit UUID
        - comment: clear analyst note

        Use this when the user asks to:
        - Document findings
        - Add triage notes
        - Record investigation actions

        Before calling, confirm the correct hit_id from context or user input.
        After calling, confirm that the comment was added successfully."""

    @mcp.prompt(name="get_field_values")
    def get_field_values_prompt() -> str:
        """Explain when and how to use the get_field_values tool."""
        return """Use get_field_values(field) to discover actual values present for a given field.

        Call this tool before building Lucene filters on enumerated or categorical fields.
        Examples:
        - howler.assignment
        - howler.escalation
        - howler.assessment
        - howler.status
        - howler.analytic

        Rules:
        - Do not guess value spelling or casing
        - Use only values returned by get_field_values

        After calling:
        - Summarize top values by count
        - Use the selected exact value in lucene_query"""

    @mcp.prompt(name="get_hit_fields")
    def get_hit_fields_prompt() -> str:
        """Explain when and how to use the get_hit_fields tool."""
        return """Use get_hit_fields to discover which hit fields are valid in Lucene queries.

            This tool returns field metadata suitable for query authoring, including:
            - Field key
            - Field type
            - List flag
            - Description

            Use it when:
            - You are unsure whether a field exists
            - You need to confirm the exact dot-notation field name

            After calling:
            - Reuse field keys verbatim in lucene_query
            - If you need accepted values for one field, call get_field_values(field)"""

    @mcp.prompt(name="get_label_set_options")
    def get_label_set_options_prompt() -> str:
        """Explain when and how to use the get_label_set_options tool."""
        return """Use get_label_set_options to discover the valid label categories accepted by add_label_to_hit.

        Call this tool when:
        - You need to know which label_set values are allowed
        - The user gives an uncertain or misspelled label category
        - You want to validate the label_set before adding a label

        Typical valid outputs include categories such as:
        - generic
        - victim
        - threat
        - mitigation

        Rules:
        - Use this tool before add_label_to_hit when label_set is ambiguous
        - If the user provides an invalid label_set, correct it using the closest valid option returned by this tool
        - Do not invent label categories that are not returned

        After calling:
        - Confirm the valid label_set you will use
        - Then call add_label_to_hit with the corrected or validated label_set"""

    @mcp.prompt(name="add_label_to_hit")
    def add_label_to_hit_prompt() -> str:
        """Explain when and how to use the add_label_to_hit tool."""
        return """Use add_label_to_hit to add one or more labels to a specific Howler hit.

        Required inputs:
        - hit_id: target hit identifier
        - labels_name: one or more label values to add
        - label_set: valid label category such as generic or victim

        Before calling:
        - Confirm the correct hit_id
        - Validate label_set with get_label_set_options if there is any doubt
        - If the user supplied a wrong label_set, correct it to a valid returned option before calling this tool

        Use this tool when the user asks to:
        - Add a generic label
        - Tag a victim, threat, campaign, or mitigation category
        - Update a hit with analyst-defined label values

        After calling:
        - Report the updated labels for that category
        - Mention the exact label_set used if you had to correct it"""

    @mcp.prompt(name="create_dossier")
    def create_dossier_prompt() -> str:
        """Explain when and how to use the create_dossier tool."""
        return """Use create_dossier to save a Lucene query as a new dossier.

        Required inputs:
        - new_dossier_name: dossier title
        - query: valid Lucene query for hit selection
        - dossier_type: one of global or personal

        Before calling:
        - Ensure the query uses valid field names
        - If field names are uncertain, call get_hit_fields first
        - If enumerated values are uncertain, call get_field_values(field) first
        - Confirm whether the dossier should be global or personal

        Use this tool when the user asks to:
        - Create a saved dossier from a search
        - Persist a repeatable triage filter
        - Share a reusable query (global dossier)

        After calling:
        - Confirm the dossier was created
        - Repeat the dossier name, type, and query used"""

    @mcp.prompt(name="update_dossier")
    def update_dossier_prompt() -> str:
        """Explain when and how to use the update_dossier tool."""
        return """Use update_dossier to modify an existing dossier by ID.

        Required inputs:
        - dossier_id: target dossier identifier
        - data_to_update: partial update object with allowed keys only

        Allowed data_to_update keys:
        - title
        - query
        - leads
        - pivots
        - type
        - owner

        Before calling:
        - Confirm the exact dossier_id
        - Ensure only allowed keys are present in data_to_update
        - If query is included, validate field names with get_hit_fields and field values with get_field_values(field) when needed

        Use this tool when the user asks to:
        - Rename a dossier
        - Update the dossier query
        - Change dossier metadata such as type or ownership

        After calling:
        - Confirm the dossier update was applied
        - Summarize the fields that were changed"""

    @mcp.prompt(name="_verify_leads")
    def verify_leads_prompt() -> str:
        """Explain the expected structure for lead validation payloads."""
        return """Use _verify_leads as the local schema reference for dossier lead objects.

        Expected lead shape:
        - icon: valid Iconify ID string
        - label: object with exactly en and fr keys
        - format: non-empty string
        - content: non-empty string
        - metadata: dictionary, which may be empty

        Example:
        - {"icon": "mdi:file-document", "label": {"en": "Overview", "fr": "Apercu"}, "format": "markdown", "content": "Initial notes", "metadata": {"source": "manual"}}

        Rules:
        - Do not add extra keys
        - Do not use a plain string for label
        - Do not use a non-dictionary metadata value
        - Use query_iconify or get_inconify_exist before choosing an uncertain icon

        Use this reference when building leads for create_dossier or update_dossier."""

    @mcp.prompt(name="_verify_pivots")
    def verify_pivots_prompt() -> str:
        """Explain the expected structure for pivot validation payloads."""
        return """Use _verify_pivots as the local schema reference for dossier pivot objects.

        Expected pivot shape:
        - icon: valid Iconify ID string
        - label: object with exactly en and fr keys
        - value: non-empty string
        - format: non-empty string
        - mappings: nested mapping container for pivot configuration

        Example:
        - {"icon": "mdi:open-in-new", "label": {"en": "Pivot Link", "fr": "Lien Pivot"}, "value": "https://example.local?q={ioc}", "format": "link", "mappings": [{"key": "ioc", "field": "howler.outline.indicators"}]}

        Rules:
        - Do not add extra keys
        - Do not use a plain string for label
        - Ensure value and format are both non-empty strings
        - Use query_iconify or get_inconify_exist before choosing an uncertain icon

        Use this reference when building pivots for create_dossier or update_dossier."""

    @mcp.prompt(name="lucene_query")
    def search_lucene_prompt() -> str:
        """Build a Lucene query from the user's request and search for matching hits."""
        return """Interpret the user's request as a Howler hit search and use lucene_query.

        Available tools:
        - get_hit_fields: discover valid field names
        - get_field_values(field): discover accepted values and counts
        - lucene_query: execute the final query

        Query construction rules:
        - Search only Howler hits
        - Use valid Lucene field:value syntax
        - Use quotes for values with spaces
        - Use operators AND, OR, NOT and range syntax when needed
        - Never invent field names
        - Never invent field values for enumerated fields; verify them first

        When to call get_field_values first:
        - howler.detection
        - howler.escalation
        - howler.assessment
        - howler.status
        - howler.scrutiny
        - howler.analytic
        - howler.assignment

        lucene_query arguments:
        - query: required Lucene expression
        - fl: required comma-separated output fields
        - rows: optional result count
        - offset: optional pagination offset
        - sort: optional sort expression such as event.created desc

        Mandatory fl usage:
        - Always include howler.id
        - Request only fields the user asked for

        Examples:
        - IDs only -> fl="howler.id"
        - IDs + status -> fl="howler.id,howler.status"
        - IDs + indicators + threat -> fl="howler.id,howler.outline.indicators,howler.outline.threat"

        After executing lucene_query:
        - Report query used
        - Report total matches
        - Present returned hits clearly"""
