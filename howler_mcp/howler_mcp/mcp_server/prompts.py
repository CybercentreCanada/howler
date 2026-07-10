import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


def RegisterPrompts(mcp):

    @mcp.prompt(name="ReviewFalsePositive")
    def review_false_positive() -> str:
        """Review analytics marked as false positives."""
        logger.info("Prompt called: ReviewFalsePositive")
        return """List all hits marked as false positives in the last 90 days. For each hit, include:
        - Hit ID
        - Assigned analyst
        - Analytic name
        - Reason for false positive classification
        - Analyst comments

        Also, retrieve the analytic details using their IDs and include them in the top of the output. Add a pie chart that shows percentage per assessment.

        Analyze the patterns behind these false positives and provide actionable recommendations to reduce them (e.g., analytic tuning, context enrichment, improved triage).
        Present the output directly in the agent in a clear, structured, and professional format, using emojis where appropriate to improve readability."""

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
        This requires to have a third party system connected though an MCP tool, for example Microsoft Sentinel."""
        return f"""Perform the following steps for hit {hit_id}:
        1) Retrieve the hit details using GetHitById and extract all indicators (IPs, domains, hashes, URLs, email addresses, etc.) attached to this hit.
        2) For each indicator, query Microsoft Sentinel for alerts that contain or reference that indicator. Use the Sentinel tools available to search across SecurityAlert, SecurityIncident, and related tables.
        3) Produce a report with the following sections:

        ## Executive
        A very short summary of the key findings from the Sentinel search, suitable for a non-technical audience.

        ## Indicator Summary
        A table listing each indicator extracted from the hit, its type (IP, domain, hash, etc.), and whether any Sentinel alerts were found.

        ## {target_system} Alerts
        For each {target_system} alert found, provide:
        - Alert name and severity
        - Alert timestamp
        - Which indicator(s) from the hit matched
        - Alert status (New, In Progress, Resolved, Dismissed)
        - Assigned owner (if any)
        - Tactics and techniques (MITRE ATT&CK mapping)
        - Related alerts and/or incidents (if the alert is part of a {target_system} incident)

        ## Correlation Analysis
        Identify patterns across the {target_system} alerts:
        - Are multiple indicators appearing in the same alert or incident?
        - Is there a timeline pattern suggesting an attack chain?
        - Are there alerts from different detection sources converging on the same indicators?

        ## Recommended Action Plan
        Based on the {target_system} alerts and their current status, suggest concrete next steps:
        - Which alerts need immediate escalation (high/critical severity, still active)?
        - Which alerts can be correlated or merged with existing incidents?
        - What containment actions should be taken (block IP, isolate host, disable account)?
        - What additional investigation queries should be run in {target_system} to expand scope?
        - Should the hit in Howler be escalated, reassigned, or closed based on {target_system} findings?

        Format the report clearly with markdown headings, tables, and bullet points.

        Start by asking the user if they want the report in the agent as markdown, or download as an HTML report."""
