"""Bounded, authenticated transports for AI triage providers."""

import json
import time
import uuid
from collections.abc import Callable, Iterator
from typing import Any

import gevent
import requests

from howler.common.logging import get_logger
from howler.odm.models.config import AITriage

logger = get_logger(__file__)

TERMINAL_A2A_STATES = {"completed", "failed", "canceled", "cancelled", "rejected", "input-required", "auth-required"}
UNSUPPORTED_A2A_METHOD_CODES = {-32601}


class AITransportError(Exception):
    """Provider failure with a safe, user-visible reason and retry classification."""

    def __init__(self, reason: str, *, transient: bool = False):
        super().__init__(reason)
        self.reason = reason
        self.transient = transient


Checkpoint = Callable[[str | None, str | None], bool | None]
BeginAttempt = Callable[[], bool]


def _begin_attempt(callback: BeginAttempt | None) -> None:
    if callback is not None and not callback():
        raise AITransportError("AI provider attempt limit reached")


def _safe_headers(config: AITriage, token: str, *, streaming: bool = False) -> dict[str, str]:
    """Build headers with reserved auth and protocol fields owned by this module."""
    reserved = {
        "authorization",
        "proxy-authorization",
        "host",
        "content-length",
        "content-type",
        "accept",
        "transfer-encoding",
        "connection",
        "cookie",
        "proxy-connection",
    }
    headers = {
        key: value
        for key, value in config.headers.items()
        if key.lower() not in reserved
        and "\r" not in key
        and "\n" not in key
        and "\r" not in value
        and "\n" not in value
    }
    headers.update(
        {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream" if streaming else "application/json",
        }
    )
    return headers


def _session() -> requests.Session:
    """Create an isolated session without implicit proxies or netrc credentials."""
    session = requests.Session()
    session.trust_env = False
    return session


def _request_timeout(remaining: float) -> tuple[float, float]:
    if remaining <= 0:
        raise AITransportError("AI triage exceeded its time limit")
    request_budget = remaining
    return min(10.0, request_budget), request_budget


def _iter_response_content(response: requests.Response) -> Iterator[bytes]:
    try:
        yield from response.iter_content(chunk_size=8192)
    except requests.exceptions.ChunkedEncodingError as exc:
        raise AITransportError("Provider response was interrupted", transient=True) from exc


def _read_bounded_json(
    response: requests.Response,
    maximum: int,
    *,
    deadline: float | None = None,
) -> dict[str, Any]:
    body = bytearray()
    for chunk in _iter_response_content(response):
        if deadline is not None and time.monotonic() >= deadline:
            raise AITransportError("Provider exceeded the run deadline", transient=True)
        if chunk:
            body.extend(chunk)
            if len(body) > maximum:
                raise AITransportError("Provider response exceeded the configured size limit")
    if deadline is not None and time.monotonic() >= deadline:
        raise AITransportError("Provider exceeded the run deadline", transient=True)
    try:
        parsed = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AITransportError("Provider returned an invalid response") from exc
    if not isinstance(parsed, dict):
        raise AITransportError("Provider returned an invalid response")
    return parsed


def _raise_http_error(response: requests.Response) -> None:
    status = response.status_code
    if 300 <= status < 400:
        raise AITransportError("Provider redirects are not supported")
    if status in {401, 403}:
        raise AITransportError("Provider rejected the authorization token")
    if status == 429 or status in {408, 425} or status >= 500:
        raise AITransportError("Provider is temporarily unavailable", transient=True)
    raise AITransportError(f"Provider rejected the request (HTTP {status})")


def _a2a_state(result: dict[str, Any]) -> str | None:
    status = result.get("status")
    if isinstance(status, dict):
        state = status.get("state")
        return state if isinstance(state, str) else None
    state = result.get("state")
    return state if isinstance(state, str) else None


def _a2a_task_id(result: dict[str, Any]) -> str | None:
    task_id = result.get("taskId")
    if not isinstance(task_id, str) and result.get("kind") == "task":
        task_id = result.get("id")
    return task_id if isinstance(task_id, str) and task_id else None


def _a2a_context_id(result: dict[str, Any]) -> str | None:
    context_id = result.get("contextId")
    return context_id if isinstance(context_id, str) and context_id else None


def _checkpoint(
    result: dict[str, Any], callback: Checkpoint, task_id: str | None, context_id: str | None
) -> tuple[str | None, str | None]:
    observed_task = _a2a_task_id(result)
    observed_context = _a2a_context_id(result)
    if task_id and observed_task and task_id != observed_task:
        raise AITransportError("A2A response changed its task identifier")
    if context_id and observed_context and context_id != observed_context:
        raise AITransportError("A2A response changed its context identifier")
    task_id = observed_task or task_id
    context_id = observed_context or context_id
    if task_id or context_id:
        if callback(task_id, context_id) is False:
            raise AITransportError("A2A task checkpoint could not be persisted")
    return task_id, context_id


def _parts_text(parts: Any) -> str:
    if not isinstance(parts, list):
        return ""
    return "".join(
        part["text"]
        for part in parts
        if isinstance(part, dict) and part.get("kind") == "text" and isinstance(part.get("text"), str)
    )


def _extract_completed_text(result: dict[str, Any], artifacts: dict[str, dict[str, Any]]) -> str:  # noqa: C901
    """Extract only text attached to a completed A2A task."""
    if _a2a_state(result) != "completed":
        raise AITransportError("A2A task did not complete successfully")

    chunks: list[str] = []
    result_artifacts = result.get("artifacts")
    if isinstance(result_artifacts, list):
        for artifact in result_artifacts:
            if isinstance(artifact, dict):
                text = _parts_text(artifact.get("parts"))
                if text:
                    chunks.append(text)

    if not chunks:
        for artifact in artifacts.values():
            text = _parts_text(artifact.get("parts"))
            if text:
                chunks.append(text)

    if not chunks:
        status = result.get("status")
        message = status.get("message") if isinstance(status, dict) else None
        if isinstance(message, dict):
            text = _parts_text(message.get("parts"))
            if text:
                chunks.append(text)

    text = "\n".join(chunks).strip()
    if not text:
        raise AITransportError("A2A task completed without text output")
    return text


def _extract_direct_message_text(result: dict[str, Any]) -> str:
    """Validate and extract a completed A2A Message returned without a Task."""
    if (
        result.get("kind") != "message"
        or result.get("role") != "agent"
        or not isinstance(result.get("messageId"), str)
        or not result["messageId"]
        or not isinstance(result.get("parts"), list)
    ):
        raise AITransportError("A2A provider returned an invalid direct message")
    text = _parts_text(result["parts"]).strip()
    if not text:
        raise AITransportError("A2A direct message contained no text output")
    return text


def _rpc_payload(method: str, params: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": method, "params": params}


def _validate_rpc_response(payload: dict[str, Any], request_id: str) -> dict[str, Any]:
    if (
        set(payload) - {"jsonrpc", "id", "result", "error"}
        or payload.get("jsonrpc") != "2.0"
        or payload.get("id") != request_id
    ):
        raise AITransportError("A2A provider returned a mismatched JSON-RPC response")
    if ("result" in payload) == ("error" in payload):
        raise AITransportError("A2A provider returned an invalid JSON-RPC response")
    if "result" in payload and not isinstance(payload["result"], dict):
        raise AITransportError("A2A provider returned an invalid JSON-RPC result")
    if "error" in payload:
        error = payload["error"]
        if (
            not isinstance(error, dict)
            or type(error.get("code")) is not int
            or not isinstance(error.get("message"), str)
            or not error["message"]
            or set(error) - {"code", "message", "data"}
        ):
            raise AITransportError("A2A provider returned an invalid JSON-RPC error")
    return payload


def _require_task_id(result: dict[str, Any]) -> str:
    """Require a Task object and its canonical A2A id field."""
    if result.get("kind") != "task":
        raise AITransportError("A2A provider returned an invalid Task")
    task_id = result.get("id")
    if not isinstance(task_id, str) or not task_id:
        raise AITransportError("A2A Task response did not include a valid id")
    return task_id


def _message_params(message: str, context_id: str | None = None, task_id: str | None = None) -> dict[str, Any]:
    msg: dict[str, Any] = {
        "messageId": str(uuid.uuid4()),
        "role": "user",
        "parts": [{"kind": "text", "text": message}],
    }
    if context_id:
        msg["contextId"] = context_id
    if task_id:
        msg["taskId"] = task_id
    return {"message": msg}


class _StreamUnsupported(Exception):
    """The provider explicitly does not implement message/stream."""


def _iter_sse_json(  # noqa: C901
    response: requests.Response,
    *,
    request_id: str,
    deadline: float,
    max_total_bytes: int,
    max_line_bytes: int,
) -> Iterator[dict[str, Any]]:
    event_data: list[str] = []
    buffered_bytes = 0
    total_bytes = 0

    def parse_line(raw_line: bytes) -> dict[str, Any] | None:  # noqa: C901
        nonlocal buffered_bytes
        if raw_line.endswith(b"\r"):
            raw_line = raw_line[:-1]
        if not raw_line:
            if not event_data:
                return None
            payload = "\n".join(event_data)
            event_data.clear()
            buffered_bytes = 0
            if payload == "[DONE]":
                return None
            try:
                decoded = json.loads(payload)
            except json.JSONDecodeError as exc:
                raise AITransportError("Provider returned an invalid stream event", transient=True) from exc
            if not isinstance(decoded, dict):
                raise AITransportError("Provider returned an invalid JSON-RPC stream event")
            return _validate_rpc_response(decoded, request_id)

        if len(raw_line) > max_line_bytes:
            raise AITransportError("Provider stream line exceeded the configured size limit")
        if raw_line.startswith(b":"):
            return None
        if raw_line.startswith(b"data:"):
            raw_data = raw_line[5:].lstrip()
            buffered_bytes += len(raw_data)
            if buffered_bytes > max_total_bytes:
                raise AITransportError("Provider stream event exceeded the configured size limit")
            try:
                event_data.append(raw_data.decode("utf-8", errors="strict"))
            except UnicodeDecodeError as exc:
                raise AITransportError("Provider returned an invalid stream event") from exc
        return None

    line_buffer = bytearray()
    for chunk in _iter_response_content(response):
        if time.monotonic() >= deadline:
            raise AITransportError("Provider exceeded the run deadline", transient=True)
        if not chunk:
            continue
        total_bytes += len(chunk)
        if total_bytes > max_total_bytes:
            raise AITransportError("Provider stream exceeded the configured size limit")
        line_buffer.extend(chunk)
        while b"\n" in line_buffer:
            line, _, remainder = line_buffer.partition(b"\n")
            line_buffer = bytearray(remainder)
            if parsed := parse_line(bytes(line)):
                yield parsed
        if len(line_buffer) > max_line_bytes:
            raise AITransportError("Provider stream line exceeded the configured size limit")

    if line_buffer:
        if parsed := parse_line(bytes(line_buffer)):
            yield parsed
    if event_data:
        if parsed := parse_line(b""):
            yield parsed


def _absorb_artifact(event_result: dict[str, Any], artifacts: dict[str, dict[str, Any]], order: list[str]) -> None:
    artifact = event_result.get("artifact")
    if not isinstance(artifact, dict):
        return
    artifact_id = artifact.get("artifactId") or artifact.get("name") or str(len(order))
    raw_parts = artifact.get("parts")
    parts: list[Any] = raw_parts if isinstance(raw_parts, list) else []
    if event_result.get("append") and artifact_id in artifacts:
        artifacts[artifact_id].setdefault("parts", []).extend(parts)
    else:
        if artifact_id not in artifacts:
            order.append(artifact_id)
        artifacts[artifact_id] = {**artifact, "parts": list(parts)}


def _stream_a2a(  # noqa: C901
    session: requests.Session,
    endpoint: str,
    token: str,
    message: str,
    *,
    deadline: float,
    config: AITriage,
    checkpoint: Checkpoint,
    begin_attempt: BeginAttempt | None = None,
) -> str:  # noqa: C901
    request_body = _rpc_payload("message/stream", _message_params(message))
    request_id = request_body["id"]
    response: requests.Response | None = None
    artifacts: dict[str, dict[str, Any]] = {}
    artifact_order: list[str] = []
    task_id: str | None = None
    context_id: str | None = None
    final_result: dict[str, Any] | None = None
    saw_result = False

    try:
        _begin_attempt(begin_attempt)
        response = session.post(
            endpoint,
            json=request_body,
            headers=_safe_headers(config, token, streaming=True),
            timeout=_request_timeout(deadline - time.monotonic()),
            allow_redirects=False,
            stream=True,
        )
        if response.status_code >= 300:
            _raise_http_error(response)

        content_type = response.headers.get("content-type", "").lower()
        if "text/event-stream" not in content_type:
            payload = _validate_rpc_response(
                _read_bounded_json(response, config.max_sse_bytes, deadline=deadline),
                request_id,
            )
            if "error" in payload:
                error = payload.get("error")
                code = error.get("code") if isinstance(error, dict) else None
                if code in UNSUPPORTED_A2A_METHOD_CODES:
                    raise _StreamUnsupported()
                raise AITransportError("A2A provider rejected the request")
            result = payload.get("result")
            if isinstance(result, dict):
                if result.get("kind") == "message":
                    return _extract_direct_message_text(result)
                _require_task_id(result)
                task_id, context_id = _checkpoint(result, checkpoint, task_id, context_id)
                if not task_id:
                    raise AITransportError("A2A completed without a task identifier")
                state = _a2a_state(result)
                if state == "completed":
                    return _extract_completed_text(result, artifacts)
                if state in {"submitted", "working"}:
                    return _send_and_poll_a2a(
                        session,
                        endpoint,
                        token,
                        message,
                        deadline=deadline,
                        config=config,
                        checkpoint=checkpoint,
                        resume_task_id=task_id,
                        resume_context_id=context_id,
                    )
                raise AITransportError("A2A task did not complete successfully")
            raise AITransportError("A2A provider returned an invalid response")

        for event in _iter_sse_json(
            response,
            request_id=request_id,
            deadline=deadline,
            max_total_bytes=config.max_sse_bytes,
            max_line_bytes=config.max_sse_line_bytes,
        ):
            if "error" in event:
                error = event.get("error")
                code = error.get("code") if isinstance(error, dict) else None
                if code in UNSUPPORTED_A2A_METHOD_CODES:
                    if saw_result or task_id or context_id:
                        raise AITransportError("A2A stream failed after a task was accepted")
                    raise _StreamUnsupported()
                raise AITransportError("A2A provider rejected the request")
            result = event.get("result")
            if not isinstance(result, dict):
                continue
            saw_result = True
            if result.get("kind") == "message":
                if task_id or context_id:
                    raise AITransportError("A2A stream returned a direct message after accepting a task")
                return _extract_direct_message_text(result)
            if result.get("kind") == "task":
                _require_task_id(result)
            task_id, context_id = _checkpoint(result, checkpoint, task_id, context_id)
            if result.get("kind") == "artifact-update":
                _absorb_artifact(result, artifacts, artifact_order)
            elif result.get("kind") == "task":
                for artifact in result.get("artifacts") or []:
                    if isinstance(artifact, dict):
                        _absorb_artifact({"artifact": artifact}, artifacts, artifact_order)
                final_result = result
            elif result.get("kind") == "status-update":
                status = result.get("status")
                if isinstance(status, dict) and status.get("state") in TERMINAL_A2A_STATES:
                    final_result = {**result, "status": status}
            elif _a2a_state(result) in TERMINAL_A2A_STATES:
                final_result = result

            if final_result and _a2a_state(final_result) in TERMINAL_A2A_STATES:
                if not task_id:
                    raise AITransportError("A2A completed without a task identifier")
                return _extract_completed_text(final_result, artifacts)

        raise AITransportError("A2A stream ended before the task completed", transient=True)
    finally:
        if response is not None:
            response.close()


def _post_a2a_json(
    session: requests.Session,
    endpoint: str,
    token: str,
    method: str,
    params: dict[str, Any],
    *,
    deadline: float,
    config: AITriage,
) -> dict[str, Any]:
    request_body = _rpc_payload(method, params)
    remaining = deadline - time.monotonic()
    try:
        response = session.post(
            endpoint,
            json=request_body,
            headers=_safe_headers(config, token),
            timeout=_request_timeout(remaining),
            allow_redirects=False,
            stream=True,
        )
    except (requests.Timeout, requests.ConnectionError, requests.exceptions.ChunkedEncodingError) as exc:
        raise AITransportError("A2A provider is temporarily unavailable", transient=True) from exc
    with response:
        if response.status_code >= 300:
            _raise_http_error(response)
        payload = _validate_rpc_response(
            _read_bounded_json(response, config.max_output_bytes, deadline=deadline),
            request_body["id"],
        )
    if "error" in payload:
        error = payload.get("error")
        code = error.get("code") if isinstance(error, dict) else None
        if code in UNSUPPORTED_A2A_METHOD_CODES:
            raise AITransportError("A2A provider does not support the requested method")
        raise AITransportError("A2A provider rejected the request")
    return payload


def _send_and_poll_a2a(  # noqa: C901
    session: requests.Session,
    endpoint: str,
    token: str,
    message: str,
    *,
    deadline: float,
    config: AITriage,
    checkpoint: Checkpoint,
    resume_task_id: str | None = None,
    resume_context_id: str | None = None,
) -> str:  # noqa: C901
    task_id = resume_task_id
    context_id = resume_context_id
    if task_id is None:
        if context_id:
            raise AITransportError("A2A context checkpoint has no task identifier; refusing to start a duplicate task")
        response = _post_a2a_json(
            session,
            endpoint,
            token,
            "message/send",
            _message_params(message),
            deadline=deadline,
            config=config,
        )
        result = response.get("result")
        if not isinstance(result, dict):
            raise AITransportError("A2A provider returned an invalid response")
        if result.get("kind") == "message":
            return _extract_direct_message_text(result)
        response_task_id = _require_task_id(result)
        task_id, context_id = _checkpoint(result, checkpoint, task_id, context_id)
        if task_id != response_task_id:
            raise AITransportError("A2A provider returned a mismatched task identifier")
        state = _a2a_state(result)
        if state == "completed":
            if not task_id:
                raise AITransportError("A2A completed without a task identifier")
            return _extract_completed_text(result, {})
        if state in {"failed", "canceled", "cancelled", "rejected", "input-required", "auth-required"}:
            raise AITransportError("A2A task did not complete successfully")
        if not task_id:
            raise AITransportError("A2A response did not include a task identifier")
        if state not in {"submitted", "working"}:
            raise AITransportError("A2A response did not contain a resumable task state")

    while time.monotonic() < deadline:
        time.sleep(min(1.0, max(0.01, deadline - time.monotonic())))
        if time.monotonic() >= deadline:
            break
        payload = _post_a2a_json(
            session,
            endpoint,
            token,
            "tasks/get",
            {"id": task_id},
            deadline=deadline,
            config=config,
        )
        result = payload.get("result")
        if not isinstance(result, dict):
            raise AITransportError("A2A provider returned an invalid task response")
        observed_task_id = _require_task_id(result)
        if observed_task_id != task_id:
            raise AITransportError("A2A provider returned a mismatched task identifier")
        task_id, context_id = _checkpoint(result, checkpoint, task_id, context_id)
        state = _a2a_state(result)
        if state == "completed":
            if not task_id:
                raise AITransportError("A2A completed without a task identifier")
            return _extract_completed_text(result, {})
        if state in {"failed", "canceled", "cancelled", "rejected", "input-required", "auth-required"}:
            raise AITransportError("A2A task did not complete successfully")
        if state not in {"submitted", "working"}:
            raise AITransportError("A2A task returned an invalid state")
    raise AITransportError("A2A task exceeded the run deadline", transient=True)


def _openai_chat(
    session: requests.Session,
    config: AITriage,
    endpoint: str,
    token: str,
    system_prompt: str,
    alert_json: str,
    *,
    deadline: float,
    begin_attempt: BeginAttempt | None = None,
) -> str:
    body = {
        **config.extra_body,
        "model": config.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": alert_json},
        ],
        "stream": False,
    }
    try:
        _begin_attempt(begin_attempt)
        response = session.post(
            endpoint,
            json=body,
            headers=_safe_headers(config, token),
            timeout=_request_timeout(deadline - time.monotonic()),
            allow_redirects=False,
            stream=True,
        )
    except (requests.Timeout, requests.ConnectionError, requests.exceptions.ChunkedEncodingError) as exc:
        raise AITransportError("AI provider is temporarily unavailable", transient=True) from exc

    with response:
        if response.status_code >= 300:
            _raise_http_error(response)
        payload = _read_bounded_json(response, config.max_output_bytes, deadline=deadline)

    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise AITransportError("AI provider returned an invalid chat completion")
    message = choices[0].get("message")
    if choices[0].get("finish_reason") != "stop":
        raise AITransportError("AI provider did not complete the chat response")
    if not isinstance(message, dict) or message.get("role") != "assistant":
        raise AITransportError("AI provider returned an invalid assistant message")
    if message.get("tool_calls") or message.get("function_call"):
        raise AITransportError("AI provider returned a tool call; tools are not supported")
    text = message.get("content")
    if not isinstance(text, str) or not text.strip():
        raise AITransportError("AI provider returned no completed text")
    return text.strip()


def generate(  # noqa: C901
    config: AITriage,
    token: str,
    system_prompt: str,
    alert_data: dict[str, Any],
    *,
    deadline: float,
    checkpoint: Checkpoint,
    begin_attempt: BeginAttempt | None = None,
    resume_task_id: str | None = None,
    resume_context_id: str | None = None,
) -> str:
    """Generate a bounded response from the configured provider.

    All outbound requests use the trusted bearer supplied by the shared action
    dispatcher. Provider headers cannot replace authorization or protocol fields.
    """
    if not token:
        raise AITransportError("A Bearer authorization token is required")
    endpoint = config.endpoint
    if not config.locally_valid() or not endpoint:
        raise AITransportError("AI triage is not configured")
    if deadline <= time.monotonic():
        raise AITransportError("AI triage run exceeded its deadline")
    provider_deadline = min(deadline, time.monotonic() + float(config.timeout_seconds))

    alert_json = json.dumps(alert_data, ensure_ascii=False, separators=(",", ":"))
    input_size = len(alert_json.encode("utf-8")) + len(system_prompt.encode("utf-8"))
    if config.provider == "openai":
        input_size += len(json.dumps(config.extra_body, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    if input_size > config.max_input_bytes:
        raise AITransportError("Alert input exceeded the configured size limit")
    if time.monotonic() >= provider_deadline:
        raise AITransportError("AI triage exceeded its deadline", transient=True)

    session = _session()
    try:
        provider_remaining = provider_deadline - time.monotonic()
        if provider_remaining <= 0:
            raise AITransportError("AI triage exceeded its configured provider timeout", transient=True)
        # Requests' read timeout is an inactivity bound. A server that sends a
        # byte frequently can keep a Content-Length read(8192) blocked forever,
        # so also enforce the absolute provider budget around the whole body
        # read. Unwinding closes the active Response context before the Session.
        with gevent.Timeout(
            provider_remaining,
            AITransportError("AI triage exceeded its configured provider timeout", transient=True),
        ):
            if config.provider == "openai":
                result = _openai_chat(
                    session,
                    config,
                    endpoint,
                    token,
                    system_prompt,
                    alert_json,
                    deadline=provider_deadline,
                    begin_attempt=begin_attempt,
                )
            else:
                a2a_message = f"{system_prompt}\n\nAlert data (JSON):\n{alert_json}"
                if resume_task_id or resume_context_id:
                    result = _send_and_poll_a2a(
                        session,
                        endpoint,
                        token,
                        a2a_message,
                        deadline=provider_deadline,
                        config=config,
                        checkpoint=checkpoint,
                        resume_task_id=resume_task_id,
                        resume_context_id=resume_context_id,
                    )
                else:
                    try:
                        result = _stream_a2a(
                            session,
                            endpoint,
                            token,
                            a2a_message,
                            deadline=provider_deadline,
                            config=config,
                            checkpoint=checkpoint,
                            begin_attempt=begin_attempt,
                        )
                    except _StreamUnsupported:
                        # Only an explicit unsupported response before task acceptance
                        # may fall back; both paths share the same immutable deadline.
                        result = _send_and_poll_a2a(
                            session,
                            endpoint,
                            token,
                            a2a_message,
                            deadline=provider_deadline,
                            config=config,
                            checkpoint=checkpoint,
                        )
    except requests.Timeout as exc:
        raise AITransportError("AI provider is temporarily unavailable", transient=True) from exc
    except requests.exceptions.ChunkedEncodingError as exc:
        # A2A checkpoints are durable before subsequent stream reads, so the
        # caller can resume tasks/get rather than submit a second message.
        raise AITransportError("AI provider response was interrupted", transient=True) from exc
    except requests.ConnectionError as exc:
        raise AITransportError("AI provider is temporarily unavailable", transient=True) from exc
    finally:
        session.close()

    if time.monotonic() >= provider_deadline:
        raise AITransportError("AI triage exceeded its deadline", transient=True)
    if len(result.encode("utf-8")) > config.max_output_bytes:
        raise AITransportError("Provider output exceeded the configured size limit")
    return result
