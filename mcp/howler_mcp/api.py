import logging
from typing import Any, Literal

import httpx

from mcp.server.auth.provider import AccessToken

from .auth import AuthProvider
from .config import HOWLER_API

HttpVerb = Literal["GET", "POST", "OPTIONS"]
logger = logging.getLogger(__name__)


class HowlerApiClient:
    def __init__(
        self,
        base_url: str = HOWLER_API.BASE_URL,
        auth_provider: AuthProvider | None = None,
        timeout: float = HOWLER_API.TIMEOUT,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.auth_provider = auth_provider or AuthProvider()
        self.timeout = timeout
        self._obo_token_cache: dict[str, tuple[str, int]] = {}
        self._default_cache_ttl_seconds = 300

    async def call(
        self,
        user_access_token: AccessToken,
        path: str,
        method: HttpVerb,
        body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        if method != "POST" and body is not None:
            raise ValueError("Request body is only allowed for POST")

        exchanged_token = await self.auth_provider.get_howler_token(
            user_access_token.token
        )
        headers = {"Authorization": f"Bearer {exchanged_token}"}
        url = f"{self.base_url}/{path.lstrip('/')}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=body if method == "POST" else None,
            )
            response.raise_for_status()

            _json = response.json()

            if "api_response" not in _json:
                raise ValueError("Howler API did not return in expected format")

            return _json["api_response"]
