import json
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest
from pydantic import ValidationError

from howler.config import config
from howler.odm.models.config import AIAgent, AIConfig, AILucene
from howler.services import agent_service
from howler.services.ai_service import AITransportError

SETTINGS = AIAgent(agent_url="https://agent.invalid/howler/", broker_url="https://broker.invalid/")


@pytest.fixture
def session(monkeypatch):
    session = MagicMock()
    session.__enter__.return_value = session
    monkeypatch.setattr(agent_service.requests, "Session", Mock(return_value=session))
    session.post.side_effect = lambda _url, **kwargs: kwargs["hooks"]["response"](session.reply)
    return session


def reply(session, status=200, *, json_body=None, lines=None, content_type="text/event-stream"):
    session.reply = MagicMock(status_code=status, headers={"Content-Type": content_type})
    session.reply.__enter__.return_value = session.reply
    session.reply.json.return_value = json_body
    session.reply.iter_lines.return_value = iter(lines or [])
    return session.reply


def plugin(token_functions):
    return SimpleNamespace(modules=SimpleNamespace(token_functions=token_functions))


def test_delegated_token_prefers_plugin_then_azure_scope_and_never_falls_back(monkeypatch):
    monkeypatch.setattr(config.core, "ai", AIConfig(lucene={"agent": {"scope": "api://agent/.default"}}))
    azure_obo = Mock(return_value="azure-delegated-token")
    monkeypatch.setattr(agent_service, "azure_obo", azure_obo)

    monkeypatch.setattr(agent_service, "get_plugins", lambda: [plugin({}), plugin({"ai_agent": lambda t: f"p-{t}"})])
    assert agent_service.get_delegated_token.uncached("howler-token") == "p-howler-token"
    azure_obo.assert_not_called()

    monkeypatch.setattr(agent_service, "get_plugins", lambda: [])
    assert agent_service.get_delegated_token.uncached("howler-token") == "azure-delegated-token"
    azure_obo.assert_called_once_with("howler-token", scope="api://agent/.default")

    monkeypatch.setattr(config.core, "ai", AIConfig())
    with pytest.raises(AITransportError, match="AI agent delegation is not configured"):
        agent_service.get_delegated_token.uncached("howler-token")


def test_agent_token_exchanges_delegated_token_with_broker(session, monkeypatch):
    monkeypatch.setattr(agent_service, "get_delegated_token", lambda token: f"delegated-{token}")
    reply(session, json_body={"access_token": "agent-token"})

    assert agent_service.get_agent_token(SETTINGS, "howler-token") == "agent-token"

    args, kwargs = session.post.call_args
    assert args == ("https://broker.invalid/v1/auth/broker/exchange",)
    assert kwargs["json"] == {
        "subject_token": "delegated-howler-token",
        "mcp_server_url": "https://agent.invalid/howler",
    }
    assert kwargs["allow_redirects"] is False
    assert session.trust_env is False

    agent_service.get_agent_token(SETTINGS.model_copy(update={"broker_token_field": "platform_token"}), "howler-token")
    assert session.post.call_args.kwargs["json"]["platform_token"] == "delegated-howler-token"


@pytest.mark.parametrize(
    ("status", "body", "reason"),
    [
        (401, None, "The token broker denied access. Check delegated permissions and user authorization."),
        (404, None, "The token broker or its endpoint was not found."),
        (200, {"access_token": "bad token"}, "The token broker returned an invalid access token."),
        (200, ["unexpected"], "The token broker returned an invalid access token."),
    ],
)
def test_agent_token_rejects_broker_failures(session, monkeypatch, status, body, reason):
    monkeypatch.setattr(agent_service, "get_delegated_token", lambda token: token)
    reply(session, status, json_body=body)

    with pytest.raises(AITransportError) as error:
        agent_service.get_agent_token(SETTINGS, "howler-token")

    assert error.value.reason == reason


def test_agent_token_hides_obo_failure_details(session, monkeypatch):
    monkeypatch.setattr(
        agent_service, "get_delegated_token", Mock(side_effect=RuntimeError("Azure OBO failed. Reason: secret"))
    )

    with pytest.raises(AITransportError) as error:
        agent_service.get_agent_token(SETTINGS, "howler-token")

    assert error.value.reason == "Failed to obtain AI agent access."
    session.post.assert_not_called()


def envelope(request_id, result):
    return b"data: " + json.dumps({"jsonrpc": "2.0", "id": request_id, "result": result}).encode()


def frames(session, *results, request_id=None):
    """Reply with SSE frames whose JSON-RPC id matches the outgoing request."""

    def iter_lines(chunk_size):
        assert chunk_size is None
        rid = request_id or session.post.call_args.kwargs["json"]["id"]
        for result in results:
            yield envelope(rid, result)
            yield b""

    reply(session)
    session.reply.iter_lines.side_effect = iter_lines


def artifact(text, append=False, artifact_id="query"):
    return {
        "kind": "artifact-update",
        "append": append,
        "artifact": {"artifactId": artifact_id, "parts": [{"kind": "text", "text": text}]},
    }


def status(state, text=None, final=False, role="agent"):
    message = {"role": role, "parts": [{"kind": "text", "text": text}]} if text else None
    return {"kind": "status-update", "final": final, "status": {"state": state, "message": message}}


def test_stream_message_sends_a2a_request_and_streams_artifacts(session):
    frames(
        session,
        {"kind": "task", "id": "task-1", "status": {"state": "submitted"}},
        status("working", "open hits"),
        status("working", "echoed request", role="user"),
        status("working", "Looking up hit fields"),
        artifact("howler.status"),
        artifact(":open", append=True),
        status("completed", final=True),
    )

    assert list(agent_service.stream_message(SETTINGS, "agent-token", "open hits")) == [
        ("status", "Looking up hit fields"),
        ("text", "howler.status"),
        ("text", "howler.status:open"),
    ]

    args, kwargs = session.post.call_args
    assert args == ("https://agent.invalid/howler/",)
    assert kwargs["headers"]["Authorization"] == "Bearer agent-token"
    assert kwargs["headers"]["Accept"] == "text/event-stream"
    assert kwargs["allow_redirects"] is False
    assert kwargs["json"]["method"] == "message/stream"
    message = kwargs["json"]["params"]["message"]
    assert (message["role"], message["kind"], message["parts"]) == (
        "user",
        "message",
        [{"kind": "text", "text": "open hits"}],
    )


@pytest.mark.parametrize(
    "final",
    [
        {"kind": "message", "parts": [{"kind": "text", "text": "howler.status:open"}]},
        status("completed", "howler.status:open", final=True),
        {
            "kind": "task",
            "status": {"state": "completed"},
            "artifacts": [{"artifactId": "a", "parts": [{"kind": "text", "text": "howler.status:open"}]}],
        },
    ],
)
def test_stream_message_uses_final_answer_without_streamed_artifacts(session, final):
    frames(session, final)

    assert list(agent_service.stream_message(SETTINGS, "agent-token", "open hits"))[-1] == (
        "text",
        "howler.status:open",
    )


@pytest.mark.parametrize(
    ("results", "request_id", "reason"),
    [
        (
            [status("failed", "secret stack trace", final=True)],
            None,
            "The AI agent could not complete the request.",
        ),
        (
            [status("input-required", "Which time range?", final=True)],
            None,
            "The AI agent needs more information: Which time range?",
        ),
        ([status("auth-required", final=True)], None, "The AI agent requires additional authorization."),
        ([status("working", "Thinking")], None, "The AI agent stream ended before a final result."),
        (
            [status("completed", final=True)],
            "other-request",
            "The AI agent returned an invalid JSON-RPC response.",
        ),
        ([{"kind": "unexpected"}], None, "The AI agent returned an invalid result."),
    ],
)
def test_stream_message_rejects_failed_or_invalid_streams(session, results, request_id, reason):
    frames(session, *results, request_id=request_id)

    with pytest.raises(AITransportError) as error:
        list(agent_service.stream_message(SETTINGS, "agent-token", "open hits"))

    assert error.value.reason == reason


@pytest.mark.parametrize(
    ("status", "reason"),
    [
        (403, "The AI agent denied access. Check delegated permissions and user authorization."),
        (503, "The AI agent returned HTTP 503"),
    ],
)
def test_stream_message_reports_agent_http_failures(session, status, reason):
    reply(session, status)

    with pytest.raises(AITransportError) as error:
        list(agent_service.stream_message(SETTINGS, "agent-token", "open hits"))

    assert error.value.reason == reason


def test_has_delegation_accepts_a_plugin_token_function_or_scope(monkeypatch):
    monkeypatch.setattr(config.core, "ai", AIConfig())
    monkeypatch.setattr(agent_service, "get_plugins", lambda: [plugin({})])
    assert agent_service.has_delegation() is False

    monkeypatch.setattr(agent_service, "get_plugins", lambda: [plugin({"ai_agent": lambda token: token})])
    assert agent_service.has_delegation() is True

    monkeypatch.setattr(agent_service, "get_plugins", lambda: [])
    monkeypatch.setattr(config.core, "ai", AIConfig(lucene={"agent": {"scope": "api://agent/.default"}}))
    assert agent_service.has_delegation() is True


def test_stream_message_rejects_non_event_stream(session):
    reply(session, content_type="application/json")

    with pytest.raises(AITransportError, match="did not return an event stream"):
        list(agent_service.stream_message(SETTINGS, "agent-token", "open hits"))


def test_agent_provider_requires_agent_and_broker_urls():
    with pytest.raises(ValidationError, match="AI agent URL is required"):
        AILucene(enabled=True, provider="agent")

    with pytest.raises(ValidationError, match="Token broker URL must use HTTPS"):
        AILucene(
            enabled=True,
            provider="agent",
            agent={"agent_url": "https://agent.invalid", "broker_url": "http://broker.invalid"},
        )
