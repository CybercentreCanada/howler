import json
from unittest.mock import Mock, call

import pytest
from pydantic import ValidationError

from howler import actions
from howler.actions import ai_triage
from howler.config import CLASSIFICATION
from howler.datastore.exceptions import VersionConflictException
from howler.odm.models.config import AITriage, config
from howler.services import ai_service as service
from howler.utils.dict_utils import remove_path

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
    assert spec["roles"] == ai_triage.ROLES
    assert spec["requires_auth_token"] is True
    assert spec["steps"][0]["optional_args"] == ["prompt"]
    assert "server-secret" not in json.dumps(spec)
    assert "ai.invalid" not in json.dumps(spec)


def test_unavailable_ai_operation_is_not_advertised(settings, monkeypatch):
    monkeypatch.setattr(config.core, "ai", AITriage())
    assert not service.is_available()
    assert all(item["id"] != "ai_triage" for item in actions.specifications())


def test_config_accepts_local_openai_endpoint_and_rejects_reserved_headers():
    local = AITriage(enabled=True, endpoint="http://localhost:8080/chat", model="model", max_concurrent_jobs=6)
    assert local.locally_valid()

    invalid = AITriage(
        enabled=True,
        endpoint="https://ai.invalid/chat",
        model="model",
        headers={"aUtHoRiZaTiOn": "override"},
    )
    assert not invalid.locally_valid()
    assert not AITriage(enabled=True, endpoint="http://ai.invalid/chat", model="model").locally_valid()
    assert not AITriage(enabled=True, endpoint="https://user@ai.invalid/chat", model="model").locally_valid()


def test_config_concurrency_has_no_artificial_upper_limit():
    assert AITriage(max_concurrent_jobs=20).max_concurrent_jobs == 20
    with pytest.raises(ValidationError):
        AITriage(max_concurrent_jobs=0)


def test_missing_encryption_key_disables_feature(settings, monkeypatch):
    monkeypatch.setattr(config.system, "encryption_key", None)
    assert not service.is_available()


def test_action_allows_user_without_access_control_when_classification_is_disabled(settings, monkeypatch):
    monkeypatch.setattr(CLASSIFICATION, "enforce", False)
    enqueue = Mock(return_value=1)
    monkeypatch.setattr(service, "enqueue_alerts", enqueue)
    user = make_user()
    user.access_control = None

    result = ai_triage.execute("event.kind:alert", user, auth_token="qa-token")

    assert result[0]["outcome"] == "success"
    enqueue.assert_called_once()


def test_action_requires_access_control_when_classification_is_enabled(settings, monkeypatch):
    monkeypatch.setattr(CLASSIFICATION, "enforce", True)
    enqueue = Mock()
    monkeypatch.setattr(service, "enqueue_alerts", enqueue)
    user = make_user()
    user.access_control = None

    result = ai_triage.execute("event.kind:alert", user, auth_token="qa-token")

    assert result[0]["outcome"] == "error"
    assert result[0]["title"] == "No user specified"
    enqueue.assert_not_called()


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


def test_provider_input_redacts_comment_values_in_all_list_items_without_mutating_hit(settings):
    settings.excluded_input_fields = ["howler.comment.value"]
    hit = make_hit(
        comment=[
            {"id": "00000000-0000-4000-8000-000000000001", "user": "analyst-1", "value": "private first"},
            {"id": "00000000-0000-4000-8000-000000000002", "user": "analyst-2", "value": "private second"},
        ]
    )
    original = hit.as_primitives()

    data = service.provider_input(hit)

    assert [comment.get("value") for comment in data["howler"]["comment"]] == [None, None]
    assert [comment["user"] for comment in data["howler"]["comment"]] == ["analyst-1", "analyst-2"]
    assert data["event"]["original"] == "current telemetry"
    assert "private first" not in json.dumps(data)
    assert "private second" not in json.dumps(data)
    assert hit.as_primitives() == original


def test_remove_path_recurses_nested_lists_without_consuming_path():
    data = {
        "howler": {
            "comment": [
                [[{"value": "private nested", "user": "analyst"}, {"value": "private sibling", "keep": True}]],
                [{"value": "private second item", "other": "preserved"}],
            ],
            "unrelated": "preserved",
        }
    }

    remove_path(data, "howler.comment.value")

    assert data == {
        "howler": {
            "comment": [
                [[{"user": "analyst"}, {"keep": True}]],
                [{"other": "preserved"}],
            ],
            "unrelated": "preserved",
        }
    }


@pytest.mark.parametrize(
    ("roles", "max_hits"),
    [(["user", "actionrunner_basic"], 10), (["user", "actionrunner_advanced"], 50), (["admin"], 50)],
)
def test_action_selects_role_limit_without_http_call(settings, monkeypatch, roles, max_hits):
    user = make_user()
    user.type = roles
    enqueue = Mock(return_value=2)
    monkeypatch.setattr(service, "enqueue_alerts", enqueue)
    generate = Mock()
    monkeypatch.setattr(service, "generate", generate)

    result = ai_triage.execute("event.kind:alert", user, auth_token="qa-token", prompt="Be concise")

    assert result[0]["outcome"] == "success"
    enqueue.assert_called_once_with("event.kind:alert", user, "qa-token", prompt="Be concise", max_hits=max_hits)
    generate.assert_not_called()


@pytest.mark.parametrize(
    ("count", "outcome", "title"),
    [(0, "skipped", "No matching alerts"), (None, "error", "Hit limit exceeded")],
)
def test_action_reports_empty_or_overflow_selection(settings, monkeypatch, count, outcome, title):
    enqueue = Mock(return_value=count)
    monkeypatch.setattr(service, "enqueue_alerts", enqueue)

    result = ai_triage.execute("*:*", make_user(), auth_token="qa-token")

    assert result[0]["outcome"] == outcome
    assert result[0]["title"] == title
    enqueue.assert_called_once()
    if count is None:
        assert "narrow the query" in result[0]["message"]


def test_enqueue_creates_minimal_jobs_and_normalizes_prompt(settings, monkeypatch):
    queue = Mock()
    monkeypatch.setattr(service, "_eligible_targets", Mock(return_value=["hit-1", "hit-2"]))
    monkeypatch.setattr(service, "get_queue", lambda: queue)
    monkeypatch.setattr(service.auth_service, "encrypt_token", lambda _token: "ciphertext")

    count = service.enqueue_alerts("*:*", make_user(), "trusted-token", prompt="  Be concise  ", max_hits=10)

    assert count == 2
    queue.push.assert_called_once_with(
        {"hit_id": "hit-1", "uname": "analyst", "bearer_token": "ciphertext", "prompt": "Be concise"},
        {"hit_id": "hit-2", "uname": "analyst", "bearer_token": "ciphertext", "prompt": "Be concise"},
    )
    assert "event" not in repr(queue.push.call_args)
    assert "trusted-token" not in repr(queue.push.call_args)


@pytest.mark.parametrize(("targets", "expected"), [([], 0), (None, None)], ids=["empty", "overflow"])
def test_enqueue_does_not_push_empty_or_overflow_selection(settings, monkeypatch, targets, expected):
    queue = Mock()
    encrypt = Mock(return_value="ciphertext")
    monkeypatch.setattr(service, "_eligible_targets", lambda *_args: targets)
    monkeypatch.setattr(service, "get_queue", lambda: queue)
    monkeypatch.setattr(service.auth_service, "encrypt_token", encrypt)

    assert service.enqueue_alerts("*:*", make_user(), "token", max_hits=10) == expected

    queue.push.assert_not_called()
    encrypt.assert_not_called()


@pytest.mark.parametrize("prompt", [None, "  ", 42])
def test_enqueue_ignores_blank_or_non_string_prompt(settings, monkeypatch, prompt):
    queue = Mock()
    monkeypatch.setattr(service, "_eligible_targets", lambda *_args: ["hit-1"])
    monkeypatch.setattr(service, "get_queue", lambda: queue)
    monkeypatch.setattr(service.auth_service, "encrypt_token", lambda _token: "ciphertext")

    service.enqueue_alerts("*:*", make_user(), "token", prompt=prompt, max_hits=10)

    assert queue.push.call_args.args[0]["prompt"] is None


@pytest.mark.parametrize(("max_hits", "count"), [(10, 10), (10, 11), (50, 50), (50, 51)])
def test_selection_fetches_only_ids_and_rejects_overflow_at_bounded_limit(settings, monkeypatch, max_hits, count):
    user = make_user()
    user.access_control = "howler.classification:TLP:U"
    hits = [make_hit(id=f"hit-{index}") for index in range(count)]
    storage = Mock()
    storage.hit.search.return_value = {"items": hits}
    monkeypatch.setattr(service, "datastore", lambda: storage)

    targets = service._eligible_targets("event.kind:alert", user, max_hits=max_hits)

    storage.hit.search.assert_called_once_with(
        "(event.kind:alert) AND NOT howler.status:resolved AND NOT howler.assessment:*",
        as_obj=True,
        rows=max_hits + 1,
        fl="howler.id",
        access_control=user.access_control,
    )
    if count > max_hits:
        assert targets is None
    else:
        assert targets == [f"hit-{index}" for index in range(count)]


def test_enqueue_failure_returns_safe_error_without_provider_fallback(settings, monkeypatch, caplog):
    enqueue = Mock(side_effect=RuntimeError("redis-password-secret"))
    generate = Mock()
    monkeypatch.setattr(service, "enqueue_alerts", enqueue)
    monkeypatch.setattr(service, "generate", generate)

    result = ai_triage.execute("*:*", make_user(), auth_token="qa-token")

    assert result[0]["outcome"] == "error"
    assert "redis-password-secret" not in repr(result) + caplog.text
    generate.assert_not_called()


def test_save_replaces_only_managed_lead_and_preserves_concurrent_edit(settings, monkeypatch):
    first_hit = make_hit(
        dossier=[
            make_lead("Analyst's note"),
            make_lead("old generated note", service.LEAD_OWNER),
            make_lead("Another integration note", "another.plugin"),
        ]
    )
    second_hit = make_hit(
        dossier=[
            make_lead("Concurrent analyst edit"),
            make_lead("old generated note", service.LEAD_OWNER),
            make_lead("Another integration note", "another.plugin"),
        ]
    )
    user = make_user()
    get_hit = Mock(side_effect=[(first_hit, "version-1"), (second_hit, "version-2")])
    save_hit = Mock(side_effect=[VersionConflictException("race"), (second_hit, "version-3")])
    monkeypatch.setattr(service.hit_service, "get_hit", get_hit)
    monkeypatch.setattr(service.hit_service, "save_hit", save_hit)
    assert service.save_ai_lead("hit-1", user, "new generated note")

    assert get_hit.call_args_list == [
        call("hit-1", as_odm=True, version=True, user=user),
        call("hit-1", as_odm=True, version=True, user=user),
    ]
    assert save_hit.call_args_list[0].kwargs["version"] == "version-1"
    assert save_hit.call_args_list[1].kwargs["version"] == "version-2"
    saved = save_hit.call_args.args[0]
    assert [lead.content for lead in saved.howler.dossier] == [
        "Concurrent analyst edit",
        "Another integration note",
        "new generated note",
    ]
    assert json.loads(saved.howler.dossier[-1].metadata) == {"owner": service.LEAD_OWNER}


@pytest.mark.parametrize(("status", "assessment"), [("resolved", None), ("open", "legitimate")])
def test_save_skips_alert_that_became_ineligible(settings, monkeypatch, status, assessment):
    hit = make_hit(status=status, assessment=assessment)
    get_hit = Mock(return_value=(hit, "version"))
    save_hit = Mock()
    monkeypatch.setattr(service.hit_service, "get_hit", get_hit)
    monkeypatch.setattr(service.hit_service, "save_hit", save_hit)

    assert not service.save_ai_lead("hit-1", make_user(), "generated note")

    get_hit.assert_called_once()
    save_hit.assert_not_called()


def test_save_stops_after_cas_retries_are_exhausted(settings, monkeypatch):
    hit = make_hit()
    get_hit = Mock(return_value=(hit, "version"))
    save_hit = Mock(side_effect=[VersionConflictException("race") for _ in range(service.CAS_RETRIES)])
    monkeypatch.setattr(service.hit_service, "get_hit", get_hit)
    monkeypatch.setattr(service.hit_service, "save_hit", save_hit)

    assert not service.save_ai_lead("hit-1", make_user(), "generated note")

    assert get_hit.call_count == service.CAS_RETRIES
    assert save_hit.call_count == service.CAS_RETRIES


@pytest.mark.parametrize("metadata", ["not-json", "[]", "null", "42"])
def test_lead_owner_handles_malformed_or_non_object_metadata(settings, metadata):
    lead = make_hit(dossier=[make_lead("bad metadata")]).howler.dossier[0]
    lead.metadata = metadata
    assert service._lead_owner(lead) is None
