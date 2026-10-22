from typing import Any

from mcp.server.auth.provider import AccessToken

from howler_mcp.api import HowlerApiClient


async def get_fields_for_index(
    api_client: HowlerApiClient, access_token: AccessToken, index: str
) -> dict[str, dict[str, Any]]:
    """Fetch searchable fields for an index and retain query-authoring metadata.

    Unlike ``get_index_fields``, this helper returns the indexed fields as a
    dictionary. ``get_index_fields`` formats them as a compact string of objects
    to reduce token usage when an LLM reads the output.
    """
    all_values: dict[str, Any] = await api_client.call(
        user_access_token=access_token,
        path=f"/v1/search/fields/{index}",
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
