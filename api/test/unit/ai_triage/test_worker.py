from types import SimpleNamespace
from unittest.mock import Mock

from howler.cronjobs import ai_triage_worker
from howler.services import ai_transport, ai_triage_service, auth_service, hit_service

from .support import make_hit, make_user


def make_job(hit_id="hit-1"):
    return {"hit_id": hit_id, "uname": "analyst", "bearer_token": "encrypted-token", "prompt": "Be concise"}


def setup_worker(monkeypatch, *, hit=None, user=None):
    user = user or make_user()
    hit = hit or make_hit()
    save = Mock(return_value=True)
    load_user = Mock(return_value=user)
    get_hit = Mock(return_value=(hit, "source-version"))
    generate = Mock(return_value="generated opinion")
    monkeypatch.setattr(
        ai_triage_worker, "config", SimpleNamespace(core=SimpleNamespace(ai=SimpleNamespace(timeout_seconds=30)))
    )
    monkeypatch.setattr(ai_triage_worker.time, "monotonic", lambda: 10)
    monkeypatch.setattr(ai_triage_service, "load_current_user", load_user)
    monkeypatch.setattr(ai_triage_service, "build_system_prompt", Mock(return_value="safe system prompt"))
    monkeypatch.setattr(ai_triage_service, "provider_input", Mock(return_value={"event": "alert"}))
    monkeypatch.setattr(ai_triage_service, "save_ai_lead", save)
    monkeypatch.setattr(hit_service, "get_hit", get_hit)
    monkeypatch.setattr(auth_service, "decrypt_token", Mock(return_value="trusted-token"))
    monkeypatch.setattr(ai_transport, "generate", generate)
    return generate, save, load_user, get_hit, user


def test_worker_processes_one_alert_and_saves(monkeypatch):
    generate, save, _load_user, get_hit, user = setup_worker(monkeypatch)

    ai_triage_worker._process(make_job())

    generate.assert_called_once()
    assert generate.call_args.args[1] == "trusted-token"
    assert generate.call_args.args[2] == "safe system prompt"
    assert generate.call_args.kwargs["deadline"] == 40
    get_hit.assert_called_once_with("hit-1", as_odm=True, version=True, user=user)
    save.assert_called_once_with("hit-1", user, "generated opinion")


def test_worker_discards_job_after_role_or_account_revocation(monkeypatch):
    revoked_user = Mock(uname="analyst", is_active=True, type=["user"])
    generate, save, _load_user, get_hit, _user = setup_worker(monkeypatch, user=revoked_user)

    ai_triage_worker._process(make_job())

    generate.assert_not_called()
    get_hit.assert_not_called()
    save.assert_not_called()


def test_worker_discards_alert_that_is_no_longer_eligible(monkeypatch):
    hit = make_hit(status="resolved")
    generate, save, _load_user, _get_hit, _user = setup_worker(monkeypatch, hit=hit)

    ai_triage_worker._process(make_job())

    generate.assert_not_called()
    save.assert_not_called()


def test_worker_logs_provider_failure_reason_and_discards_result(monkeypatch, caplog):
    generate, save, _load_user, _get_hit, _user = setup_worker(monkeypatch)
    generate.side_effect = ai_transport.AITransportError("provider unavailable")

    ai_triage_worker._process(make_job())

    assert "provider unavailable" in caplog.text
    save.assert_not_called()


def test_worker_hides_unexpected_exception_details(monkeypatch, caplog):
    generate, save, _load_user, _get_hit, _user = setup_worker(monkeypatch)
    generate.side_effect = RuntimeError("credential-secret")

    ai_triage_worker._process(make_job())

    assert "AI triage job failed" in caplog.text
    assert "credential-secret" not in caplog.text
    save.assert_not_called()


def test_setup_starts_configured_threads_idempotently(monkeypatch):
    thread = Mock(is_alive=Mock(return_value=True))
    factory = Mock(return_value=thread)
    monkeypatch.setattr(ai_triage_worker, "_threads", {})
    monkeypatch.setattr(ai_triage_worker.threading, "Thread", factory)
    monkeypatch.setattr(
        ai_triage_worker, "config", SimpleNamespace(core=SimpleNamespace(ai=SimpleNamespace(max_concurrent_jobs=3)))
    )
    monkeypatch.setattr(ai_triage_service, "is_available", lambda: True)

    ai_triage_worker.setup_job(Mock())
    ai_triage_worker.setup_job(Mock())

    assert factory.call_count == 3
    assert [call.kwargs["name"] for call in factory.call_args_list] == [
        "ai-triage-consumer-0",
        "ai-triage-consumer-1",
        "ai-triage-consumer-2",
    ]
    assert all(call.kwargs["target"] is ai_triage_worker.run_worker for call in factory.call_args_list)
    assert all(call.kwargs["daemon"] is True for call in factory.call_args_list)
    assert thread.start.call_count == 3


def test_setup_does_not_start_threads_when_unavailable(monkeypatch):
    factory = Mock()
    monkeypatch.setattr(ai_triage_worker, "_threads", {})
    monkeypatch.setattr(ai_triage_worker.threading, "Thread", factory)
    monkeypatch.setattr(ai_triage_service, "is_available", lambda: False)

    ai_triage_worker.setup_job(Mock())

    factory.assert_not_called()
