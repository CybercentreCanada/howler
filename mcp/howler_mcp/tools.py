import logging
import re
import uuid
from typing import Any

from fastmcp.server.dependencies import get_access_token
from pydantic import BaseModel, Field

from mcp.server.auth.provider import AccessToken

logger = logging.getLogger(__name__)
LUCENE_SPECIAL_CHARS = frozenset('+-!(){}[]^"~:\\/&|')


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


MAXIMUM_TICKET: int = 200
MAXIMUM_LOOK_BACK: int = 3650  # 10 years (3650 days = ~120 months = ~521 weeks)


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
        """Return the hit information for the given ID."""
        try:
            uuid.UUID(hit_id)
        except ValueError:
            raise ValueError("hit_id must be a valid UUID.")
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
        """Return hits with an 'alert' escalation for a given period.
        The search using a lookback period in days (default is 7 days), and returns a limit of 25 hits unless asked for more with the limit parameter.
        Only use the limit parameters if the user asks for it."""
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
        """Return hits assigned to the currently signed in user. Only use this tool if the user asks for hits assigned to them or to their team."""
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
        """Return hits with matching indicators. Indicators must be a non-empty array of strings.
        Always try to invoke the tool once, even if there are wildcard characters in the list and if the user uses 'and'.
        Only use the limit parameters if the user asks for it (default is 25)."""
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
        """Return hits marked as false positives.
        The search using a lookback period in days (default is 7 days), and returns a limit of 25 hits unless asked for more with the limit parameter.
        Only use the limit parameters if the user asks for it."""
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
        """Return hits generated by a specific analytic name. It needs to be an exact match on the analytic name. Not the id.
        The search using a lookback period in days (default is 30 days), and returns a limit of 25 hits unless asked for more with the limit parameter.
        Only use the limit parameters if the user asks for it."""
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
        # Removing special character and making the \ odd to ensure no escape.
        analytic_name = analytic_name.replace("\\", "\\\\").replace('"', '\\"')

        analytic_name = re.sub(r"[\r\n\t]+", " ", analytic_name).strip()
        if not analytic_name:
            raise ValueError(
                "analytic_name cannot be empty after whitespace normalization."
            )

        # Escape quotes so user input stays data within the Lucene phrase.
        # Remove the ValueError block for "\\"

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
        """Add a comment to a specific hit."""
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
