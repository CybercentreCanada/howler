from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from howler.cronjobs import ai_triage_worker
from howler.services import ai_service, auth_service, hit_service, user_service

from .support import make_hit, make_user


def make_job(bearer_token="encrypted-token"):
    return ai_service.AIAlertJob(hit_id="hit-1", uname="analyst", bearer_token=bearer_token, prompt="Be concise")


@pytest.fixture
def worker(monkeypatch):
    mocks = SimpleNamespace(
        user=make_user(),
        get_user=Mock(),
        get_hit=Mock(),
        generate=Mock(return_value="generated opinion"),
        save=Mock(return_value=True),
        decrypt=Mock(return_value="trusted-token"),
    )
    mocks.get_user.return_value = mocks.user
    mocks.get_hit.return_value = make_hit()
    monkeypatch.setattr(user_service, "get_user", mocks.get_user)
    monkeypatch.setattr(hit_service, "get_hit", mocks.get_hit)
    monkeypatch.setattr(auth_service, "decrypt_token", mocks.decrypt)
    monkeypatch.setattr(ai_service, "generate", mocks.generate)
    monkeypatch.setattr(ai_service, "save_ai_lead", mocks.save)
    return mocks


@pytest.mark.parametrize(("bearer_token", "expected"), [("encrypted-token", "trusted-token"), (None, None)])
def test_worker_generates_and_saves(worker, bearer_token, expected):
    ai_triage_worker._process(make_job(bearer_token))

    worker.get_user.assert_called_once_with("analyst", as_odm=True, version=False)
    worker.get_hit.assert_called_once_with("hit-1", as_odm=True, user=worker.user)
    assert worker.decrypt.called == (bearer_token is not None)
    config, token, system_prompt, alert = worker.generate.call_args.args
    assert (config, token) == (ai_triage_worker.config.core.ai, expected)
    assert "Be concise" in system_prompt
    assert alert["howler"]["id"] == worker.get_hit.return_value.howler.id
    worker.save.assert_called_once_with("hit-1", worker.user, "generated opinion")


@pytest.mark.parametrize(
    "initiator",
    [
        None,
        Mock(is_active=False, type=["user", "actionrunner_basic"]),
        Mock(is_active=True, type=["user"]),
    ],
    ids=["missing", "inactive", "revoked-role"],
)
def test_worker_discards_unauthorized_initiator(worker, initiator):
    worker.get_user.return_value = initiator

    ai_triage_worker._process(make_job())

    worker.get_hit.assert_not_called()
    worker.generate.assert_not_called()
    worker.save.assert_not_called()


@pytest.mark.parametrize(
    "hit",
    [None, make_hit(status="resolved"), make_hit(assessment="legitimate")],
    ids=["inaccessible", "resolved", "assessed"],
)
def test_worker_discards_alert_that_is_no_longer_eligible(worker, hit):
    worker.get_hit.return_value = hit

    ai_triage_worker._process(make_job())

    worker.generate.assert_not_called()
    worker.save.assert_not_called()


@pytest.mark.parametrize(
    ("failure", "logged", "hidden"),
    [
        (ai_service.AITransportError("provider unavailable"), "provider unavailable", None),
        (RuntimeError("credential-secret"), "AI triage job failed", "credential-secret"),
    ],
)
def test_worker_logs_safely_and_discards_failed_job(worker, caplog, failure, logged, hidden):
    worker.generate.side_effect = failure

    ai_triage_worker._process(make_job())

    assert logged in caplog.text
    assert hidden is None or hidden not in caplog.text
    worker.save.assert_not_called()


@pytest.mark.parametrize(("available", "started"), [(True, 3), (False, 0)])
def test_setup_starts_configured_threads_idempotently(monkeypatch, available, started):
    thread = Mock(is_alive=Mock(return_value=True))
    factory = Mock(return_value=thread)
    monkeypatch.setattr(ai_triage_worker, "_threads", {})
    monkeypatch.setattr(ai_triage_worker.threading, "Thread", factory)
    monkeypatch.setattr(ai_triage_worker.config.core.ai, "max_concurrent_jobs", 3)
    monkeypatch.setattr(ai_service, "is_available", lambda: available)

    ai_triage_worker.setup_job(Mock())
    ai_triage_worker.setup_job(Mock())

    assert factory.call_count == thread.start.call_count == started
    assert [c.kwargs["name"] for c in factory.call_args_list] == [f"ai-triage-consumer-{i}" for i in range(started)]
    assert all(c.kwargs["target"] is ai_triage_worker.run_worker and c.kwargs["daemon"] for c in factory.call_args_list)
