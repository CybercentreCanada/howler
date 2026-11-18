import json
from unittest.mock import Mock

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

ENDPOINT = "https://ai.invalid/chat"
ENCRYPTION_KEY = "0123456789abcdef0123456789abcdef"


@pytest.fixture
def settings(monkeypatch):
    ai = AITriage(enabled=True, endpoint=ENDPOINT, model="qa-model")
    monkeypatch.setattr(config.core, "ai", ai)
    monkeypatch.setattr(config.system, "encryption_key", ENCRYPTION_KEY)
    monkeypatch.setattr(CLASSIFICATION, "enforce", False)
    return ai


def advertised():
    return any(item["id"] == "ai_triage" for item in actions.specifications())


@pytest.mark.parametrize(
    ("enabled", "api_key", "encryption_key", "available"),
    [
        (True, None, ENCRYPTION_KEY, True),
        (True, None, None, False),
        (True, "key", None, True),
        (False, None, None, False),
    ],
)
def test_availability_requires_enabled_and_a_credential_path(
    settings, monkeypatch, enabled, api_key, encryption_key, available
):
    settings.enabled = enabled
    settings.api_key = api_key
    monkeypatch.setattr(config.system, "encryption_key", encryption_key)

    assert service.is_available() == available
    assert ai_triage.is_available() == available
    assert advertised() == available


def test_operation_spec_does_not_leak_provider_configuration(settings):
    settings.api_key = "provider-secret"
    settings.headers = {"X-Provider-Key": "server-secret"}
    spec = next(item for item in actions.specifications() if item["id"] == "ai_triage")

    assert spec["roles"] == ai_triage.ROLES
    for private in ("provider-secret", "server-secret", "ai.invalid"):
        assert private not in json.dumps(spec)
    assert "provider-secret" not in repr(settings)


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"headers": {"aUtHoRiZaTiOn": "override"}}, "reserved"),
        ({"endpoint": "http://ai.invalid/chat"}, "HTTPS"),
        ({"endpoint": "https://user@ai.invalid/chat"}, "credentials"),
        ({"endpoint": None}, "endpoint is required"),
        ({"model": " "}, "model is required"),
        ({"system_prompt": " "}, "system prompt"),
    ],
)
def test_config_rejects_invalid_values(overrides, match):
    with pytest.raises(ValidationError, match=match):
        AITriage(**{"enabled": True, "endpoint": ENDPOINT, "model": "model", **overrides})


def test_config_accepts_localhost_http_and_many_concurrent_jobs():
    assert AITriage(enabled=True, endpoint="http://localhost:8080/chat", model="m", max_concurrent_jobs=20).enabled


@pytest.mark.parametrize(("enforce", "outcome"), [(False, "success"), (True, "error")])
def test_action_requires_access_control_only_when_classification_is_enforced(settings, monkeypatch, enforce, outcome):
    monkeypatch.setattr(CLASSIFICATION, "enforce", enforce)
    enqueue = Mock(return_value=1)
    monkeypatch.setattr(service, "enqueue_alerts", enqueue)
    user = make_user()
    user.access_control = None

    result = ai_triage.execute("event.kind:alert", user, auth_token="qa-token")

    assert result[0]["outcome"] == outcome
    assert enqueue.called == (not enforce)


@pytest.mark.parametrize(
    ("roles", "max_hits"),
    [(["user", "actionrunner_basic"], 3), (["user", "actionrunner_advanced"], 7), (["admin"], 7)],
)
def test_action_selects_configured_role_limit(settings, monkeypatch, roles, max_hits):
    settings.max_hits_basic, settings.max_hits_advanced = 3, 7
    user = make_user()
    user.type = roles
    enqueue = Mock(return_value=2)
    monkeypatch.setattr(service, "enqueue_alerts", enqueue)

    result = ai_triage.execute("event.kind:alert", user, auth_token="qa-token", prompt="Be concise")

    assert result[0]["outcome"] == "success"
    enqueue.assert_called_once_with("event.kind:alert", user, "qa-token", prompt="Be concise", max_hits=max_hits)


@pytest.mark.parametrize(
    ("enqueue", "outcome", "title"),
    [
        (Mock(return_value=0), "skipped", "No matching alerts"),
        (Mock(return_value=None), "error", "Hit limit exceeded"),
        (Mock(side_effect=RuntimeError("redis-password-secret")), "error", "AI triage could not be queued"),
    ],
)
def test_action_reports_empty_overflow_or_failed_selection(settings, monkeypatch, caplog, enqueue, outcome, title):
    monkeypatch.setattr(service, "enqueue_alerts", enqueue)

    result = ai_triage.execute("*:*", make_user(), auth_token="qa-token")

    assert (result[0]["outcome"], result[0]["title"]) == (outcome, title)
    assert "redis-password-secret" not in repr(result) + caplog.text


@pytest.fixture
def queue(settings, monkeypatch):
    queue = Mock()
    monkeypatch.setattr(service, "get_queue", lambda: queue)
    monkeypatch.setattr(service, "_eligible_targets", Mock(return_value=["hit-1", "hit-2"]))
    return queue


@pytest.mark.parametrize(
    ("api_key", "token", "stored"),
    [
        (None, "trusted-token", "ciphertext"),
        ("provider-secret", None, None),
        ("provider-secret", "incoming-token", None),
    ],
)
def test_enqueue_stores_minimal_jobs_and_only_encrypted_credentials(
    settings, queue, monkeypatch, api_key, token, stored
):
    settings.api_key = api_key
    encrypt = Mock(return_value="ciphertext")
    monkeypatch.setattr(service.auth_service, "encrypt_token", encrypt)

    count = service.enqueue_alerts("*:*", make_user(), token, prompt="  Be concise  ", max_hits=10)

    assert count == 2
    queue.push.assert_called_once_with(
        *[
            service.AIAlertJob(hit_id=hit_id, uname="analyst", bearer_token=stored, prompt="Be concise")
            for hit_id in ("hit-1", "hit-2")
        ]
    )
    assert encrypt.called == (stored is not None)
    for secret in ("trusted-token", "provider-secret", "incoming-token"):
        assert secret not in repr(queue.push.call_args)


@pytest.mark.parametrize("prompt", [None, "  ", 42])
def test_enqueue_ignores_blank_or_non_string_prompt(settings, queue, monkeypatch, prompt):
    monkeypatch.setattr(service.auth_service, "encrypt_token", lambda _token: "ciphertext")

    service.enqueue_alerts("*:*", make_user(), "token", prompt=prompt, max_hits=10)

    assert queue.push.call_args.args[0].prompt is None


@pytest.mark.parametrize(
    ("token", "targets", "result"),
    [(None, ["hit-1"], "raises"), ("token", [], 0), ("token", None, None)],
    ids=["no-credential", "empty", "overflow"],
)
def test_enqueue_pushes_nothing_without_credential_or_eligible_alerts(
    settings, queue, monkeypatch, token, targets, result
):
    monkeypatch.setattr(service, "_eligible_targets", lambda *_args: targets)

    if result == "raises":
        with pytest.raises(service.AITransportError, match="requires a Bearer"):
            service.enqueue_alerts("*:*", make_user(), token, max_hits=10)
    else:
        assert service.enqueue_alerts("*:*", make_user(), token, max_hits=10) == result

    queue.push.assert_not_called()


@pytest.mark.parametrize(("max_hits", "count"), [(10, 10), (10, 11)])
def test_selection_fetches_only_ids_and_rejects_overflow(settings, monkeypatch, max_hits, count):
    user = make_user()
    user.access_control = "howler.classification:TLP:U"
    storage = Mock()
    storage.hit.search.return_value = {"items": [make_hit(id=f"hit-{index}") for index in range(count)]}
    monkeypatch.setattr(service, "datastore", lambda: storage)

    targets = service._eligible_targets("event.kind:alert", user, max_hits=max_hits)

    storage.hit.search.assert_called_once_with(
        "(event.kind:alert) AND NOT howler.status:resolved AND NOT howler.assessment:*",
        as_obj=True,
        rows=max_hits + 1,
        fl="howler.id",
        access_control=user.access_control,
    )
    assert targets == (None if count > max_hits else [f"hit-{index}" for index in range(count)])


def test_provider_input_excludes_private_fields_without_mutating_hit(settings):
    settings.excluded_input_fields = ["howler.dossier", "howler.log", "howler.comment.value"]
    hit = make_hit(
        dossier=[make_lead("private opinion")],
        log=[{"timestamp": "NOW", "explanation": "private log", "user": "analyst"}],
        comment=[
            {
                "id": "00000000-0000-4000-8000-00000000000" + str(index),
                "user": f"analyst-{index}",
                "value": f"private {index}",
            }
            for index in (1, 2)
        ],
    )
    original = hit.as_primitives()

    data = service.provider_input(hit)

    assert [comment["user"] for comment in data["howler"]["comment"]] == ["analyst-1", "analyst-2"]
    assert data["event"]["original"] == "current telemetry"
    assert "private" not in json.dumps(data)
    assert hit.as_primitives() == original


@pytest.mark.parametrize("prompt", [None, "Prefer concise output"])
def test_system_prompt_is_additive(settings, prompt):
    built = service.build_system_prompt(prompt)

    assert built.startswith(settings.system_prompt)
    assert (prompt in built) if prompt else (built == settings.system_prompt)


def test_remove_path_recurses_nested_lists():
    data = {"a": {"b": [[[{"value": 1, "user": "u"}, {"value": 2, "keep": True}]], [{"value": 3, "other": 4}]], "c": 5}}

    remove_path(data, "a.b.value")

    assert data == {"a": {"b": [[[{"user": "u"}, {"keep": True}]], [{"other": 4}]], "c": 5}}


def test_save_replaces_only_managed_lead_and_retries_on_concurrent_edit(settings, monkeypatch):
    def hit_with(first_lead):
        return make_hit(
            dossier=[
                make_lead(first_lead),
                make_lead("old generated note", service.LEAD_OWNER),
                make_lead("Another integration note", "another.plugin"),
            ]
        )

    second_hit = hit_with("Concurrent analyst edit")
    save_hit = Mock(side_effect=[VersionConflictException("race"), None])
    monkeypatch.setattr(
        service.hit_service, "get_hit", Mock(side_effect=[(hit_with("Analyst's note"), "v1"), (second_hit, "v2")])
    )
    monkeypatch.setattr(service.hit_service, "save_hit", save_hit)

    assert service.save_ai_lead("hit-1", make_user(), "new generated note")

    assert [c.kwargs["version"] for c in save_hit.call_args_list] == ["v1", "v2"]
    saved = save_hit.call_args.args[0]
    assert [lead.content for lead in saved.howler.dossier] == [
        "Concurrent analyst edit",
        "Another integration note",
        "new generated note",
    ]
    assert json.loads(saved.howler.dossier[-1].metadata) == {"owner": service.LEAD_OWNER}


@pytest.mark.parametrize(
    "hit",
    [make_hit(status="resolved"), make_hit(assessment="legitimate"), None],
    ids=["resolved", "assessed", "missing"],
)
def test_save_skips_alert_that_is_missing_or_ineligible(settings, monkeypatch, hit):
    save_hit = Mock()
    monkeypatch.setattr(service.hit_service, "get_hit", Mock(return_value=(hit, "version")))
    monkeypatch.setattr(service.hit_service, "save_hit", save_hit)

    assert not service.save_ai_lead("hit-1", make_user(), "generated note")

    save_hit.assert_not_called()


def test_save_stops_after_retries_are_exhausted(settings, monkeypatch):
    get_hit = Mock(return_value=(make_hit(), "version"))
    save_hit = Mock(side_effect=VersionConflictException("race"))
    monkeypatch.setattr(service.hit_service, "get_hit", get_hit)
    monkeypatch.setattr(service.hit_service, "save_hit", save_hit)

    assert not service.save_ai_lead("hit-1", make_user(), "generated note")

    assert get_hit.call_count == save_hit.call_count == service.AI_LEAD_RETRIES


@pytest.mark.parametrize("metadata", ["not-json", "[]", "null", "42"])
def test_lead_owner_handles_malformed_or_non_object_metadata(metadata):
    lead = make_lead("bad metadata")
    lead["metadata"] = metadata
    assert service._lead_owner(service.Lead(lead)) is None
