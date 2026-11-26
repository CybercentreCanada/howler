"""Call A2A AI agents with the current user's delegated identity."""

import json
from collections.abc import Callable, Iterator
from typing import Any
from uuid import uuid4

import requests

from howler.common.logging import get_logger
from howler.config import cache, config
from howler.helper.azure import azure_obo
from howler.odm.models.config import AIAgent
from howler.plugins import get_plugins
from howler.services.ai_service import AITransportError, AIUpdate, iter_sse_data, transport_error
from howler.utils.constants import TESTING

logger = get_logger(__file__)

BROKER_EXCHANGE_PATH = "/v1/auth/broker/exchange"
MAX_AGENT_RESPONSE_BYTES = 1_000_000
MAX_AGENT_MESSAGE_CHARS = 500
FAILED_STATES = {"failed", "rejected", "canceled"}
FINAL_STATES = {"completed", "input-required", "auth-required"}
RESULT_KINDS = {"message", "task", "status-update", "artifact-update"}
AGENT = "The AI agent"
BROKER = "The token broker"


def _skip_cache(*_args: Any) -> bool:
    return TESTING


def _token_function() -> Callable[[str], str] | None:
    """Return the first plugin-provided ``ai_agent`` token function, if any."""
    for plugin in get_plugins():
        if token_function := plugin.modules.token_functions.get("ai_agent", None):
            return token_function

    return None


def has_delegation() -> bool:
    """Return whether a delegated agent token can be obtained, via a plugin or an Azure OBO scope."""
    return _token_function() is not None or bool(config.core.ai.lucene.agent.scope)


def exchange_token(access_token: str) -> str:
    """Exchange a Howler bearer token for a token accepted by the AI agent platform.

    A plugin ``ai_agent`` token function takes precedence; otherwise Azure on-behalf-of is used with the
    configured scope. The Howler token is never forwarded to the agent platform as-is.
    """
    if token_function := _token_function():
        return token_function(access_token)

    scope = config.core.ai.lucene.agent.scope
    if not scope:
        raise AITransportError("AI agent delegation is not configured")

    return azure_obo(access_token, scope=scope)


@cache.memoize(15 * 60, unless=_skip_cache)
def get_delegated_token(access_token: str) -> str:
    """Return a cached delegated token for the AI agent platform; see :func:`exchange_token`."""
    return exchange_token(access_token)


def _status_hook(service: str) -> Callable[..., requests.Response]:
    """Build a response hook that rejects non-success responses from ``service`` without exposing their bodies."""

    def check_status(response: requests.Response, *args: Any, **kwargs: Any) -> requests.Response:
        if 200 <= response.status_code < 300:
            return response

        response.close()
        if response.status_code in {401, 403}:
            raise AITransportError(f"{service} denied access. Check delegated permissions and user authorization.")
        if response.status_code == 404:
            raise AITransportError(f"{service} or its endpoint was not found.")
        raise AITransportError(f"{service} returned HTTP {response.status_code}")

    return check_status


def _agent_url(settings: AIAgent) -> str:
    return (settings.agent_url or "").rstrip("/") + "/"


def get_agent_token(settings: AIAgent, access_token: str) -> str:
    """Obtain a short-lived token for the configured agent from the token broker.

    Args:
        settings: AI agent and broker settings.
        access_token: The current user's Howler bearer token.

    Returns:
        The agent access token. It is used for a single request and never returned to the browser.

    Raises:
        AITransportError: If the OBO exchange or the broker exchange fails.
    """
    try:
        delegated_token = get_delegated_token(access_token)
    except AITransportError:
        raise
    except Exception:
        # OBO failures can include provider response bodies.
        logger.error("AI agent delegated token exchange failed")  # noqa: TRY400
        raise AITransportError("Failed to obtain AI agent access.") from None

    try:
        with requests.Session() as session:
            # Do not inherit proxy, CA bundle, or .netrc settings from the environment.
            session.trust_env = False
            response = session.post(
                (settings.broker_url or "").rstrip("/") + BROKER_EXCHANGE_PATH,
                json={settings.broker_token_field: delegated_token, "mcp_server_url": _agent_url(settings).rstrip("/")},
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                timeout=(10, 30),
                allow_redirects=False,
                hooks={"response": _status_hook(BROKER)},
            )
            data = response.json()
    except requests.exceptions.JSONDecodeError:
        raise AITransportError("The token broker returned an invalid response.") from None
    except requests.exceptions.RequestException as exc:
        raise transport_error(
            exc, "The token broker timed out.", "The token broker is temporarily unavailable."
        ) from None

    token = data.get("access_token") if isinstance(data, dict) else None
    if not isinstance(token, str) or not token or any(char.isspace() for char in token):
        raise AITransportError("The token broker returned an invalid access token.")

    return token


def _text(parts: Any) -> str:
    """Join the text parts of an A2A message or artifact."""
    if not isinstance(parts, list):
        return ""

    return "".join(
        part["text"]
        for part in parts
        if isinstance(part, dict) and part.get("kind") == "text" and isinstance(part.get("text"), str)
    )


def _status_message(status: Any) -> tuple[str, Any]:
    """Return the text and role of a task status message."""
    message = status.get("message") if isinstance(status, dict) else None
    if not isinstance(message, dict):
        return "", None
    return _text(message.get("parts")), message.get("role")


def _parse_envelope(data: bytes, request_id: str) -> dict[str, Any]:
    try:
        envelope = json.loads(data)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise AITransportError("The AI agent returned an invalid response.") from None

    if not isinstance(envelope, dict) or envelope.get("jsonrpc") != "2.0" or envelope.get("id") != request_id:
        raise AITransportError("The AI agent returned an invalid JSON-RPC response.")
    if "error" in envelope:
        raise AITransportError("The AI agent reported an error.")

    result = envelope.get("result")
    if not isinstance(result, dict) or result.get("kind") not in RESULT_KINDS:
        raise AITransportError("The AI agent returned an invalid result.")

    return result


def _check_final_state(state: Any, message: str) -> None:
    if state in FAILED_STATES:
        raise AITransportError("The AI agent could not complete the request.")
    if state == "auth-required":
        raise AITransportError("The AI agent requires additional authorization.")
    if state == "input-required":
        detail = message.strip()[:MAX_AGENT_MESSAGE_CHARS]
        raise AITransportError(
            f"The AI agent needs more information: {detail}" if detail else "The AI agent needs more input."
        )


def _apply_artifacts(result: dict[str, Any], artifacts: dict[str, str]) -> bool:
    """Record artifact text from an artifact-update or task result.

    Returns:
        Whether any artifact text was recorded.
    """
    if result["kind"] == "artifact-update":
        artifact = result.get("artifact")
        if not isinstance(artifact, dict):
            raise AITransportError("The AI agent returned an invalid artifact.")
        artifact_id = str(artifact.get("artifactId", ""))
        text = _text(artifact.get("parts"))
        artifacts[artifact_id] = artifacts.get(artifact_id, "") + text if result.get("append") else text
        return True

    updated = False
    for artifact in result.get("artifacts") or []:
        if isinstance(artifact, dict):
            artifacts[str(artifact.get("artifactId", ""))] = _text(artifact.get("parts"))
            updated = True
    return updated


def _agent_updates(frames: Iterator[bytes], request_id: str, sent_text: str) -> Iterator[AIUpdate]:
    """Convert A2A stream events into answer text and progress updates.

    Artifacts carry the answer and are reported as the full text so far. When the agent returns no
    artifact, the final message is the answer. Non-final agent status messages are reported as
    progress; echoes of the request are ignored.
    """
    artifacts: dict[str, str] = {}

    for data in frames:
        result = _parse_envelope(data, request_id)

        if result["kind"] == "message":
            if not artifacts:
                yield ("text", _text(result.get("parts")))
            return

        if _apply_artifacts(result, artifacts):
            yield ("text", "".join(artifacts.values()))
        if result["kind"] == "artifact-update":
            continue

        status = result.get("status")
        state = status.get("state") if isinstance(status, dict) else None
        message, role = _status_message(status)
        _check_final_state(state, message)

        if result.get("final") is True or state in FINAL_STATES:
            if not artifacts:
                yield ("text", message)
            return

        if message and role != "user" and message.strip() != sent_text.strip():
            yield ("status", message[:MAX_AGENT_MESSAGE_CHARS])

    raise AITransportError("The AI agent stream ended before a final result.")


def stream_message(settings: AIAgent, agent_token: str, text: str) -> Iterator[AIUpdate]:
    """Send an A2A ``message/stream`` request and yield answer and progress updates.

    Args:
        settings: AI agent settings.
        agent_token: Token obtained from :func:`get_agent_token`.
        text: Message text sent to the agent.

    Yields:
        ``("text", answer_so_far)`` and ``("status", progress_message)`` updates.

    Raises:
        AITransportError: If the transport, status, or event stream is invalid, or the task fails.
    """
    request_id = str(uuid4())
    payload = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "message/stream",
        "params": {
            "message": {
                "role": "user",
                "kind": "message",
                "messageId": str(uuid4()),
                "parts": [{"kind": "text", "text": text}],
            }
        },
    }

    try:
        with requests.Session() as session:
            session.trust_env = False
            with session.post(
                _agent_url(settings),
                json=payload,
                headers={
                    "Authorization": f"Bearer {agent_token}",
                    "Accept": "text/event-stream",
                    "Content-Type": "application/json",
                },
                timeout=(10, settings.timeout_seconds),
                allow_redirects=False,
                stream=True,
                hooks={"response": _status_hook(AGENT)},
            ) as response:
                if response.headers.get("Content-Type", "").split(";")[0].strip() != "text/event-stream":
                    raise AITransportError("The AI agent did not return an event stream.")

                yield from _agent_updates(iter_sse_data(response, MAX_AGENT_RESPONSE_BYTES), request_id, text)
    except requests.exceptions.RequestException as exc:
        raise transport_error(exc, "The AI agent timed out.", "The AI agent is temporarily unavailable.") from None
