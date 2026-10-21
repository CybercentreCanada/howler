from typing import Any

from mcp.server.auth.provider import AccessToken

from howler_mcp.api import HowlerApiClient


async def get_hit_fields(
    api_client: HowlerApiClient,
    access_token: AccessToken,
) -> dict[str, dict[str, Any]]:
    """Fetch searchable hit fields and retain query-authoring metadata."""
    all_values: dict[str, Any] = await api_client.call(
        user_access_token=access_token,
        path="/v1/search/fields/hit",
        method="GET",
    )

    return {
        key: {
            "list": values.get("list"),
            "type": values.get("type"),
            "description": values.get("description"),
        }
        for key, values in all_values.items()
        if isinstance(values, dict)
    }
