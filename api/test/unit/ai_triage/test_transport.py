import json
import time
from unittest.mock import MagicMock, Mock

import pytest

from howler.odm.models.config import AITriage
from howler.services import ai_transport as transport


def json_response(payload, *, status=200):
    response = MagicMock()
    response.status_code = status
    response.iter_content.return_value = [json.dumps(payload).encode()]
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    return response


def settings():
    return AITriage(
        enabled=True,
        endpoint="https://ai.invalid/v1/chat/completions",
        model="qa-model",
        headers={"X-Provider-Key": "private-key"},
    )


def generate(session, monkeypatch):
    monkeypatch.setattr(transport.requests, "Session", Mock(return_value=session))
    return transport.generate(
        settings(),
        "qa-access-token",
        "Conservative system prompt",
        {"event": "alert"},
        deadline=time.monotonic() + 30,
    )


def test_openai_success_uses_bearer_and_closes_session(monkeypatch):
    session = Mock()
    session.post.return_value = json_response({"choices": [{"message": {"content": "Conservative opinion"}}]})

    assert generate(session, monkeypatch) == "Conservative opinion"

    call = session.post.call_args
    assert call.args == ("https://ai.invalid/v1/chat/completions",)
    assert call.kwargs["headers"] == {
        "X-Provider-Key": "private-key",
        "Authorization": "Bearer qa-access-token",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    assert call.kwargs["json"] == {
        "model": "qa-model",
        "messages": [
            {"role": "system", "content": "Conservative system prompt"},
            {"role": "user", "content": '{"event":"alert"}'},
        ],
        "stream": False,
    }
    assert call.kwargs["allow_redirects"] is False
    assert call.kwargs["stream"] is True
    assert session.trust_env is False
    session.close.assert_called_once()


def test_openai_auth_error_is_reported_without_upstream_details(monkeypatch):
    session = Mock()
    session.post.return_value = json_response({"error": "private provider detail"}, status=401)

    with pytest.raises(transport.AITransportError, match="authorization token") as error:
        generate(session, monkeypatch)

    assert "private provider detail" not in str(error.value)
    session.close.assert_called_once()


def test_non_auth_http_error_only_exposes_status(monkeypatch):
    session = Mock()
    session.post.return_value = json_response({"error": "secret"}, status=503)

    with pytest.raises(transport.AITransportError, match="HTTP 503") as error:
        generate(session, monkeypatch)

    assert "secret" not in str(error.value)
    session.close.assert_called_once()


def test_timeout_becomes_safe_transport_error(monkeypatch):
    session = Mock()
    session.post.side_effect = transport.requests.Timeout("provider-secret")

    with pytest.raises(transport.AITransportError, match="temporarily unavailable") as error:
        generate(session, monkeypatch)

    assert "provider-secret" not in str(error.value)
    session.close.assert_called_once()
