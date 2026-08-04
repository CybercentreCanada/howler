import logging
import re
import uuid
from typing import Any

from fastmcp.server.dependencies import get_access_token
from mcp.server.auth.provider import AccessToken
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
MAXIMUM_TICKET: int = 200


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
    cached_hit_fields: set[str] | None = None

    async def validate_query_fields(query: str) -> str:
        nonlocal cached_hit_fields

        # Normalize first so empty/whitespace-only queries are rejected early.
        normalized = re.sub(r"[\r\n\t]+", " ", query).strip()
        if not normalized:
            raise ValueError("query must be provided and cannot be empty.")

        # Match dotted field names only when they appear as field selectors
        # (left side of a Lucene field:value expression).
        regex = r"\b([a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)+)\s*:"
        all_options: list[str] = re.findall(regex, normalized)

        if cached_hit_fields is None:
            cached_hit_fields = set((await get_hit_fields()).keys())

        errors: list[str] = []
        for option in all_options:
            if option not in cached_hit_fields:
                errors.append(f"{option}")

        if errors:
            raise ValueError(
                f"values {', '.join(errors)} are not allowed in howler. Attempt again"
            )

        return normalized

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
        nonlocal cached_hit_fields

        access_token: AccessToken | None = get_access_token()
        if not access_token:
            raise ValueError("Access token is not available.")

        normalized_field = field.strip()
        if not normalized_field:
            raise ValueError("field parameter is required")

        if cached_hit_fields is None:
            cached_hit_fields = set((await get_hit_fields()).keys())

        if normalized_field not in cached_hit_fields:
            raise ValueError(
                f"The field: {normalized_field} is not a valid option. Use GetHitFields to see available fields."
            )

        return await api_client.call(
            user_access_token=access_token,
            # The facet endpoint lives under /search/facet/<index>/<field>.
            # Passing the field directly in the path avoids a separate body.
            path=f"/search/facet/hit/{normalized_field}",
            method="GET",
            # A broad query is required — the facet endpoint needs at least one
            # matching document to return any distinct values. Using howler.id:*
            # matches every hit so we always get the full value distribution.
            params={"query": r"howler.id:*"},
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
        all_values: dict[str, Any] = await api_client.call(
            user_access_token=access_token,
            # /search/fields/<index> returns the Elasticsearch field mapping
            # for that index, including type, indexed, and stored flags.
            # This is the authoritative source of valid field names for
            # Lucene queries — use these names verbatim.
            path="/search/fields/hit",
            method="GET",
        )
        # Keep only the metadata required for query authoring.
        projected_values: dict[str, Any] = {}
        for key, values in all_values.items():
            # Somehow this key has no value?
            if not isinstance(values, dict):
                continue

            projected_values[key] = {
                "list": values.get("list"),
                "type": values.get("type"),
                "description": values.get("description"),
            }

        return projected_values

    @mcp.tool(name="luceneQuery")
    async def lucene_query(
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

        query = await validate_query_fields(query)

        if rows <= 0 or rows > MAXIMUM_TICKET:
            raise ValueError(
                f"Row : {rows} can not be lower then 0 or higher then {MAXIMUM_TICKET}"
            )

        if not fl.strip():
            raise ValueError("fl must be provided and cannot be empty.")

        if not isinstance(offset, int):
            raise ValueError(f"Offset must be an integer not {offset} a {type(offset)}")

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
