import importlib
import sys
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_server_defaults_invalid_port_and_closes_api_client(monkeypatch):
    monkeypatch.setattr("howler_mcp.config.MCPSettings.PORT", "not-a-port")
    sys.modules.pop("howler_mcp.server", None)

    with (
        patch("mcp.server.fastmcp.FastMCP") as mock_fast_mcp,
        patch("howler_mcp.api.HowlerApiClient") as mock_api_client,
        patch("howler_mcp.tools.register_tools") as mock_register_tools,
        patch("howler_mcp.prompts.register_prompts") as mock_register_prompts,
    ):
        api_client = mock_api_client.return_value
        api_client.aclose = AsyncMock()
        server = importlib.import_module("howler_mcp.server")

        assert server.port == 8000
        assert mock_fast_mcp.call_args.kwargs["port"] == 8000
        mock_register_tools.assert_called_once_with(server.mcp, api_client)
        mock_register_prompts.assert_called_once_with(server.mcp)

        async with server.lifespan(server.mcp) as context:
            assert context == {}

    api_client.aclose.assert_awaited_once()
