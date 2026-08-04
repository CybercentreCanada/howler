import logging

logger = logging.getLogger(__name__)


def RegisterPrompts(mcp):

    @mcp.prompt(name="ReviewFalsePositive")
    def review_false_positive() -> str:
        """Review analytics marked as false positives."""
        logger.info("Prompt called: ReviewFalsePositive")
        return """Retrieve all hits marked as false positives in the last 90 days using GetFalsePositiveHits.

            Then analyze and present a comprehensive false-positive review report with the following structure:

            ## Summary Statistics
            - Total false positives found
            - Distribution by analytic (group the counts)
            - Percentage breakdown showing which analytics produce the most false positives

            ## Detailed False Positive Analysis
            For each unique analytic identified, provide:
            - Analytic name
            - Count of false positives
            - Sample hit IDs
            - Common patterns or characteristics of the false positives

            ## Root Cause Assessment
            Based on the false positive hits returned, identify and categorize the reasons:
            - Configuration issues (e.g., overly broad rules, missing context filters)
            - Environment-specific noise (e.g., internal testing, legitimate security tools triggering alerts)
            - Data quality problems (e.g., incomplete or duplicate data)
            - Timing or threshold issues

            ## Actionable Recommendations
            Provide specific, prioritized recommendations to reduce false positives:
            1. Analytics with highest false positive rates and suggested fixes
            2. Quick wins (easy configuration changes with high impact)
            3. Detection engineering improvements (rule refinement, filter additions)
            4. Monitoring and tuning strategy going forward

            Format with clear sections, bullet points, and a summary table. Make it suitable for sharing with detection engineers."""

    @mcp.prompt(name="HitReview")
    def hit_review(hit_id: str) -> str:
        """Review a hit and provide an analysis."""
        return f"""Generate a report for hit {hit_id} that includes the following sections:
        1) Summary: A brief overview of the hit, including the analytic that generated it and the reason for its creation.
        2) Evidence: A detailed list of all evidence associated with the hit, including timestamps, sources, and any relevant metadata.
        3) Analyst Comments: A compilation of all comments made by analysts regarding this hit, including their insights and any actions taken.
        4) Recommendations: Based on the evidence and analyst comments, provide recommendations for next steps or further investigation.
        Format the report in a clear and organized manner, using bullet points and headings where appropriate."""

    @mcp.prompt(name="SearchMatchingIndicatorsInOtherSystem")
    def search_indicators(hit_id: str, target_system: str) -> str:
        """Retrieve all indicators from a hit and query a third party system for matching alerts, then produce an action plan.
        This prompt is the canonical way to retrieve all indicators for a hit.
        It requires a third party system connected through an MCP tool."""
        return f"""Perform the following steps for hit {hit_id}:
        1) Retrieve the hit details using GetHitById and extract all indicators (IPs, domains, hashes, URLs, email addresses, etc.) attached to this hit.
           This step must collect every available indicator from the hit payload.
        2) For each indicator, query {target_system} for alerts or incidents that contain or reference that indicator. Use the available MCP tools for {target_system} to search for matching alerts, incidents, or security events.
        3) Produce a report with the following sections:

        ## Executive Summary
        A very short summary of the key findings from the {target_system} search, suitable for a non-technical audience.

        ## Indicator Summary
        A table listing each indicator extracted from the hit, its type (IP, domain, hash, etc.), and whether any matches were found in {target_system}.

        ## {target_system} Findings
        For each alert or incident found in {target_system}, provide:
        - Alert/incident name, ID, and severity
        - Timestamp
        - Which indicator(s) from the hit matched
        - Status (New, In Progress, Resolved, Closed, etc.)
        - Assigned owner or team (if available)
        - Associated entities (hosts, users, services affected)
        - Related context or metadata from {target_system}

        ## Correlation Analysis
        Identify patterns across the {target_system} findings:
        - Are multiple indicators appearing in the same alert or incident?
        - Is there a timeline pattern suggesting a coordinated attack or attack chain?
        - Are there findings from different detection sources or alert types converging on the same indicators?
        - How do the {target_system} findings correlate with the original hit in Howler?

        ## Recommended Action Plan
        Based on the {target_system} findings and their current status, suggest concrete next steps:
        - Which alerts/incidents need immediate escalation (high/critical severity, still active)?
        - Which findings can be correlated or merged with existing investigations?
        - What containment or remediation actions should be prioritized?
        - What additional investigation queries should be run in {target_system} to expand scope?
        - Should the hit in Howler be escalated, reassigned, or closed based on {target_system} findings?

        Format the report clearly with markdown headings, tables, and bullet points. Make it suitable for sharing with security analysts and response teams."""

    @mcp.prompt(name="luceneQuery")
    def search_luecene() -> str:
        """Build a Lucene query from the user's request and search for matching hits."""
        return """Interpret the user's request as a Howler hit search and use the luceneQuery tool.

        Your job is to translate the user's natural language request into a valid Lucene query for Howler hits, then call the luceneQuery tool with the correct arguments.

        Available tools:
        - GetHitFields: call this when you are unsure which field names exist. It returns the full list of searchable Howler hit fields with their types. Use the returned field names verbatim in your Lucene query.
        - GetFieldValues(field): call this to retrieve the exact distinct values stored in a field before using that field as a filter. The response maps each distinct value to its hit count. ALWAYS call this before filtering on any enumerated field (see mandatory list below). Use only values returned by this call — never assume casing or spelling from example data.
        - luceneQuery: call this to execute the query only after field names and values have been confirmed with the tools above.
        - SearchMatchingIndicatorsInOtherSystem (search_indicators): use this when the user asks to retrieve all indicators from a specific hit. This is the canonical prompt for complete indicator extraction.

        Mandatory pre-query verification steps:
        1. For every field the user filters on that is NOT a free-text or numeric field, call GetFieldValues FIRST.
           Fields that ALWAYS require GetFieldValues before use:
           - howler.detection
           - howler.escalation
           - howler.assessment
           - howler.status
           - howler.scrutiny
           - howler.analytic (use GetFieldValues to confirm exact analytic name casing)
           - howler.assignment (use GetFieldValues to confirm exact username)
        2. Do NOT rely on values seen in previous responses, example data, or context. Always verify from GetFieldValues.
        3. Only after GetFieldValues confirms the exact value should you build and execute the query.

        Follow these rules:
        - Search only Howler hits.
        - Build a valid Lucene query string using field:value syntax.
        - Use quoted values when the value contains spaces.
        - Use Lucene operators such as AND, OR, NOT, parentheses, and range expressions when needed.
        - Pass rows, offset, and sort as separate tool arguments. Do not include them inside the Lucene query string.
        - Do not invent field names. If you are unsure whether a field exists, call GetHitFields before building the query.
        - Do not invent field values. ALWAYS call GetFieldValues for enumerated fields — do not guess from prior context.
        - If the user gives a plain English filter, translate it into the simplest valid Lucene expression.
        - If the user asks for pagination, pass rows and offset explicitly to the tool.
        - If the user asks for sorting, pass sort explicitly to the tool.

        Common Howler fields:
        - howler.id: exact hit identifier.
        - howler.assignment: assigned user or queue.
        - howler.escalation: escalation state such as alert.
        - howler.assessment: analyst assessment such as false-positive.
        - howler.analytic: analytic name.
        - howler.score: numeric hit score.
        - howler.outline.indicators: indicator values extracted from the hit.
        - howler.outline.target: target values associated with the hit.
        - howler.outline.threat: threat values associated with the hit.
        - event.created: hit event timestamp, commonly used in time ranges.

        Common field examples:
        - howler.id:1THVzoMxLWnvH8Z2u8XYsj
        - howler.assignment:user
        - howler.escalation:alert
        - howler.assessment:false-positive
        - howler.analytic:"Password Checker"
        - howler.score:[50 TO 100]
        - event.created:[now-7d TO now]

        Common examples:
        - "Find hits assigned to user" -> query: howler.assignment:user
        - "Find hits from analytic Password Checker" -> query: howler.analytic:\"Password Checker\"
        - "Find alert hits from the last 7 days" -> query: howler.escalation:alert AND event.created:[now-7d TO now]
        - "Find hits with score between 50 and 100" -> query: howler.score:[50 TO 100]

        Example transformation:
        - User request: Search for all tickets where howler.assignment equals user. Give me 20 rows and an offset of 30.
        - Tool call arguments:
            - query: howler.assignment:user
            - rows: 20
            - offset: 30

        After calling the tool:
        - Summarize what query was executed.
        - Report the total number of matches.
        - Present the returned hits clearly.
        - If the user asked for a filter that cannot be translated safely into Lucene, explain what is missing and ask for clarification.

        Mandatory fl usage:
        Always pass fl. Build fl from the exact field(s) the user asked for,
        always including howler.id.

        Think of fl as the precise output projection.
        Example question: "Find me the detection for every ticket that the victime was 8.8.8.8"
        - Query should filter tickets where the victime criterion matches 8.8.8.8.
        - fl should request detection (and howler.id), so the response is minimal and does not require extra parsing.

        Example fl values for common requests:
        - "give me the IDs"                         -> fl="howler.id"
        - "IDs, detection, status"                  -> fl="howler.id,howler.detection,howler.status"
        - "IDs, analytic, assignment, assessment"   -> fl="howler.id,howler.analytic,howler.assignment,howler.assessment"
        - "IDs, indicators, threat"                 -> fl="howler.id,howler.outline.indicators,howler.outline.threat"
        - "full ticket details for one ticket"      -> omit fl entirely
        """
