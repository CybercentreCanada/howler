"""Bounded OpenAI-compatible chat-completions transport for AI triage."""

import json
import time
from typing import Any

import requests

from howler.odm.models.config import AITriage

MAX_INPUT_BYTES = 200_000
MAX_OUTPUT_BYTES = 100_000


class AITransportError(Exception):
    """Provider failure with a safe, user-visible reason."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _session() -> requests.Session:
    """Create an isolated session without implicit proxies or netrc credentials."""
    session = requests.Session()
    session.trust_env = False
    return session


def _read_bounded_json(response: requests.Response, deadline: float) -> dict[str, Any]:
    body = bytearray()
    for chunk in response.iter_content(chunk_size=8192):
        if time.monotonic() >= deadline:
            raise AITransportError("Provider exceeded its timeout")
        if chunk:
            body.extend(chunk)
            if len(body) > MAX_OUTPUT_BYTES:
                raise AITransportError("Provider response exceeded the size limit")
    if time.monotonic() >= deadline:
        raise AITransportError("Provider exceeded its timeout")

    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AITransportError("Provider returned an invalid response") from exc
    if not isinstance(payload, dict):
        raise AITransportError("Provider returned an invalid response")
    return payload


def _post_json(
    session: requests.Session,
    config: AITriage,
    token: str,
    body: dict[str, Any],
    *,
    deadline: float,
) -> dict[str, Any]:
    endpoint = config.endpoint
    if not endpoint:
        raise AITransportError("AI triage is not configured")
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise AITransportError("AI triage exceeded its time limit")

    headers = {
        **config.headers,
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    try:
        with session.post(
            endpoint,
            json=body,
            headers=headers,
            timeout=(min(10, remaining), remaining),
            allow_redirects=False,
            stream=True,
        ) as response:
            if not 200 <= response.status_code < 300:
                if response.status_code in {401, 403}:
                    raise AITransportError("Provider rejected the authorization token")
                raise AITransportError(f"Provider returned HTTP {response.status_code}")
            return _read_bounded_json(response, deadline)
    except (
        requests.Timeout,
        requests.ConnectionError,
        requests.exceptions.ChunkedEncodingError,
    ) as exc:
        raise AITransportError("AI provider is temporarily unavailable") from exc


def generate(
    config: AITriage,
    token: str,
    system_prompt: str,
    alert_data: dict[str, Any],
    *,
    deadline: float,
) -> str:
    """Generate bounded text from the configured OpenAI-compatible endpoint."""
    alert_json = json.dumps(alert_data, ensure_ascii=False, separators=(",", ":"))
    if len((system_prompt + alert_json).encode("utf-8")) > MAX_INPUT_BYTES:
        raise AITransportError("Alert input exceeded the size limit")

    body = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": alert_json},
        ],
        "stream": False,
    }
    session = _session()
    try:
        payload = _post_json(session, config, token, body, deadline=deadline)
    finally:
        session.close()

    choices = payload.get("choices")
    first_choice = choices[0] if isinstance(choices, list) and choices else None
    message = first_choice.get("message") if isinstance(first_choice, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise AITransportError("AI provider returned no text")
    return content.strip()
