import logging

logger = logging.getLogger(__name__)


def RegisterPrompts(mcp):
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
