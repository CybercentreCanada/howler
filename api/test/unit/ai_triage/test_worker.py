from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock

from howler.services import ai_transport, ai_triage_queue, ai_triage_service, ai_triage_worker


def make_job():
    return {
        "run_id": "run-1",
        "index": 0,
        "hit_id": "hit-1",
        "nonce": "nonce-1",
        "deadline_at": 200,
        "attempts": 1,
        "run": {"run_id": "run-1", "results": [{"hit_id": "hit-1"}]},
    }


def setup_worker(monkeypatch, provider_result="generated opinion"):
    user = Mock()
    current_run = {"results": [{}], "_prompt": "Keep it brief"}
    hit = Mock()
    candidate = {"content": "generated opinion"}
    queue = {
        "lease_is_current": Mock(return_value=True),
        "begin_provider_attempt": Mock(return_value={"run": current_run}),
        "store_candidate": Mock(return_value=True),
        "finish_item": Mock(return_value=current_run),
    }
    service = {
        "run_owner_and_token": Mock(return_value=(user, "trusted-token", current_run)),
        "user_can_run_ai_triage": Mock(return_value=True),
        "get_current_user": Mock(return_value=user),
        "get_current_hit": Mock(return_value=(hit, "version-1")),
        "_eligible_hit": Mock(return_value=True),
        "build_system_prompt": Mock(return_value="system prompt"),
        "provider_input": Mock(return_value={"event": "alert"}),
        "prepare_candidate": Mock(return_value=candidate),
        "save_ai_lead": Mock(return_value=(True, None)),
        "notify_run": Mock(),
    }
    for name, mock in queue.items():
        monkeypatch.setattr(ai_triage_queue, name, mock)
    for name, mock in service.items():
        monkeypatch.setattr(ai_triage_service, name, mock)

    def generate_response(*_args, **kwargs):
        assert kwargs["begin_attempt"]()
        return provider_result

    generate = Mock(side_effect=generate_response)
    monkeypatch.setattr(ai_transport, "generate", generate)
    monkeypatch.setattr(ai_triage_worker.gevent, "Timeout", lambda *_args: nullcontext())
    monkeypatch.setattr(
        ai_triage_worker,
        "time",
        SimpleNamespace(monotonic=lambda: 10, time=lambda: 100),
    )
    return queue, service, generate, candidate


def test_worker_saves_candidate_and_marks_run_succeeded(monkeypatch):
    queue, service, generate, candidate = setup_worker(monkeypatch)

    ai_triage_worker._process(make_job())

    generate.assert_called_once()
    assert generate.call_args.args[1] == "trusted-token"
    queue["begin_provider_attempt"].assert_called_once_with("run-1", 0, "nonce-1")
    queue["store_candidate"].assert_called_once_with("run-1", 0, "nonce-1", candidate)
    service["save_ai_lead"].assert_called_once()
    assert queue["finish_item"].call_args.kwargs["state"] == "succeeded"
    service["notify_run"].assert_called()


def test_worker_marks_provider_failure_without_saving(monkeypatch):
    failure = ai_transport.AITransportError("provider unavailable")
    queue, service, generate, _candidate = setup_worker(monkeypatch)
    generate.side_effect = failure

    ai_triage_worker._process(make_job())

    assert queue["finish_item"].call_args.kwargs["state"] == "failed"
    assert queue["finish_item"].call_args.kwargs["reason"] == "provider_error"
    service["save_ai_lead"].assert_not_called()
