import json
from unittest.mock import MagicMock, Mock

import pytest
import requests
from pydantic import ValidationError
from urllib3.exceptions import ReadTimeoutError

from howler.odm.models.config import AITriage
from howler.services import ai_service as transport


@pytest.fixture
def provider(monkeypatch):
    session = MagicMock()
    session.__enter__.return_value = session
    factory = Mock(return_value=session)
    monkeypatch.setattr(transport.requests, "Session", factory)

    def post(_endpoint, **kwargs):
        reply = session.reply
        return kwargs["hooks"]["response"](reply)

    session.post.side_effect = post
    return session, factory


def response(payload, status=200):
    result = MagicMock(status_code=status)
    result.json.return_value = payload
    result.__enter__.return_value = result
    return result


def generate(
    *, prompt="Conservative system prompt", alert=None, model="qa-model", endpoint="https://ai.invalid/chat", timeout=30
):
    return transport.generate(
        AITriage(
            enabled=True,
            endpoint=endpoint,
            model=model,
            headers={"X-Provider-Key": "private-key"},
            timeout_seconds=timeout,
        ),
        "qa-access-token",
        prompt,
        {"event": "alert"} if alert is None else alert,
    )


def test_success_preserves_request_security_and_cleans_up(provider, monkeypatch):
    session, factory = provider
    monkeypatch.setenv("HTTPS_PROXY", "https://proxy.invalid")
    monkeypatch.setenv("NETRC", "/nonexistent/private-credentials")
    reply = response({"choices": [{"message": {"content": "  Conservative opinion  "}}]})
    session.reply = reply

    assert generate() == "Conservative opinion"

    args, kwargs = session.post.call_args
    assert args == ("https://ai.invalid/chat",)
    assert kwargs["headers"] == {
        "X-Provider-Key": "private-key",
        "Authorization": "Bearer qa-access-token",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    assert kwargs["json"] == {
        "model": "qa-model",
        "messages": [
            {"role": "system", "content": "Conservative system prompt"},
            {"role": "user", "content": '{"event":"alert"}'},
        ],
        "stream": False,
    }
    assert kwargs["allow_redirects"] is False and kwargs["stream"] is True
    assert kwargs["timeout"] == (10, 30)
    assert session.trust_env is False
    factory.assert_called_once_with()
    session.__exit__.assert_called_once()
    reply.__exit__.assert_called_once()


@pytest.mark.parametrize("token", [None, "incoming-token"])
def test_provider_api_key_takes_precedence_over_incoming_token(provider, token):
    session, _factory = provider
    session.reply = response({"choices": [{"message": {"content": "opinion"}}]})
    config = AITriage(enabled=True, endpoint="https://ai.invalid/chat", model="model", api_key="provider-secret")

    assert transport.generate(config, token, "prompt", {}) == "opinion"

    assert session.post.call_args.kwargs["headers"]["Authorization"] == "Bearer provider-secret"
    assert "incoming-token" not in repr(session.post.call_args)


def test_missing_provider_credential_never_contacts_provider(provider):
    _session, factory = provider
    config = AITriage(enabled=True, endpoint="https://ai.invalid/chat", model="model")

    with pytest.raises(transport.AITransportError, match="provider credential"):
        transport.generate(config, None, "prompt", {})

    factory.assert_not_called()


def test_connect_timeout_is_bounded_by_configured_timeout(provider):
    session, _factory = provider
    session.reply = response({"choices": [{"message": {"content": "opinion"}}]})
    assert generate(timeout=3) == "opinion"
    assert session.post.call_args.kwargs["timeout"] == (3, 3)


@pytest.mark.parametrize(
    "status,reason", [(401, "authorization token"), (403, "authorization token"), (503, "HTTP 503"), (302, "HTTP 302")]
)
def test_http_errors_do_not_read_or_expose_provider_details(provider, status, reason):
    session, _factory = provider
    reply = response({"error": "private provider detail"}, status)
    session.reply = reply

    with pytest.raises(transport.AITransportError, match=reason) as error:
        generate()

    assert "private provider detail" not in str(error.value)
    reply.json.assert_not_called()
    reply.close.assert_called_once()
    session.__exit__.assert_called_once()


@pytest.mark.parametrize(
    "failure,reason",
    [
        (requests.exceptions.ConnectTimeout("provider-secret"), "timed out"),
        (requests.exceptions.ReadTimeout("provider-secret"), "timed out"),
        (requests.exceptions.ConnectionError(ReadTimeoutError(None, "/chat", "provider-secret")), "timed out"),
        (requests.exceptions.ConnectionError("provider-secret"), "temporarily unavailable"),
        (requests.exceptions.RequestException("provider-secret"), "temporarily unavailable"),
    ],
)
def test_network_failure_is_safe_and_cleans_up(provider, failure, reason):
    session, _factory = provider
    session.post.side_effect = failure
    with pytest.raises(transport.AITransportError, match=reason) as error:
        generate()
    assert "provider-secret" not in str(error.value)
    session.__exit__.assert_called_once()


def test_streaming_read_timeout_is_reported_as_timeout(provider):
    session, _factory = provider
    reply = response(None)
    reply.json.side_effect = requests.exceptions.ConnectionError(ReadTimeoutError(None, "/chat", "provider-secret"))
    session.reply = reply
    with pytest.raises(transport.AITransportError, match="timed out"):
        generate()
    reply.__exit__.assert_called_once()
    session.__exit__.assert_called_once()


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        {"choices": [None]},
        {"choices": [{"message": {"content": " "}}]},
    ],
)
def test_invalid_provider_responses_are_rejected(provider, payload):
    session, _factory = provider
    session.reply = response(payload)
    with pytest.raises(transport.AITransportError, match="invalid format"):
        generate()
    session.__exit__.assert_called_once()


def test_invalid_json_is_rejected(provider):
    session, _factory = provider
    session.reply = response(None)
    session.reply.json.side_effect = requests.exceptions.JSONDecodeError("invalid", "", 0)
    with pytest.raises(transport.AITransportError, match="invalid response"):
        generate()


def test_large_response_is_accepted(provider):
    session, _factory = provider
    content = "x" * 100_001
    session.reply = response({"choices": [{"message": {"content": content}}]})
    assert generate() == content


@pytest.mark.parametrize("extra", [0, 1])
def test_input_limit_counts_message_content_not_request_envelope(provider, extra):
    session, factory = provider
    session.reply = response({"choices": [{"message": {"content": "opinion"}}]})
    prompt = '"' * (transport.MAX_INPUT_BYTES - len(b"{}") + extra)
    if extra:
        with pytest.raises(transport.AITransportError, match="input exceeded the size limit"):
            generate(prompt=prompt, alert={}, model="model-name-does-not-count")
        factory.assert_not_called()
    else:
        assert generate(prompt=prompt, alert={}, model="model-name-does-not-count") == "opinion"
        assert len(json.dumps(session.post.call_args.kwargs["json"]).encode()) > transport.MAX_INPUT_BYTES


def test_input_limit_counts_unicode_utf8_bytes(provider):
    session, factory = provider
    session.reply = response({"choices": [{"message": {"content": "opinion"}}]})
    assert generate(prompt="😀" * 49_999 + "xx", alert={}) == "opinion"
    factory.reset_mock()
    with pytest.raises(transport.AITransportError, match="input exceeded the size limit"):
        generate(prompt="😀" * 49_999 + "xxx", alert={})
    factory.assert_not_called()


def test_alert_json_content_counts_towards_input_limit(provider):
    session, _factory = provider
    session.reply = response({"choices": [{"message": {"content": "opinion"}}]})
    alert = {"event": "😀" * 20_000}
    assert generate(alert=alert) == "opinion"
    assert json.loads(session.post.call_args.kwargs["json"]["messages"][1]["content"]) == alert
    with pytest.raises(transport.AITransportError, match="input exceeded the size limit"):
        generate(prompt="", alert={"event": "😀" * 50_000})


def test_missing_endpoint_never_contacts_provider(provider):
    _session, factory = provider
    config = AITriage(enabled=False, endpoint=None, model="qa-model")
    with pytest.raises(transport.AITransportError, match="not configured"):
        transport.generate(config, "qa-access-token", "prompt", {})
    factory.assert_not_called()


def test_enabled_config_requires_endpoint(provider):
    _session, factory = provider
    with pytest.raises(ValidationError, match="AI triage endpoint is required when enabled"):
        AITriage(enabled=True, endpoint=None, model="qa-model")
    factory.assert_not_called()
