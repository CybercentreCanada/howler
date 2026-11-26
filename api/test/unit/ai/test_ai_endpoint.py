import json
import time
from unittest.mock import Mock, patch

import pytest
from flask import Flask

from howler.config import config
from howler.odm.models.config import AIConfig
from howler.services import agent_service, ai_lucene_service, ai_service

from .support import make_user


@pytest.fixture(autouse=True)
def isolated_generation(monkeypatch):
    monkeypatch.setattr(ai_lucene_service, "_slots", None)
    monkeypatch.setattr(ai_lucene_service, "_query_warning", lambda _query: None)


@pytest.fixture
def lucene_enabled(monkeypatch):
    settings = AIConfig(enabled=True, endpoint="https://ai.invalid/chat", model="qa-model", lucene={"enabled": True})
    monkeypatch.setattr(config.core, "ai", settings)
    monkeypatch.setattr(ai_lucene_service, "_field_context", lambda: "howler.status: enum[open]")


def call_route(headers=None, body=None):
    app = Flask("ai_lucene_test")
    app.config.update(SECRET_KEY="test secret")
    with (
        patch("howler.security.login.auth_service") as login_auth,
        patch("howler.security.login.QUOTA_TRACKER") as login_quota,
        patch("howler.api.QUOTA_TRACKER"),
    ):
        login_auth.bearer_auth.return_value = (make_user(), ["R"])
        login_auth.basic_auth.return_value = (make_user(), ["R"])
        login_auth.decode_b64.return_value = "target:apikey"
        login_auth.validate_apikey.return_value = (make_user("target"), ["R"])
        login_quota.begin.return_value = True
        with app.test_request_context(
            method="POST",
            path="/api/v2/ai/lucene",
            headers=headers or {"Authorization": "Bearer oauth.access.token"},
            json={"prompt": "open hits"} if body is None else body,
        ):
            from howler.api.v2.ai import generate_lucene

            response = generate_lucene()
            return response, response.get_data(as_text=True) if response.status_code == 200 else None


def test_route_rejects_when_disabled(monkeypatch):
    monkeypatch.setattr(config.core, "ai", AIConfig())
    response, _ = call_route()

    assert response.status_code == 400
    assert response.get_json()["api_error_message"] == "AI query generation is not enabled."


@pytest.mark.usefixtures("lucene_enabled")
@pytest.mark.parametrize(
    ("headers", "body", "error"),
    [
        (None, {"prompt": " "}, "A natural-language prompt is required."),
        (None, {"prompt": "x" * 2001}, "The prompt cannot exceed 2000 characters."),
        ({"Authorization": "Basic dXNlcjpwYXNz"}, None, "AI query generation requires a Bearer authorization token."),
    ],
)
def test_route_rejects_invalid_requests(headers, body, error):
    response, _ = call_route(headers, body)

    assert response.status_code == 400
    assert response.get_json()["api_error_message"] == error


@pytest.mark.usefixtures("lucene_enabled")
def test_route_streams_with_forwarded_token(monkeypatch):
    stream_chat = Mock(return_value=iter(["```lucene\nhowler.status", ":open\n```", "\nBecause."]))
    monkeypatch.setattr(ai_service, "stream_chat", stream_chat)

    response, body = call_route(body={"prompt": "open hits", "query": "a:b"})

    assert response.status_code == 200
    assert response.mimetype == "text/event-stream"
    assert response.headers["X-Accel-Buffering"] == "no"
    assert 'data: {"text": "howler.status"}' in body
    assert 'data: {"text": "howler.status:open"}' in body
    done = {"query": "howler.status:open", "response": "```lucene\nhowler.status:open\n```\nBecause."}
    assert body.endswith(f"event: done\ndata: {json.dumps(done)}\n\n")
    assert stream_chat.call_args.args[1] == "oauth.access.token"
    assert stream_chat.call_args.args[2][1]["content"] == "Request:\nopen hits\n\nCurrent query:\na:b"


@pytest.mark.usefixtures("lucene_enabled")
def test_route_rejects_generations_over_the_concurrency_limit(monkeypatch):
    monkeypatch.setattr(
        ai_lucene_service, "start_generation", Mock(side_effect=ai_lucene_service.GenerationBusyError())
    )

    response, _ = call_route()

    assert response.status_code == 429
    assert response.get_json()["api_error_message"].startswith("Too many AI query generations")


@pytest.fixture
def agent_enabled(monkeypatch):
    lucene = {
        "enabled": True,
        "provider": "agent",
        "agent": {
            "agent_url": "https://agent.invalid/howler/",
            "broker_url": "https://broker.invalid",
            "scope": "api://agent/.default",
        },
    }
    monkeypatch.setattr(config.core, "ai", AIConfig(lucene=lucene))


@pytest.mark.usefixtures("agent_enabled")
@pytest.mark.parametrize(
    "authorization",
    ["Basic dXNlcjpwYXNz", "Bearer analyst:internal-token"],
)
def test_agent_route_is_available_without_core_ai_and_requires_oauth(monkeypatch, authorization):
    get_agent_token = Mock()
    monkeypatch.setattr(agent_service, "get_agent_token", get_agent_token)

    response, _ = call_route(headers={"Authorization": authorization})

    assert ai_lucene_service.is_available() is True
    assert response.status_code == 400
    assert response.get_json()["api_error_message"] == (
        "AI query generation with an AI agent requires signing in with OAuth."
    )
    get_agent_token.assert_not_called()


@pytest.mark.usefixtures("agent_enabled")
def test_agent_route_rejects_impersonated_requests(monkeypatch):
    get_agent_token = Mock()
    monkeypatch.setattr(agent_service, "get_agent_token", get_agent_token)

    response, _ = call_route(
        headers={"Authorization": "Bearer oauth.access.token", "X-Impersonating": "Basic dGFyZ2V0OmFwaWtleQ=="}
    )

    assert response.status_code == 400
    assert response.get_json()["api_error_message"] == (
        "AI query generation with an AI agent is not available while impersonating another user."
    )
    get_agent_token.assert_not_called()


@pytest.mark.usefixtures("agent_enabled")
def test_agent_route_reports_access_failures_before_streaming(monkeypatch):
    monkeypatch.setattr(
        agent_service,
        "get_agent_token",
        Mock(side_effect=ai_service.AITransportError("Failed to obtain AI agent access.")),
    )

    response, _ = call_route()

    assert response.status_code == 502
    assert response.get_json()["api_error_message"] == "Failed to obtain AI agent access."


@pytest.mark.usefixtures("agent_enabled")
def test_agent_route_streams_agent_answer_without_field_list(monkeypatch):
    get_agent_token = Mock(return_value="agent-token")
    answer = "```lucene\nhowler.status:open\n```\nOpen hits use howler.status."
    stream_message = Mock(return_value=iter([("status", "Checking fields"), ("text", answer)]))
    monkeypatch.setattr(agent_service, "get_agent_token", get_agent_token)
    monkeypatch.setattr(agent_service, "stream_message", stream_message)

    response, body = call_route()

    assert response.status_code == 200
    assert 'event: status\ndata: {"status": "Checking fields"}' in body
    assert 'data: {"text": "howler.status:open"}' in body
    assert body.endswith(f"event: done\ndata: {json.dumps({'query': 'howler.status:open', 'response': answer})}\n\n")
    assert get_agent_token.call_args.args[1] == "oauth.access.token"
    settings, token, text, deadline = stream_message.call_args.args
    assert 179 < deadline - time.monotonic() <= 180
    assert (settings.agent_url, token) == ("https://agent.invalid/howler/", "agent-token")
    assert text.endswith("Request:\nopen hits")
    assert "Searchable hit fields" not in text
