import logging
import time
from typing import Any, Literal

import httpx
from mcp.server.auth.provider import AccessToken

from .auth import AuthProvider
from .config import HOWLER_API

HttpVerb = Literal["GET", "POST", "OPTIONS", "PUT"]
logger = logging.getLogger(__name__)


def _status_class(code: int) -> str:
    """Return HTTP status class label, for example ``4xx``."""
    return f"{code // 100}xx"


class HowlerApiClient:
    """HTTP client for communicating with the Howler REST API.

    Handles token exchange, request construction, and response unwrapping
    for all MCP tool calls that need to reach the Howler backend.
    """

    def __init__(
        self,
        base_url: str = HOWLER_API.BASE_URL,
        auth_provider: AuthProvider | None = None,
        timeout: float = HOWLER_API.TIMEOUT,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        """Initialise the API client.

        Args:
            base_url: Base URL of the Howler API, including the version prefix.
            auth_provider: Provider used to exchange the MCP user token for a
                Howler-compatible bearer token. Defaults to a new
                ``AuthProvider`` instance.
            timeout: Request timeout in seconds.
            client: Optional pre-constructed ``httpx.AsyncClient``. When
                omitted the client creates and owns its own instance.
        """
        self.base_url = base_url.rstrip("/")
        self.auth_provider = auth_provider or AuthProvider()
        self.timeout = timeout
        self._client = client or httpx.AsyncClient(timeout=timeout)
        self._owns_client = client is None

    async def aclose(self) -> None:
        """Close the underlying HTTP client if it is owned by this instance."""
        if self._owns_client:
            await self._client.aclose()

    async def call(
        self,
        user_access_token: AccessToken,
        path: str,
        method: HttpVerb,
        body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Execute an authenticated request against the Howler API.

        Args:
            user_access_token: The verified MCP user token used to obtain a
                Howler bearer token via the configured ``AuthProvider``.
            path: API path relative to ``base_url``, e.g. ``/search/hit``.
            method: HTTP verb. ``GET`` and ``OPTIONS`` requests must not carry a
                body.
                body: JSON-serialisable request body. Must be ``None`` for
                    ``GET`` and ``OPTIONS`` requests.
            params: Optional URL query parameters.

        Returns:
            Any: The ``api_response`` value extracted from the Howler JSON
            envelope.

        Raises:
            ValueError: If a body is supplied for a ``GET`` or ``OPTIONS``
                request, or if
                the response JSON does not contain an ``api_response`` key.
            httpx.HTTPStatusError: If the server returns a 4xx or 5xx status.
        """
        started = time.perf_counter()
        outcome = "unknown"
        api_response = None
        status_code: int = -1  # Initialised to known impossible answer value
        route = f"/{path.lstrip('/')}"
        logger.info(f"api_request_sroutetart method={method} route={route} timeout={self.timeout:.2f}")

        try:
            if method in {"GET", "OPTIONS"} and body is not None:
                outcome = "body_error"
                raise ValueError("Request body is not allowed for GET or OPTIONS")
            exchanged_token = await self.auth_provider.get_howler_token(user_access_token.token)
            headers = {"Authorization": f"Bearer {exchanged_token}"}
            url = f"{self.base_url}/{route.lstrip('/')}"
            response = await self._client.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=body if body is not None else None,
            )
            status_code = response.status_code
            response.raise_for_status()
            _json = response.json()
            if "api_response" not in _json:
                outcome = "invalid_envelope"
                logger.error(
                    f"api_request_invalid_envelope method={method} route={route} status={response.status_code}"
                )
                raise ValueError("Howler API did not return in expected format")

            outcome = "success"
            api_response = _json["api_response"]

        except httpx.HTTPStatusError as e:
            code = e.response.status_code
            status_code = code
            status_class = _status_class(code)
            outcome = f"http_{status_class}"
            logger.warning(
                f"api_request_http_error method={method} route={route} status_code={code} "
                f"outcome={outcome} response={e.response.content.decode()}"
            )
            raise

        except httpx.TimeoutException:
            outcome = "timeout"
            logger.warning(f"api_request_timeout method={method} route={route} outcome={outcome}")
            raise

        except httpx.HTTPError:
            outcome = "network_error"
            logger.exception(f"api_request_http_error method={method} route={route} outcome={outcome}")
            raise

        except ValueError:
            outcome = "value_error"
            logger.warning(f"api_request_value_error method={method} route={route} outcome={outcome}")
            raise

        finally:
            duration_seconds = time.perf_counter() - started
            logger.info(
                f"api_request_end method={method} route={route} outcome={outcome} status={status_code} duration_ms={duration_seconds * 1000.0:.2f}"
            )
        return api_response
