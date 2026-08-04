import logging
import re
import uuid
from typing import Any

from fastmcp.server.dependencies import get_access_token
from mcp.server.auth.provider import AccessToken
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
LUCENE_SPECIAL_CHARS = frozenset(' +-!(){}[]^"~:\\/&|?*')
MAXIMUM_TICKET: int = 200
MAXIMUM_LOOK_BACK: int = 3650  # 10 years (3650 days = ~120 months = ~521 weeks)


class WhoAmIResponse(BaseModel):
    username: str = Field(
        description="Unique login name used to identify the current user in Howler."
    )
    email: str = Field(
        description="Primary email address associated with the user account."
    )
    groups: list[str] = Field(
        default_factory=list,
        description="Security or organizational groups the user belongs to.",
    )
    roles: list[str] = Field(
        default_factory=list,
        description="Application roles granted to the user, such as admin or user.",
    )


# Howler_response is a wrapper around the response_api to have a more structured output for the tools.
class HowlerResponse(BaseModel):
    rows: int = Field(description="Number of rows returned in the search results.")
    total: int = Field(description="Total number of hits matching the search criteria.")
    hits: list[dict[str, Any]] = Field(
        default_factory=list, description="List of hits matching the search criteria."
    )


def RegisterTools(mcp, api_client):
    @mcp.tool(name="WhoAmI", description="Get information about the current user")
    async def whoami() -> WhoAmIResponse:
        """Return identity details for the authenticated Howler user.

        Use this tool when the user asks who they are authenticated as, what
        email address is tied to the session, or which groups and roles are
        currently available to them.

        Returns:
            WhoAmIResponse: Username, email, group membership, and role
            information for the current Howler user.
        """
        access_token: AccessToken | None = get_access_token()
        if not access_token:
            raise ValueError("Access token is not available.")

        logger.info(
            "Tool called: whoami. Client: %s User:%s",
            access_token.client_id,
            access_token.subject,
        )
        data = await api_client.call(
            user_access_token=access_token,
            path="/user/whoami",
            method="GET",
        )
        return WhoAmIResponse(
            username=data.get("username", ""),
            email=data.get("email", ""),
            groups=data.get("groups") or [],
            roles=data.get("roles") or [],
        )

    @mcp.tool(name="GetHitById")
    async def get_hit_by_id(hit_id: str) -> dict[str, Any]:
        """Return the full Howler hit payload for a specific hit ID.

        Args:
            hit_id: Exact UUID of the hit to retrieve.

        Returns:
            dict[str, Any]: Raw hit data returned by the Howler API.

        Raises:
            ValueError: If ``hit_id`` is not a valid UUID or if no access token
                is available.
        """
        if not hit_id.strip() or not hit_id:
            raise ValueError("hit_id cannot be empty")

        access_token: AccessToken | None = get_access_token()
        if not access_token:
            raise ValueError("Access token is not available.")

        logger.info(
            "Tool called: GetHitById. Client: %s User:%s",
            access_token.client_id,
            access_token.subject,
        )
        data = await api_client.call(
            user_access_token=access_token,
            path=f"/hit/{hit_id}",
            method="GET",
        )
        return data

    @mcp.tool(name="ListAlerts")
    async def list_alerts(lookback_in_days: int = 7, limit: int = 25) -> dict[str, Any]:
        """Return hits with ``howler.escalation:alert`` in a recent time window.

        Use this tool when the user asks for active or escalated alerts over a
        recent period.

        Args:
            lookback_in_days: Number of days to look back from now when filtering
                on ``event.created``.
            limit: Maximum number of hits to return.

        Returns:
            dict[str, Any]: Raw search response from the Howler search API,
            including total hit count and returned items.

        Raises:
            ValueError: If ``lookback_in_days`` or ``limit`` is outside the
                accepted range, or if no access token is available.
        """
        if lookback_in_days < 1 or lookback_in_days > MAXIMUM_LOOK_BACK:
            raise ValueError(
                f"lookback_in_days must be between 1 and {MAXIMUM_LOOK_BACK}."
            )

        if limit < 1 or limit > MAXIMUM_TICKET:
            raise ValueError(f"limit must be between 1 and {MAXIMUM_TICKET}.")

        access_token: AccessToken | None = get_access_token()
        if not access_token:
            raise ValueError("Access token is not available.")

        logger.info(
            "Tool called: ListAlerts. Client: %s User:%s",
            access_token.client_id,
            access_token.subject,
        )
        return await api_client.call(
            user_access_token=access_token,
            path="/search/hit",
            method="POST",
            body={
                "query": "\nhowler.id:*\nAND\nhowler.escalation:alert",
                "fl": None,
                "filters": [
                    "event.created:[now-" + str(lookback_in_days) + "d TO now]"
                ],
                "rows": limit,
            },
        )

    @mcp.tool(name="ListAssignedHits")
    async def list_assigned_hits() -> list[dict[str, Any]]:
        """Return hits assigned to the currently authenticated user.

        Use this tool when the user asks for their assigned hits or work queue.

        Returns:
            list[dict[str, Any]]: Hits returned by the Howler API for the
            current user's assignments.

        Raises:
            ValueError: If no access token is available.
        """
        access_token: AccessToken | None = get_access_token()
        if not access_token:
            raise ValueError("Access token is not available.")
        logger.info(
            "Tool called: ListAssignedHits. Client: %s User:%s",
            access_token.client_id,
            access_token.subject,
        )

        return await api_client.call(
            user_access_token=access_token,
            path="/hit/user",
            method="GET",
        )

    @mcp.tool(name="SearchHitsWithIndicators")
    async def search_hits_with_indicators(
        indicators: list[str], limit: int = 25
    ) -> HowlerResponse:
        """Search hits whose indicator fields match one or more indicators.

        This tool builds a Lucene query across ``howler.outline.indicators``,
        ``howler.outline.target``, and ``howler.outline.threat`` using the
        provided indicator values.

        Args:
            indicators: Non-empty list of indicator strings such as IPs,
                domains, hashes, or URLs.
            limit: Maximum number of hits to return.

        Returns:
            HowlerResponse: Structured search results with simplified hit data.

        Raises:
            ValueError: If the indicator list is empty, contains blank values
                after normalization, if ``limit`` is out of range, or if no
                access token is available.
        """
        if not indicators:
            raise ValueError("indicators must be a non-empty list.")

        if limit < 1 or limit > MAXIMUM_TICKET:
            raise ValueError(f"limit must be between 1 and {MAXIMUM_TICKET}.")
        for i in range(len(indicators)):
            indicators[i] = re.sub(r"[\r\n\t]+", " ", indicators[i]).strip()
            if not indicators[i]:
                raise ValueError(
                    "indicators cannot contain empty strings after whitespace normalization."
                )

        access_token: AccessToken | None = get_access_token()
        if not access_token:
            raise ValueError("Access token is not available.")

        logger.info(
            "Tool called: SearchHitsWithIndicators. Client: %s User:%s",
            access_token.client_id,
            access_token.subject,
        )

        converted_indicators = " OR ".join(
            "".join(
                f"\\{char}" if char in LUCENE_SPECIAL_CHARS else char
                for char in indicator
            )
            for indicator in indicators
        )
        query = f"howler.outline.indicators:({converted_indicators}) OR howler.outline.target:({converted_indicators}) OR howler.outline.threat:({converted_indicators})"
        data = await api_client.call(
            user_access_token=access_token,
            path="/search/hit",
            method="POST",
            body={"query": query, "fl": None, "rows": limit},
        )

        return HowlerResponse(
            rows=data.get("rows", 0),
            total=data.get("total", 0),
            hits=[
                {
                    "classification": item.get("classification"),
                    "howler": item.get("howler", {}),
                    "timestamp": item.get("timestamp"),
                }
                for item in (data.get("items") or [])
            ],
        )

    @mcp.tool(name="GetFalsePositiveHits")
    async def get_false_positive_hits(
        lookback_in_days: int = 7, limit: int = 25
    ) -> HowlerResponse:
        """Return hits assessed as false positives in a recent time window.

        This tool searches for ``howler.assessment:false-positive`` and also
        requests analytic metadata for each matching hit.

        Args:
            lookback_in_days: Number of days to look back from now when filtering
                on ``event.created``.
            limit: Maximum number of hits to return.

        Returns:
            HowlerResponse: Structured false-positive search results including
            analytic identifiers when available.

        Raises:
            ValueError: If ``lookback_in_days`` or ``limit`` is outside the
                accepted range, or if no access token is available.
        """
        if lookback_in_days < 1 or lookback_in_days > MAXIMUM_LOOK_BACK:
            raise ValueError(
                f"lookback_in_days must be between 1 and {MAXIMUM_LOOK_BACK}."
            )

        if limit < 1 or limit > MAXIMUM_TICKET:
            raise ValueError(f"limit must be between 1 and {MAXIMUM_TICKET}.")

        access_token: AccessToken | None = get_access_token()
        if not access_token:
            raise ValueError("Access token is not available.")
        logger.info(
            "Tool called: GetFalsePositiveHits. Client: %s User:%s",
            access_token.client_id,
            access_token.subject,
        )

        data = await api_client.call(
            user_access_token=access_token,
            path="/search/hit",
            method="POST",
            body={
                "query": "howler.id:*\nAND\nhowler.assessment:false-positive",
                "fl": None,
                "filters": [
                    "event.created:[now-" + str(lookback_in_days) + "d TO now]"
                ],
                "metadata": ["analytic"],
                "rows": limit,
            },
        )
        return HowlerResponse(
            rows=data.get("rows", 0),
            total=data.get("total", 0),
            hits=[
                {
                    "classification": item.get("classification"),
                    "analytic_id": (item.get("__analytic") or {}).get("analytic_id"),
                    "howler": item.get("howler", {}),
                    "timestamp": item.get("timestamp"),
                }
                for item in (data.get("items") or [])
            ],
        )

    @mcp.tool(name="ListHitsByAnalytic")
    async def list_hits_by_analytic(
        analytic_name: str, lookback_in_days: int = 30, limit: int = 25
    ) -> HowlerResponse:
        """Return hits generated by an analytic with an exact display name.

        This tool searches on ``howler.analytic`` using a quoted Lucene phrase.
        The input is the analytic name, not the analytic ID.

        Args:
            analytic_name: Exact analytic name to match.
            lookback_in_days: Number of days to look back from now when filtering
                on ``event.created``.
            limit: Maximum number of hits to return.

        Returns:
            HowlerResponse: Structured search results containing hits generated
            by the requested analytic.

        Raises:
            ValueError: If ``analytic_name`` becomes empty after normalization,
                if ``lookback_in_days`` or ``limit`` is outside the accepted
                range, or if no access token is available.
        """
        if lookback_in_days < 1 or lookback_in_days > MAXIMUM_LOOK_BACK:
            raise ValueError(
                f"lookback_in_days must be between 1 and {MAXIMUM_LOOK_BACK}."
            )

        if limit < 1 or limit > MAXIMUM_TICKET:
            raise ValueError(f"limit must be between 1 and {MAXIMUM_TICKET}.")

        access_token: AccessToken | None = get_access_token()
        if not access_token:
            raise ValueError("Access token is not available.")

        logger.info(
            "Tool called: ListHitsByAnalytic. Client: %s User:%s",
            access_token.client_id,
            access_token.subject,
        )
        # Escape backslashes and quotes before embedding the value in a Lucene phrase.
        analytic_name = analytic_name.replace("\\", "\\\\").replace('"', '\\"')

        analytic_name = re.sub(r"[\r\n\t]+", " ", analytic_name).strip()
        if not analytic_name:
            raise ValueError(
                "analytic_name cannot be empty after whitespace normalization."
            )

        data = await api_client.call(
            user_access_token=access_token,
            path="/search/hit",
            method="POST",
            body={
                "query": f'howler.analytic:"{analytic_name}"',
                "fl": None,
                "filters": [
                    "event.created:[now-" + str(lookback_in_days) + "d TO now]"
                ],
                "rows": limit,
            },
        )
        return HowlerResponse(
            rows=data.get("rows", 0),
            total=data.get("total", 0),
            hits=[
                {
                    "classification": item.get("classification"),
                    "howler": item.get("howler", {}),
                    "timestamp": item.get("timestamp"),
                }
                for item in (data.get("items") or [])
            ],
        )

    @mcp.tool(name="AddCommentToHit")
    async def add_comment_to_hit(hit_id: str, comment: str) -> str:
        """Add an analyst comment to a specific hit.

        Args:
            hit_id: Exact UUID of the hit that should receive the comment.
            comment: Comment text to append. The tool prefixes the text to show
                it originated from the MCP client.

        Returns:
            str: Confirmation message after the comment is added.

        Raises:
            ValueError: If ``hit_id`` is not a valid UUID or if no access token
                is available.
        """
        try:
            uuid.UUID(hit_id)
        except ValueError:
            raise ValueError("hit_id must be a valid UUID.")
        access_token: AccessToken | None = get_access_token()
        if not access_token:
            raise ValueError("Access token is not available.")

        logger.info(
            "Tool called: AddCommentToHit. Client: %s User:%s",
            access_token.client_id,
            access_token.subject,
        )
        _ = await api_client.call(
            user_access_token=access_token,
            path=f"/hit/{hit_id}/comments",
            method="POST",
            body={"value": f"From MCP Client: {comment}"},
        )
        return "Comment added successfully."

    @mcp.tool(name="GetFieldValues")
    async def get_field_values(field: str) -> dict[str, int]:
        """Return the distinct values and their hit counts for a specific Howler hit field.

        Use this tool when you know a field name but are unsure which values it
        accepts. For example, call it with ``howler.escalation`` or
        ``howler.assessment`` before building a Lucene query that filters on
        those fields.

        Args:
            field: Exact field name to inspect, such as ``howler.escalation``
                or ``howler.assessment``.

        Returns:
            dict[str, int]: Mapping of distinct field value to the number of
            hits that carry it, for example
            ``{"alert": 120, "hit": 340, "miss": 5}``.

        Raises:
            ValueError: If no access token is available.
        """
        access_token: AccessToken | None = get_access_token()
        if not access_token:
            raise ValueError("Access token is not available.")

        logger.info(
            "Tool called: GetFieldValues(%s). Client: %s User:%s",
            field,
            access_token.client_id,
            access_token.subject,
        )
        return await api_client.call(
            user_access_token=access_token,
            # The facet endpoint lives under /search/facet/<index>/<field>.
            # Passing the field directly in the path avoids a separate body.
            path=f"/search/facet/hit/{field}",
            method="GET",
            # A broad query is required — the facet endpoint needs at least one
            # matching document to return any distinct values. Using howler.id:*
            # matches every hit so we always get the full value distribution.
            params={"query": "howler.id:*"},
        )

    @mcp.tool(name="GetHitFields")
    async def get_hit_fields() -> dict[str, Any]:
        """Return all searchable fields available on Howler hits.

        Use this tool before building a Lucene query when you are unsure which
        field names are valid. The response lists every indexed field together
        with its type and whether it is stored or indexed.

        Returns:
            dict[str, Any]: Mapping of field name to field metadata, for
            example ``{"howler.assignment": {"type": "keyword", "indexed": true,
            "stored": false}, ...}``.

        Raises:
            ValueError: If no access token is available.
        """
        access_token: AccessToken | None = get_access_token()
        if not access_token:
            raise ValueError("Access token is not available.")

        logger.info(
            "Tool called: GetHitFields. Client: %s User:%s",
            access_token.client_id,
            access_token.subject,
        )
        return await api_client.call(
            user_access_token=access_token,
            # /search/fields/<index> returns the Elasticsearch field mapping
            # for that index, including type, indexed, and stored flags.
            # This is the authoritative source of valid field names for
            # Lucene queries — use these names verbatim.
            path="/search/fields/hit",
            method="GET",
        )

    @mcp.tool(name="luceneQuery")
    async def luecen_query(
        query: str,
        fl: str,
        sort: str = "",
        rows: int = MAXIMUM_TICKET,
        offset: int = 0,
    ) -> HowlerResponse:
        """Search hits using a valid Lucene query.

        Use this tool when the user asks to search hits with explicit field/value
        criteria, boolean logic, ranges, or quoted phrases. The ``query`` argument
        must already be valid Lucene syntax.

        Common Howler fields:
            howler.id: Exact hit identifier.
            howler.assignment: Assigned user or queue.
            howler.escalation: Escalation state such as ``alert``.
            howler.assessment: Analyst assessment such as
                ``false-positive``.
            howler.analytic: Analytic name.
            howler.score: Numeric hit score.
            howler.outline.indicators: Indicator values extracted from the
                hit.
            howler.outline.target: Target values associated with the hit.
            howler.outline.threat: Threat values associated with the hit.
            event.created: Hit event timestamp, commonly used in time ranges.

        Examples:
            howler.assignment:user
            howler.analytic:"Password Checker"
            howler.escalation:alert AND event.created:[now-7d TO now]
            howler.score:[50 TO 100] AND NOT howler.assessment:false-positive
            howler.outline.indicators:(example.com OR 1.2.3.4)

        If you are unsure which field names are valid, call ``GetHitFields``
        first. If you are unsure which values a field accepts, call
        ``GetFieldValues`` first.

        **Reducing response size with** ``fl``:

        Large responses (many hits or hits with long comment/log/dossier arrays)
        are written to a file that cannot be read back. Use ``fl`` to request
        only the fields you need so the response stays small enough to return
        inline.

        Pass ``fl`` as a comma-separated list of dot-notation field names.
        ``howler.id`` is always returned regardless of ``fl``.

        Examples:
            fl="howler.id,howler.assignment,howler.status"
            fl="howler.id,howler.analytic,howler.detection,howler.assessment"
            fl="howler.id,howler.outline.indicators,howler.outline.threat"

        Use ``fl`` to request the exact field(s) the user asked for so the
        response is as small as possible and does not require extra parsing.
        Example request: "Find me the detection for every ticket where the
        victim was 8.8.8.8" should request only detection (and ``howler.id``)
        in ``fl``, while filtering with the victim criterion in ``query``.

        Args:
            query: A valid Lucene query string. Use ``field:value`` syntax, quote
                phrase values that contain spaces, and use Lucene operators such as
                ``AND``, ``OR``, ``NOT``, parentheses, and range expressions.
                Do not invent field names or values. Use ``GetHitFields`` and
                ``GetFieldValues`` to verify them before querying.
            sort: Optional Howler sort expression, such as
                ``event.created desc``. Leave empty to use the API default.
            rows: Maximum number of hits to return.
            offset: Starting offset into the result set for pagination.
            fl: Required comma-separated list of field names to include in each
                returned hit. Always pass only the exact fields requested by the
                user. ``howler.id`` is always added automatically if missing.

        Returns:
            HowlerResponse: Structured search results containing the total count,
            returned row count, and simplified hit payloads.
        """
        access_token: AccessToken | None = get_access_token()
        if not access_token:
            raise ValueError("Access token is not available.")

        if rows <= 0 or rows > MAXIMUM_TICKET:
            raise ValueError(
                f"Row : {rows} can not be lower then 0 or higher then {MAXIMUM_TICKET}"
            )

        if not fl.strip():
            raise ValueError("fl must be provided and cannot be empty.")

        logger.info(
            "Tool called: luceneQuery. Client: %s User:%s",
            access_token.client_id,
            access_token.subject,
        )

        # Build the POST body incrementally so that optional fields are only
        # sent when they carry a meaningful value.
        body: dict[str, Any] = {"query": query, "offset": offset, "rows": rows}
        if sort:
            # Only include sort when the caller explicitly set it. Sending an
            # empty string causes the API to reject the request rather than
            # falling back to its default sort order.
            body["sort"] = sort

        # Pass the field list to the API so it projects only the requested
        # fields server-side. The API expects a comma-separated string, not
        # a list — matching the "fl": "id,score" format in the data block.
        # howler.id is always included so hits remain identifiable.
        requested = [f.strip() for f in fl.split(",") if f.strip()]
        if "howler.id" not in requested:
            requested.insert(0, "howler.id")
        body["fl"] = ",".join(requested)

        data = await api_client.call(
            user_access_token=access_token,
            # The search endpoint accepts any Lucene query against the hit index.
            # The caller is responsible for providing valid Lucene syntax.
            path="/search/hit",
            method="POST",
            body=body,
        )
        return HowlerResponse(
            rows=data.get("rows", 0),
            total=data.get("total", 0),
            hits=[
                {
                    "classification": item.get("classification"),
                    "howler": item.get("howler", {}),
                    "timestamp": item.get("timestamp"),
                }
                for item in (data.get("items") or [])
            ],
        )
