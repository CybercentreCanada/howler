import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from howler.config import config
from howler.odm.models.config import AIConfig
from howler.odm.models.hit import Hit
from howler.services import agent_service, ai_lucene_service, ai_service

query_warning = ai_lucene_service._query_warning


@pytest.fixture(autouse=True)
def valid_queries(monkeypatch):
    monkeypatch.setattr(ai_lucene_service, "_query_warning", lambda _query: None)


def test_field_context_lists_types_and_enum_values(monkeypatch):
    ai_lucene_service._field_context.cache_clear()
    monkeypatch.setattr(ai_lucene_service, "datastore", lambda: SimpleNamespace(hit=SimpleNamespace(model_class=Hit)))

    try:
        context = ai_lucene_service._field_context().splitlines()
    finally:
        ai_lucene_service._field_context.cache_clear()

    assert "howler.status: enum[in-progress|on-hold|open|resolved]" in context
    assert "howler.analytic: caseinsensitivekeyword" in context


def test_build_messages_includes_current_query_only_when_meaningful(monkeypatch):
    monkeypatch.setattr(ai_lucene_service, "_field_context", lambda: "howler.status: enum[open]")

    system, user = ai_lucene_service.build_messages(" open hits ", "howler.escalation:alert")

    assert system["content"].endswith("Searchable hit fields (name: type):\nhowler.status: enum[open]")
    assert user["content"] == "Request:\nopen hits\n\nCurrent query:\nhowler.escalation:alert"
    assert ai_lucene_service.build_messages("open hits", "*:*")[1]["content"] == "Request:\nopen hits"


def events(stream):
    parsed = []
    for frame in stream:
        event = "message"
        for line in frame.strip().splitlines():
            if line.startswith("event: "):
                event = line[7:]
            elif line.startswith("data: "):
                parsed.append((event, json.loads(line[6:])))
    return parsed


def test_stream_events_emits_text_status_then_cleaned_query():
    updates = iter(
        [
            ("status", "Looking up fields"),
            ("text", "Here it is: ```lucene\n"),
            ("text", "Here it is: ```lucene\na:b\n```"),
        ]
    )

    assert events(ai_lucene_service.stream_events(updates)) == [
        ("status", {"status": "Looking up fields"}),
        ("message", {"text": "Here it is: ```lucene\n"}),
        ("message", {"text": "Here it is: ```lucene\na:b\n```"}),
        ("done", {"query": "a:b"}),
    ]


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (ai_service.AITransportError("Provider response timed out"), "Provider response timed out"),
        (RuntimeError("secret-bearing failure"), "AI query generation failed."),
        (None, "AI provider returned an empty query."),
    ],
)
def test_stream_events_reports_safe_errors(error, reason):
    def updates():
        if error:
            raise error
        yield ("text", "  ")

    assert events(ai_lucene_service.stream_events(updates()))[-1] == ("error", {"error": reason})


def test_stream_events_warns_about_invalid_queries(monkeypatch):
    monkeypatch.setattr(ai_lucene_service, "_query_warning", lambda query: f"bad {query}")

    assert events(ai_lucene_service.stream_events(iter([("text", "a:(")])))[-1] == (
        "done",
        {"query": "a:(", "warning": "bad a:("},
    )


@pytest.mark.parametrize(
    ("result", "warning"),
    [
        ({"valid": True}, None),
        ({"valid": False}, "The generated query is not valid Lucene. Review it before searching."),
        (RuntimeError("cluster unavailable"), None),
    ],
)
def test_query_warning_validates_with_elasticsearch(monkeypatch, result, warning):
    validate = Mock(side_effect=result) if isinstance(result, Exception) else Mock(return_value=Mock(body=result))
    monkeypatch.setattr(ai_lucene_service, "IndicesClient", lambda _client: Mock(validate_query=validate))
    monkeypatch.setattr(
        ai_lucene_service, "datastore", lambda: SimpleNamespace(hit=SimpleNamespace(datastore=Mock(), index_name="hit"))
    )

    assert query_warning("howler.status:open") == warning
    validate.assert_called_once_with(q="howler.status:open", index="hit")


@pytest.mark.parametrize(
    ("lucene", "core_enabled", "scope", "available"),
    [
        ({"enabled": False}, True, None, False),
        ({"enabled": True}, False, None, False),
        ({"enabled": True}, True, None, True),
        ({"enabled": True, "provider": "agent"}, False, None, False),
        ({"enabled": True, "provider": "agent"}, False, "api://agent/.default", True),
    ],
)
def test_is_available_requires_a_usable_provider(monkeypatch, lucene, core_enabled, scope, available):
    if lucene.get("provider") == "agent":
        lucene = {
            **lucene,
            "agent": {"agent_url": "https://agent.invalid", "broker_url": "https://broker.invalid", "scope": scope},
        }
    settings = {"enabled": True, "endpoint": "https://ai.invalid", "model": "m"} if core_enabled else {}
    monkeypatch.setattr(config.core, "ai", AIConfig(**settings, lucene=lucene))
    monkeypatch.setattr(agent_service, "get_plugins", lambda: [])

    assert ai_lucene_service.is_available() is available


@pytest.fixture
def one_slot(monkeypatch):
    monkeypatch.setattr(ai_lucene_service, "_slots", None)
    monkeypatch.setattr(config.core, "ai", AIConfig(lucene={"enabled": True, "max_concurrent": 1}))
    monkeypatch.setattr(ai_lucene_service, "_openai_updates", lambda *_args: iter([("text", "a:b")]))
    monkeypatch.setattr(ai_lucene_service, "build_messages", lambda *_args: [])


@pytest.mark.usefixtures("one_slot")
def test_generation_slot_is_held_until_the_stream_is_closed():
    stream = ai_lucene_service.start_generation("open hits", None, "token")

    with pytest.raises(ai_lucene_service.GenerationBusyError):
        ai_lucene_service.start_generation("open hits", None, "token")

    # The WSGI server always closes the response, even when the client disconnects before reading it.
    stream.close()
    stream.close()

    assert list(ai_lucene_service.start_generation("open hits", None, "token"))[-1].startswith("event: done")


@pytest.mark.usefixtures("one_slot")
def test_generation_slot_is_released_when_preparation_fails(monkeypatch):
    monkeypatch.setattr(config.core.ai.lucene, "provider", "agent")
    monkeypatch.setattr(
        agent_service, "get_agent_token", Mock(side_effect=ai_service.AITransportError("Failed to obtain access."))
    )

    for _ in range(2):
        with pytest.raises(ai_service.AITransportError):
            ai_lucene_service.start_generation("open hits", None, "token")
