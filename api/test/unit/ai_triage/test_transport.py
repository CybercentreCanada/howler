import json
import ssl
import time
from unittest.mock import MagicMock, Mock

import pytest

from howler.odm.models.config import AITriage
from howler.services import ai_transport as transport


@pytest.fixture
def provider(monkeypatch):
    pool = MagicMock()
    factory = Mock(return_value=pool)
    monkeypatch.setattr(transport.urllib3, "PoolManager", factory)
    return pool, factory


def response(body, status=200):
    result = MagicMock(status=status)
    result.stream.return_value = [body]
    result.__enter__.return_value = result
    return result


def generate(
    *,
    prompt="Conservative system prompt",
    alert=None,
    deadline=None,
    model="qa-model",
    endpoint="https://ai.invalid/chat",
):
    return transport.generate(
        AITriage(enabled=True, endpoint=endpoint, model=model, headers={"X-Provider-Key": "private-key"}),
        "qa-access-token",
        prompt,
        {"event": "alert"} if alert is None else alert,
        deadline=time.monotonic() + 30 if deadline is None else deadline,
    )


def test_repeated_success_preserves_request_security_and_cleans_up(provider, monkeypatch):
    pool, factory = provider
    monkeypatch.setenv("HTTPS_PROXY", "https://proxy.invalid")
    monkeypatch.setenv("NETRC", "/nonexistent/private-credentials")
    replies = [response(b'{"choices":[{"message":{"content":"  Conservative opinion  "}}]}') for _ in range(2)]
    pool.request.side_effect = replies

    for _ in range(2):
        assert generate() == "Conservative opinion"

    args, kwargs = pool.request.call_args
    assert args == ("POST", "https://ai.invalid/chat")
    assert kwargs["headers"] == {
        "X-Provider-Key": "private-key",
        "Authorization": "Bearer qa-access-token",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    assert json.loads(kwargs["body"]) == {
        "model": "qa-model",
        "messages": [
            {"role": "system", "content": "Conservative system prompt"},
            {"role": "user", "content": '{"event":"alert"}'},
        ],
        "stream": False,
    }
    assert kwargs["redirect"] is False and kwargs["retries"] is False
    assert kwargs["preload_content"] is False
    assert factory.call_args.kwargs["ssl_context"].verify_mode == ssl.CERT_REQUIRED
    assert type(factory.call_args.kwargs["ssl_context"]) is transport.ssl.SSLContext
    assert pool.clear.call_count == 2
    for reply in replies:
        reply.__exit__.assert_called_once()


@pytest.mark.parametrize(
    "status,reason", [(401, "authorization token"), (403, "authorization token"), (503, "HTTP 503"), (302, "HTTP 302")]
)
def test_http_errors_do_not_read_or_expose_provider_details(provider, status, reason):
    pool, _factory = provider
    reply = response(b'{"error":"private provider detail"}', status)
    pool.request.return_value = reply

    with pytest.raises(transport.AITransportError, match=reason) as error:
        generate()

    assert "private provider detail" not in str(error.value)
    reply.stream.assert_not_called()
    reply.__exit__.assert_called_once()
    pool.clear.assert_called_once()


def test_network_failure_is_safe_and_cleans_up(provider):
    pool, _factory = provider
    pool.request.side_effect = transport.urllib3.exceptions.ReadTimeoutError(None, "/chat", "provider-secret")
    with pytest.raises(transport.AITransportError, match="temporarily unavailable") as error:
        generate()
    assert "provider-secret" not in str(error.value)
    pool.clear.assert_called_once()


@pytest.mark.parametrize(
    "body,reason",
    [
        (b"not-json", "invalid response"),
        (b"\xff", "invalid response"),
        (b"[]", "invalid response"),
        (b"{}", "no text"),
        (b'{"choices":[null]}', "no text"),
        (b'{"choices":[{"message":{"content":" "}}]}', "no text"),
    ],
)
def test_invalid_provider_responses_are_rejected(provider, body, reason):
    pool, _factory = provider
    pool.request.return_value = response(body)
    with pytest.raises(transport.AITransportError, match=reason):
        generate()
    pool.clear.assert_called_once()


@pytest.mark.parametrize("extra", [0, 1])
def test_response_byte_limit(provider, extra):
    pool, _factory = provider
    body = b'{"choices":[{"message":{"content":"opinion"}}]}'
    pool.request.return_value = response(body + b" " * (transport.MAX_OUTPUT_BYTES - len(body) + extra))
    if extra:
        with pytest.raises(transport.AITransportError, match="response exceeded the size limit"):
            generate()
    else:
        assert generate() == "opinion"
    pool.clear.assert_called_once()


@pytest.mark.parametrize("extra", [0, 1])
def test_input_limit_counts_the_complete_transmitted_body(provider, extra):
    pool, factory = provider
    frame = (
        b'{"model":"qa-model","messages":['
        b'{"role":"system","content":""},'
        b'{"role":"user","content":"{}"}],"stream":false}'
    )
    pool.request.return_value = response(b'{"choices":[{"message":{"content":"opinion"}}]}')
    prompt = "x" * (transport.MAX_INPUT_BYTES - len(frame) + extra)
    if extra:
        with pytest.raises(transport.AITransportError, match="input exceeded the size limit"):
            generate(prompt=prompt, alert={})
        factory.assert_not_called()
    else:
        assert generate(prompt=prompt, alert={}) == "opinion"
        assert len(pool.request.call_args.kwargs["body"]) == transport.MAX_INPUT_BYTES


def test_unicode_is_sent_as_bounded_utf8_not_reencoded_ascii(provider):
    pool, _factory = provider
    pool.request.return_value = response(b'{"choices":[{"message":{"content":"opinion"}}]}')
    alert = {"event": "😀" * 20_000}
    assert generate(alert=alert) == "opinion"
    body = pool.request.call_args.kwargs["body"]
    assert isinstance(body, bytes) and len(body) < transport.MAX_INPUT_BYTES
    assert json.loads(json.loads(body)["messages"][1]["content"]) == alert


@pytest.mark.parametrize(
    "kwargs,reason",
    [
        ({"prompt": '"' * 100_000}, "input exceeded the size limit"),
        ({"model": "x" * 200_000}, "input exceeded the size limit"),
        ({"deadline": 0}, "exceeded its timeout"),
        ({"endpoint": None}, "not configured"),
    ],
)
def test_rejected_input_or_expired_deadline_never_contacts_provider(provider, kwargs, reason):
    _pool, factory = provider
    with pytest.raises(transport.AITransportError, match=reason):
        generate(**kwargs)
    factory.assert_not_called()
