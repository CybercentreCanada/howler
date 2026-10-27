import json as json_module
import time
from unittest.mock import MagicMock, Mock

import pytest

from howler.odm.models.config import AITriage
from howler.services import ai_transport as transport


def json_response(payload, *, status=200, content_type="application/json"):
    response = MagicMock()
    response.status_code = status
    response.headers = {"content-type": content_type}
    response.iter_content.return_value = [json_module.dumps(payload).encode()]
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    return response


def settings(provider):
    return AITriage(
        enabled=True,
        provider=provider,
        endpoint="https://ai.invalid/triage",
        model="qa-model",
    )


def run(provider, session, *, checkpoint=None):
    return transport.generate(
        settings(provider),
        "qa-access-token",
        "Conservative system prompt",
        {"event": "alert"},
        deadline=time.monotonic() + 30,
        checkpoint=checkpoint or Mock(),
    )


def test_openai_success_uses_bearer_and_closes_session(monkeypatch):
    session = Mock()
    session.post.return_value = json_response(
        {"choices": [{"message": {"role": "assistant", "content": "Conservative opinion"}, "finish_reason": "stop"}]}
    )
    monkeypatch.setattr(transport.requests, "Session", Mock(return_value=session))

    assert run("openai", session) == "Conservative opinion"

    call = session.post.call_args.kwargs
    assert call["headers"]["Authorization"] == "Bearer qa-access-token"
    assert call["json"]["stream"] is False
    assert call["allow_redirects"] is False
    assert session.close.called


def test_openai_auth_error_is_reported_without_upstream_details(monkeypatch):
    session = Mock()
    session.post.return_value = json_response({"error": "private provider detail"}, status=401)
    monkeypatch.setattr(transport.requests, "Session", Mock(return_value=session))

    with pytest.raises(transport.AITransportError, match="authorization token") as error:
        run("openai", session)

    assert "private provider detail" not in str(error.value)
    session.close.assert_called_once()


def test_a2a_direct_message_success(monkeypatch):
    session = Mock()
    response = json_response({})

    def post(_endpoint, *, json: dict, **_kwargs):
        response.iter_content.return_value = [
            json_module.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": json["id"],
                    "result": {
                        "kind": "message",
                        "role": "agent",
                        "messageId": "message-1",
                        "parts": [{"kind": "text", "text": "A2A opinion"}],
                    },
                }
            ).encode()
        ]
        return response

    session.post.side_effect = post
    monkeypatch.setattr(transport.requests, "Session", Mock(return_value=session))
    checkpoint = Mock()

    assert run("a2a", session, checkpoint=checkpoint) == "A2A opinion"

    assert session.post.call_args.kwargs["headers"]["Authorization"] == "Bearer qa-access-token"
    response.close.assert_called_once()
    session.close.assert_called_once()
    checkpoint.assert_not_called()


def test_a2a_error_response_is_safe_and_does_not_retry(monkeypatch):
    session = Mock()
    response = json_response({})

    def post(_endpoint, *, json: dict, **_kwargs):
        response.iter_content.return_value = [
            json_module.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": json["id"],
                    "error": {"code": -32000, "message": "private upstream detail"},
                }
            ).encode()
        ]
        return response

    session.post.side_effect = post
    monkeypatch.setattr(transport.requests, "Session", Mock(return_value=session))

    with pytest.raises(transport.AITransportError, match="rejected the request") as error:
        run("a2a", session)

    assert session.post.call_count == 1
    assert "private upstream detail" not in str(error.value)
    session.close.assert_called_once()
