"""Bounded OpenAI-compatible chat-completions transport for AI triage."""

import json
import time
from typing import Any, cast

import urllib3
from gevent import Timeout, socket, ssl
from requests.utils import DEFAULT_CA_BUNDLE_PATH
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool
from urllib3.response import BaseHTTPResponse

from howler.odm.models.config import AITriage

MAX_INPUT_BYTES = 200_000
MAX_OUTPUT_BYTES = 100_000


class AITransportError(Exception):
    """Provider failure with a safe, user-visible reason."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class _HTTPConnection(HTTPConnection):
    """Use cancellable I/O without globally monkey-patching development/tests."""

    def _new_conn(self):
        return socket.create_connection((self.host, self.port), self.timeout, self.source_address)


class _HTTPSConnection(HTTPSConnection, _HTTPConnection):
    """Use the same cancellable connection for TLS endpoints."""


class _HTTPPool(HTTPConnectionPool):
    # urllib3's concrete connections conflict with its own protocol annotations.
    ConnectionCls = cast(Any, _HTTPConnection)


class _HTTPSPool(HTTPSConnectionPool):
    ConnectionCls = cast(Any, _HTTPSConnection)


def _remaining_time(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise AITransportError("Provider exceeded its timeout")
    return remaining


def _read_bounded_json(response: BaseHTTPResponse) -> dict[str, Any]:
    body = bytearray()
    for chunk in response.stream(8192):
        body.extend(chunk)
        if len(body) > MAX_OUTPUT_BYTES:
            raise AITransportError("Provider response exceeded the size limit")

    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AITransportError("Provider returned an invalid response") from exc
    if not isinstance(payload, dict):
        raise AITransportError("Provider returned an invalid response")
    return payload


def generate(
    config: AITriage,
    token: str,
    system_prompt: str,
    alert_data: dict[str, Any],
    *,
    deadline: float,
) -> str:
    """Generate text within a request-wide deadline and exact byte limits."""
    if not config.endpoint:
        raise AITransportError("AI triage is not configured")

    body = json.dumps(
        {
            "model": config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(alert_data, ensure_ascii=False, separators=(",", ":"))},
            ],
            "stream": False,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    if len(body) > MAX_INPUT_BYTES:
        raise AITransportError("Alert input exceeded the size limit")

    remaining = _remaining_time(deadline)

    # urllib3 does not inherit proxies or .netrc credentials. Cooperative sockets
    # and TLS make the deadline interrupt DNS, connect, headers, and body reads.
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_verify_locations(cafile=DEFAULT_CA_BUNDLE_PATH)
    pool = urllib3.PoolManager(ssl_context=context)
    pools: dict[str, type[HTTPConnectionPool] | type[HTTPSConnectionPool]] = {"http": _HTTPPool, "https": _HTTPSPool}
    pool.pool_classes_by_scheme = pools
    try:
        remaining = _remaining_time(deadline)
        with Timeout(remaining, AITransportError("Provider exceeded its timeout")):
            with pool.request(
                "POST",
                config.endpoint,
                body=body,
                headers={
                    **config.headers,
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                timeout=urllib3.Timeout(connect=min(10, remaining), read=remaining),
                retries=False,
                redirect=False,
                preload_content=False,
            ) as response:
                if not 200 <= response.status < 300:
                    if response.status in {401, 403}:
                        raise AITransportError("Provider rejected the authorization token")
                    raise AITransportError(f"Provider returned HTTP {response.status}")
                payload = _read_bounded_json(response)
    except urllib3.exceptions.HTTPError as exc:
        if time.monotonic() >= deadline:
            raise AITransportError("Provider exceeded its timeout") from exc
        raise AITransportError("AI provider is temporarily unavailable") from exc
    finally:
        pool.clear()

    _remaining_time(deadline)
    choices = payload.get("choices")
    first_choice = choices[0] if isinstance(choices, list) and choices else None
    message = first_choice.get("message") if isinstance(first_choice, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise AITransportError("AI provider returned no text")
    return content.strip()
