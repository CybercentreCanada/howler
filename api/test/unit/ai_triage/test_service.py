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


@pytest.mark.parametrize(
    "change",
    [{"enabled": False}, {"endpoint": None}, {"model": None}, {"endpoint": "http://external.invalid"}],
)
def test_disabled_or_unconfigured_is_hidden_and_cannot_dispatch(settings, change, monkeypatch):
    for key, value in change.items():
        setattr(settings, key, value)
    enqueue = Mock()
    monkeypatch.setattr(service, "enqueue_action", enqueue)
    assert "ai_triage" not in {spec["id"] for spec in actions.specifications()}
    report = actions.execute("ai_triage", "*:*", make_user(), trusted_auth_token="qa-token")
    assert all(item["outcome"] == "error" for item in report)
    enqueue.assert_not_called()


def test_availability_is_local_and_spec_contains_no_provider_secrets(settings):
    settings.headers = {"X-Provider-Key": "server-secret"}
    spec = next(item for item in actions.specifications() if item["id"] == "ai_triage")
    assert service.is_available()
    assert spec["requires_auth_token"] is True
    assert spec["steps"][0]["optional_args"] == ["prompt"]
    assert "server-secret" not in json.dumps(spec)
    assert "ai.invalid" not in json.dumps(spec)


def test_missing_encryption_key_hides_feature(settings, monkeypatch):
    monkeypatch.setattr(config.system, "encryption_key", None)
    assert not service.is_available()


def test_prompt_is_conservative_additive_and_independent_of_alert_json(settings):
    hit = make_hit(dossier=[make_lead("private opinion")])
    hit.howler.log = [{"timestamp": "NOW", "explanation": "private log", "user": "analyst"}]
    original = deepcopy(hit.as_primitives())
    data = service.provider_input(hit)
    prompt = service.build_system_prompt("Prefer concise output")
    for heading in ("Summary", "Recommended assessment", "Reasoning", "Confidence", "Next steps"):
        assert heading in prompt
    assert "no recommendation" in prompt.lower()
    assert "strong" in prompt.lower()
    assert prompt.startswith(settings.system_prompt)
    assert "Prefer concise output" in prompt
    assert "dossier" not in data["howler"]
    assert "log" not in data["howler"]
    assert data["event"]["original"] == "current telemetry"
    assert "private opinion" not in json.dumps(data)
    assert hit.as_primitives() == original


def test_server_prompt_override_and_nested_exclusions(settings):
    settings.system_prompt = "Server safety policy"
    settings.excluded_input_fields += ["event.original", "does.not.exist"]
    assert service.build_system_prompt(None) == "Server safety policy"
    assert "original" not in service.provider_input(make_hit())["event"]


def test_failed_durable_enqueue_does_not_fall_back_to_provider(settings, monkeypatch, caplog):
    enqueue = Mock(side_effect=RuntimeError("redis-password-secret"))
    generate = Mock()
    monkeypatch.setattr(service, "enqueue_action", enqueue)
    monkeypatch.setattr("howler.services.ai_transport.generate", generate)
    result = ai_triage.execute("*:*", make_user(), trusted_auth_token="qa-token")
    assert result[0]["outcome"] == "error"
    assert "redis-password-secret" not in repr(result) + caplog.text
    generate.assert_not_called()


def test_lead_ownership_not_label_controls_replacement_and_version_zero(settings, monkeypatch):
    analyst = make_lead("Analyst's identically labelled note")
    other_plugin = make_lead("Other integration note", "another.plugin")
    hit = make_hit(dossier=[analyst, make_lead("old", service.LEAD_OWNER), other_plugin])
    before = hit.as_primitives()
    save = Mock()
    storage = Mock()
    storage.hit.save = save
    storage.hit.get_if_exists.return_value = (None, "0")
    monkeypatch.setattr(service, "datastore", lambda: storage)
    monkeypatch.setattr(service, "get_current_hit", lambda *_: (hit, "0"))
    candidate = service.prepare_candidate("new", "run-qa", "0")
    assert service.save_ai_lead(hit.howler.id, make_user(), candidate) == (True, None)
    saved = save.call_args.args[1].as_primitives()
    assert save.call_args.kwargs["version"] == "0"
    assert [lead["content"] for lead in saved["howler"]["dossier"]] == [
        "Analyst's identically labelled note",
        "Other integration note",
        "new",
    ]
    metadata = json.loads(saved["howler"]["dossier"][-1]["metadata"])
    assert metadata["owner"] == service.LEAD_OWNER
    assert metadata["source_version"] == "0"
    assert metadata["run_id"] == "run-qa" and metadata["schema_version"] == 1
    saved["howler"].pop("dossier")
    before["howler"].pop("dossier")
    assert saved == before


def test_async_report_sanitizer_does_not_collapse_distinct_runs():
    sanitize = actions.__dict__["__sanitize_report"]
    entries = [
        {
            "query": "*:*",
            "title": "Queued",
            "message": "Queued",
            "outcome": "success",
            "run_id": run_id,
            "status": "queued",
        }
        for run_id in ("run-a", "run-b")
    ]
    reports = sanitize(entries)
    assert {entry["run_id"] for entry in reports} == {"run-a", "run-b"}
    assert all(entry["status"] == "queued" for entry in reports)


@pytest.mark.parametrize("mutation", ["digest", "generated_at", "source_version", "provider", "label", "format"])
def test_candidate_confirmation_rejects_same_owner_run_and_content_with_tampered_identity(settings, mutation):
    candidate = service.prepare_candidate("identical text", "identical-run", "identical-version")
    changed = {key: deepcopy(candidate[key]) for key in ("content", "label", "format", "metadata")}
    metadata = json.loads(changed["metadata"])
    if mutation == "label":
        changed["label"]["fr"] = "Different label"
    elif mutation == "format":
        changed["format"] = "text"
    elif mutation == "digest":
        metadata["candidate_sha256"] = "0" * 64
    else:
        metadata[mutation] = "different-provenance"
    changed["metadata"] = json.dumps(metadata)
    assert metadata["owner"] == service.LEAD_OWNER and metadata["run_id"] == "identical-run"
    assert changed["content"] == candidate["content"]
    assert not service.has_managed_candidate(make_hit(dossier=[changed]), candidate)
