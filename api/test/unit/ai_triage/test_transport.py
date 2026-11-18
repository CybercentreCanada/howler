import json
from unittest.mock import MagicMock, Mock

import pytest
import requests
from urllib3.exceptions import ReadTimeoutError

from howler.odm.models.config import AITriage
from howler.services import ai_service as transport

OK = {"choices": [{"message": {"content": "opinion"}}]}


@pytest.fixture
def provider(monkeypatch):
    session = MagicMock()
    session.__enter__.return_value = session
    factory = Mock(return_value=session)
    monkeypatch.setattr(transport.requests, "Session", factory)
    session.post.side_effect = lambda _endpoint, **kwargs: kwargs["hooks"]["response"](session.reply)
    return session, factory


def reply(session, payload, status=200):
    session.reply = MagicMock(status_code=status)
    session.reply.json.return_value = payload
    session.reply.__enter__.return_value = session.reply
    return session.reply


def generate(*, prompt="Conservative system prompt", alert=None, token="qa-access-token", timeout=30, **settings):
    config = AITriage(
        enabled=True,
        endpoint="https://ai.invalid/chat",
        model="qa-model",
        headers={"X-Provider-Key": "private-key"},
        timeout_seconds=timeout,
        **settings,
    )
    return transport.generate(config, token, prompt, {"event": "alert"} if alert is None else alert)


def test_success_preserves_request_security_and_cleans_up(provider, monkeypatch):
    session, factory = provider
    monkeypatch.setenv("HTTPS_PROXY", "https://proxy.invalid")
    response = reply(session, {"choices": [{"message": {"content": "  Conservative opinion  "}}]})

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
    assert (kwargs["allow_redirects"], kwargs["stream"], kwargs["timeout"]) == (False, True, (10, 30))
    assert session.trust_env is False
    factory.assert_called_once_with()
    session.__exit__.assert_called_once()
    response.__exit__.assert_called_once()


@pytest.mark.parametrize(
    ("api_key", "token", "sent"),
    [("provider-secret", None, "provider-secret"), ("provider-secret", "incoming-token", "provider-secret")],
)
def test_provider_api_key_takes_precedence_over_incoming_token(provider, api_key, token, sent):
    session, _ = provider
    reply(session, OK)

    assert generate(api_key=api_key, token=token) == "opinion"

    assert session.post.call_args.kwargs["headers"]["Authorization"] == f"Bearer {sent}"
    assert "incoming-token" not in repr(session.post.call_args)


def test_connect_timeout_is_bounded_by_configured_timeout(provider):
    session, _ = provider
    reply(session, OK)

    generate(timeout=3)

    assert session.post.call_args.kwargs["timeout"] == (3, 3)


def test_unconfigured_provider_or_credential_never_contacts_provider(provider):
    _, factory = provider
    with pytest.raises(transport.AITransportError, match="provider credential"):
        generate(token=None)
    with pytest.raises(transport.AITransportError, match="not configured"):
        transport.generate(AITriage(model="m"), "token", "prompt", {})

    factory.assert_not_called()


@pytest.mark.parametrize(
    ("status", "reason"),
    [(401, "authorization token"), (403, "authorization token"), (503, "HTTP 503"), (302, "HTTP 302")],
)
def test_http_errors_do_not_read_or_expose_provider_details(provider, status, reason):
    session, _ = provider
    response = reply(session, {"error": "private provider detail"}, status)

    with pytest.raises(transport.AITransportError, match=reason) as error:
        generate()

    assert "private provider detail" not in str(error.value)
    response.json.assert_not_called()
    response.close.assert_called_once()
    session.__exit__.assert_called_once()


@pytest.mark.parametrize(
    ("failure", "reason"),
    [
        (requests.exceptions.ConnectTimeout("provider-secret"), "timed out"),
        (requests.exceptions.ReadTimeout("provider-secret"), "timed out"),
        (requests.exceptions.ConnectionError(ReadTimeoutError(None, "/chat", "provider-secret")), "timed out"),
        (requests.exceptions.ConnectionError("provider-secret"), "temporarily unavailable"),
        (requests.exceptions.RequestException("provider-secret"), "temporarily unavailable"),
        (requests.exceptions.JSONDecodeError("invalid", "", 0), "invalid response"),
    ],
)
@pytest.mark.parametrize("raised_by", ["post", "body"])
def test_network_failure_is_safe_and_cleans_up(provider, failure, reason, raised_by):
    session, _ = provider
    response = reply(session, None)
    if raised_by == "post":
        session.post.side_effect = failure
    else:
        response.json.side_effect = failure

    with pytest.raises(transport.AITransportError, match=reason) as error:
        generate()

    assert "provider-secret" not in str(error.value)
    session.__exit__.assert_called_once()


@pytest.mark.parametrize("payload", [[], {}, {"choices": [None]}, {"choices": [{"message": {"content": " "}}]}])
def test_invalid_provider_responses_are_rejected(provider, payload):
    session, _ = provider
    reply(session, payload)

    with pytest.raises(transport.AITransportError, match="invalid format"):
        generate()


def test_large_response_is_accepted(provider):
    session, _ = provider
    reply(session, {"choices": [{"message": {"content": "x" * 100_001}}]})

    assert len(generate()) == 100_001


@pytest.mark.parametrize(
    ("prompt", "alert", "limit", "allowed"),
    [
        ("x" * 10, {}, 12, True),
        ("x" * 11, {}, 12, False),
        ("😀" * 3, {}, 14, True),
        ("😀" * 3 + "x", {}, 14, False),
        ("", {"e": "😀" * 3}, 20, True),
        ("", {"e": "😀" * 4}, 20, False),
    ],
    ids=["ascii-at", "ascii-over", "utf8-at", "utf8-over", "alert-at", "alert-over"],
)
def test_input_limit_counts_utf8_bytes_of_prompt_and_alert_content(provider, prompt, alert, limit, allowed):
    session, factory = provider
    reply(session, OK)

    if allowed:
        assert generate(prompt=prompt, alert=alert, max_input_bytes=limit) == "opinion"
        assert json.loads(session.post.call_args.kwargs["json"]["messages"][1]["content"]) == alert
    else:
        with pytest.raises(transport.AITransportError, match="input exceeded the size limit"):
            generate(prompt=prompt, alert=alert, max_input_bytes=limit)
        factory.assert_not_called()
