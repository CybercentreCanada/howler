import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from howler import actions
from howler.actions import ai_triage
from howler.odm.models.config import AITriage, config
from howler.services import ai_triage_service as service

from .support import make_hit, make_lead, make_user


@pytest.fixture
def settings(monkeypatch):
    ai = AITriage(enabled=True, endpoint="https://ai.invalid/chat", model="qa-model")
    monkeypatch.setattr(config.core, "ai", ai)
    monkeypatch.setattr(config.system, "encryption_key", "0123456789abcdef0123456789abcdef")
    return ai


def test_availability_and_operation_spec_are_local(settings):
    settings.headers = {"X-Provider-Key": "server-secret"}

    assert service.is_available()
    spec = next(item for item in actions.specifications() if item["id"] == "ai_triage")
    assert spec["requires_auth_token"] is True
    assert spec["steps"][0]["optional_args"] == ["prompt"]
    assert "server-secret" not in json.dumps(spec)
    assert "ai.invalid" not in json.dumps(spec)


def test_missing_encryption_key_disables_feature(settings, monkeypatch):
    monkeypatch.setattr(config.system, "encryption_key", None)
    assert not service.is_available()


def test_provider_input_excludes_analyst_content_and_prompt_is_additive(settings):
    hit = make_hit(dossier=[make_lead("private opinion")])
    hit.howler.log = [{"timestamp": "NOW", "explanation": "private log", "user": "analyst"}]
    original = hit.as_primitives()

    data = service.provider_input(hit)
    prompt = service.build_system_prompt("Prefer concise output")

    assert prompt.startswith(settings.system_prompt)
    assert "Prefer concise output" in prompt
    assert "Summary" in prompt and "Next steps" in prompt
    assert "dossier" not in data["howler"] and "log" not in data["howler"]
    assert data["event"]["original"] == "current telemetry"
    assert "private opinion" not in json.dumps(data)
    assert hit.as_primitives() == original


def test_action_report_is_ordinary_and_keeps_optional_prompt(settings, monkeypatch):
    user = make_user()
    enqueue = Mock(return_value=2)
    monkeypatch.setattr(service, "enqueue_alerts", enqueue)

    result = ai_triage.execute(
        "*:*", user, trusted_auth_token="qa-token", prompt="Be concise", request_id="request-1", trigger="create"
    )

    assert result == [
        {
            "query": "*:*",
            "outcome": "success",
            "title": "AI triage queued",
            "message": "AI triage was queued for 2 alert(s).",
        }
    ]
    enqueue.assert_called_once_with("*:*", user, "qa-token", prompt="Be concise")


def test_enqueue_creates_one_minimal_reference_per_hit(settings, monkeypatch):
    first = SimpleNamespace(howler=SimpleNamespace(id="hit-1"))
    second = SimpleNamespace(howler=SimpleNamespace(id="hit-2"))
    queue = Mock()
    monkeypatch.setattr(service, "_eligible_targets", Mock(return_value=[first, second]))
    monkeypatch.setattr(service, "get_queue", lambda: queue)
    monkeypatch.setattr(service.auth_service, "encrypt_token", lambda _token: "ciphertext")

    count = service.enqueue_alerts("*:*", make_user(), "trusted-token", prompt="Be concise")

    assert count == 2
    queue.push.assert_called_once_with(
        {"hit_id": "hit-1", "uname": "analyst", "bearer_token": "ciphertext", "prompt": "Be concise"},
        {"hit_id": "hit-2", "uname": "analyst", "bearer_token": "ciphertext", "prompt": "Be concise"},
    )
    assert "event" not in repr(queue.push.call_args)
    assert "trusted-token" not in repr(queue.push.call_args)


def test_enqueue_failure_returns_safe_error_without_provider_fallback(settings, monkeypatch, caplog):
    enqueue = Mock(side_effect=RuntimeError("redis-password-secret"))
    generate = Mock()
    monkeypatch.setattr(service, "enqueue_alerts", enqueue)
    monkeypatch.setattr("howler.services.ai_transport.generate", generate)

    result = ai_triage.execute("*:*", make_user(), trusted_auth_token="qa-token")

    assert result[0]["outcome"] == "error"
    assert "redis-password-secret" not in repr(result) + caplog.text
    generate.assert_not_called()


def test_save_replaces_only_managed_lead_and_preserves_unrelated_data(settings, monkeypatch):
    hit = make_hit(
        dossier=[
            make_lead("Analyst's note"),
            make_lead("old generated note", service.LEAD_OWNER),
            make_lead("Another integration note", "another.plugin"),
        ]
    )
    storage = Mock()
    storage.hit.save = Mock()
    storage.hit.get_if_exists.return_value = ({"howler": {"id": hit.howler.id}}, "1")
    monkeypatch.setattr(service, "datastore", lambda: storage)
    monkeypatch.setattr(service, "load_current_user", lambda _uname: make_user())
    monkeypatch.setattr(service, "load_current_hit", lambda *_args: (hit, "save-v2"))
    monkeypatch.setattr(service.comms_service, "emit", Mock())

    assert service.save_ai_lead(hit.howler.id, make_user(), "new generated note", "generation-v1")

    saved = storage.hit.save.call_args.args[1].as_primitives()
    assert storage.hit.save.call_args.kwargs["version"] == "save-v2"
    assert [lead["content"] for lead in saved["howler"]["dossier"]] == [
        "Analyst's note",
        "Another integration note",
        "new generated note",
    ]
    metadata = json.loads(saved["howler"]["dossier"][-1]["metadata"])
    assert metadata["owner"] == service.LEAD_OWNER
    assert metadata["source_version"] == "generation-v1"
    assert "run_id" not in metadata
