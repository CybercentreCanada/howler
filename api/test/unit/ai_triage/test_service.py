import json
from copy import deepcopy
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
    original = deepcopy(hit.as_primitives())

    data = service.provider_input(hit)
    prompt = service.build_system_prompt("Prefer concise output")

    assert prompt.startswith(settings.system_prompt)
    assert "Prefer concise output" in prompt
    assert "Summary" in prompt and "Next steps" in prompt
    assert "dossier" not in data["howler"] and "log" not in data["howler"]
    assert data["event"]["original"] == "current telemetry"
    assert "private opinion" not in json.dumps(data)
    assert hit.as_primitives() == original


def test_action_success_enqueues_with_trusted_token(settings, monkeypatch):
    user = make_user()
    enqueue = Mock(return_value={"run_id": "run-1", "counts": {"total": 1}})
    monkeypatch.setattr(service, "enqueue_run", enqueue)

    result = ai_triage.execute("*:*", user, trusted_auth_token="qa-token", prompt="Be concise", request_id="request-1")

    assert result[0]["outcome"] == "success"
    assert result[0]["run_id"] == "run-1"
    enqueue.assert_called_once_with(
        "*:*",
        user,
        request_id="request-1",
        action_id=None,
        trigger=None,
        bearer_token="qa-token",
        prompt="Be concise",
    )


def test_enqueue_failure_returns_safe_error_without_provider_fallback(settings, monkeypatch, caplog):
    enqueue = Mock(side_effect=RuntimeError("redis-password-secret"))
    generate = Mock()
    monkeypatch.setattr(service, "enqueue_run", enqueue)
    monkeypatch.setattr("howler.services.ai_transport.generate", generate)

    result = ai_triage.execute("*:*", make_user(), trusted_auth_token="qa-token")

    assert result[0]["outcome"] == "error"
    assert "redis-password-secret" not in repr(result) + caplog.text
    generate.assert_not_called()


def test_save_replaces_only_managed_lead_and_preserves_version_zero(settings, monkeypatch):
    hit = make_hit(
        dossier=[
            make_lead("Analyst's note"),
            make_lead("old generated note", service.LEAD_OWNER),
            make_lead("Another integration note", "another.plugin"),
        ]
    )
    original = hit.as_primitives()
    storage = Mock()
    storage.hit.save = Mock()
    monkeypatch.setattr(service, "datastore", lambda: storage)
    monkeypatch.setattr(service, "get_current_hit", lambda *_args: (hit, "0"))
    candidate = service.prepare_candidate("new generated note", "run-1", "0")

    assert service.save_ai_lead(hit.howler.id, make_user(), candidate) == (True, None)

    saved = storage.hit.save.call_args.args[1].as_primitives()
    assert storage.hit.save.call_args.kwargs["version"] == "0"
    assert [lead["content"] for lead in saved["howler"]["dossier"]] == [
        "Analyst's note",
        "Another integration note",
        "new generated note",
    ]
    metadata = json.loads(saved["howler"]["dossier"][-1]["metadata"])
    assert metadata["owner"] == service.LEAD_OWNER
    assert metadata["run_id"] == "run-1"
    original["howler"].pop("dossier")
    saved["howler"].pop("dossier")
    assert saved == original
