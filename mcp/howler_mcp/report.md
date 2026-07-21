# Howler MCP Server

MCP Server allowing connection between AI Agent and Howler using an On-Behalf-Of flow for authentication.
When the user connects for the first time, their MCP client gets registered using the Dynamic Client Registration (DCR - RFC 7591) and consent is requested. More about the flows [here](README.md).

## Available Tools 🔨

- **GetHitById** Enables full-context investigation of any alert without leaving the AI interface.
- **ListAlerts** Surfaces active alerts immediately, cutting triage start time from minutes to seconds.
- **ListAssignedHits** Delivers a personal work queue on demand, eliminating UI context-switching.
- **SearchHitsWithIndicators** Powers rapid threat hunting by pivoting on IOCs across all hits.
- **GetFalsePositiveHits** Exposes noisy detections so engineers can tune analytics and reduce alert fatigue.
- **ListHitsByAnalytic** Measures analytic effectiveness by surfacing hit volume and quality at a glance.
- **AddCommentToHit** Documents AI-driven findings directly on alerts, preserving audit trail continuity.
- **WhoAmI** Confirms caller identity and permissions instantly, preventing misrouted actions.

## Prompts 💬

- **ReviewFalsePositive** — Generates a 90-day false-positive report with tuning recommendations, driving measurable noise reduction.
- **HitReview** — Produces standardized investigation reports, accelerating analyst hand-offs and ensuring nothing is missed.
- **SearchMatchingIndicatorsInOtherSystem** — Cross-correlates indicators with external SIEMs (e.g., Sentinel), closing visibility gaps across platforms.

Users can begin with suggested prompts in their agent or engage in interactive conversation.
# Examples

Testing environment:
- Howler Dev
- Visual Studio Code
- GitHub Copilot
- Models: GPT-5.3-Codex & Claude Opus 4.6

## Example 1️⃣

The user initiates the /SearchMatchingIndicatorsInOtherSystem command, supplying the hit identifier and the target third-party system (connected via its own MCP) to perform correlation. In this example, the system used is Sentinel and the agent starts by asking about the output format:

![Output format](EX1-0-Report-Format.jpg)

The agent generates the report available here: [Howler ↔ Sentinel Correlation Report](EX1-HowlerHitCorrelationReport.html). Some screenshots:
![Report - part1](EX1-1-Report-Part1.jpg)
![Report - part1](EX1-1-Report-Part2.jpg)
![Report - part1](EX1-1-Report-Part3.jpg)

Then the user added the summary as a comment to the hit:

![Add Comment - part1](EX1-1-AddComment-Part1.jpg)
![Add Comment - part1](EX1-1-AddComment-Part2.jpg)


## Example 2️⃣

The user triggers the /ReviewFalsePositive prompt with no additional input:
![ReviewFalsePositive - part1](EX2-Report-Part1.jpg)
![ReviewFalsePositive - part2](EX2-Report-Part2.jpg)
![ReviewFalsePositive - part3](EX2-Report-Part3.jpg)

Note the recommendations **🔧 1. Tune "Exploit Patcher" Analytic (CRITICAL — 6/9 FPs)** and the one review a hit because of content of a comment **⚠️ 4. Investigate Hit 4Gw3NSEImOX1UtVwpJH88E Immediately**.

## Example 3️⃣

This time the user starts interacting with another MCP server (here Microsoft Sentinel) and uses the insights from it to search for matching indicators in hits in Howler.

![IndicatorsMatch - part1](EX3-Report-Part1.jpg)
![IndicatorsMatch - part2](EX3-Report-Part2.jpg)
![IndicatorsMatch - part3](EX3-Report-Part3.jpg)


## 🔮 Next steps

- [ ] Improve tools descriptions and range.
- [ ] Add relevant prompts.
- [ ] Implement token cache (FastMCP has a middleware that should be able to handle tokens).
- [ ] Implement Open Telemetry logging.


## Possible refactor angles

Instead of listing specialized tools (or in the top of it?):
- have a tool that takes the intent of the user, use RAG on the backend to map it to sample Lucene queries that would help achieve this goal, and return it
- then have another tool that take as in input the selected, relevant and completed query and perform the call
This logic is similar to the one explained here: 🔗 https://learn.microsoft.com/en-us/graph/mcp-server/overview

Implement OAuth scope and mapping to allow different level of permissions. Now it is `howlermcp:access`, but it could be turned into `howlermcp:read` and `howlermcp:write` and use [visibility and tags](https://fastmcp.wiki/en/servers/visibility) in FastMCP to limit tools' availability based on scope.
