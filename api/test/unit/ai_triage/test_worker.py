from types import SimpleNamespace
from unittest.mock import Mock

import gevent
from gevent.pool import Pool

from howler.cronjobs import ai_triage_worker
from howler.services import ai_transport, ai_triage_service, auth_service


def make_job(hit_id="hit-1"):
    return {"hit_id": hit_id, "uname": "analyst", "bearer_token": "encrypted-token", "prompt": "Be concise"}


def setup_worker(monkeypatch):
    user = Mock(uname="analyst")
    hit = Mock()
    can_run = Mock(return_value=True)
    eligible = Mock(return_value=True)
    save = Mock(return_value=True)
    load_user = Mock(return_value=user)
    load_hit = Mock(return_value=(hit, "generation-v1"))
    monkeypatch.setattr(ai_triage_service, "load_current_user", load_user)
    monkeypatch.setattr(ai_triage_service, "user_can_run_ai_triage", can_run)
    monkeypatch.setattr(ai_triage_service, "load_current_hit", load_hit)
    monkeypatch.setattr(ai_triage_service, "_eligible_hit", eligible)
    monkeypatch.setattr(ai_triage_service, "provider_input", Mock(return_value={"event": "alert"}))
    monkeypatch.setattr(ai_triage_service, "build_system_prompt", Mock(return_value="safe system prompt"))
    monkeypatch.setattr(ai_triage_service, "save_ai_lead", save)
    monkeypatch.setattr(auth_service, "decrypt_token", Mock(return_value="trusted-token"))
    generate = Mock(return_value="generated opinion")
    monkeypatch.setattr(ai_transport, "generate", generate)
    monkeypatch.setattr(ai_triage_worker.time, "monotonic", lambda: 10)
    return generate, save, can_run, eligible, load_user, load_hit


def test_worker_processes_one_alert_once_and_saves(monkeypatch):
    generate, save, _can_run, _eligible, load_user, _load_hit = setup_worker(monkeypatch)

    ai_triage_worker._process(make_job())

    generate.assert_called_once()
    assert generate.call_args.args[1] == "trusted-token"
    assert generate.call_args.args[2] == "safe system prompt"
    save.assert_called_once_with("hit-1", load_user.return_value, "generated opinion", "generation-v1")


def test_worker_drops_job_after_authorization_revocation(monkeypatch):
    generate, save, can_run, _eligible, _load_user, _load_hit = setup_worker(monkeypatch)
    can_run.return_value = False

    ai_triage_worker._process(make_job())

    generate.assert_not_called()
    save.assert_not_called()


def test_worker_drops_alert_that_is_no_longer_eligible(monkeypatch):
    generate, save, _can_run, eligible, _load_user, _load_hit = setup_worker(monkeypatch)
    eligible.return_value = False

    ai_triage_worker._process(make_job())

    generate.assert_not_called()
    save.assert_not_called()


def test_worker_discards_provider_failure_without_retry(monkeypatch):
    generate, save, _can_run, _eligible, _load_user, _load_hit = setup_worker(monkeypatch)
    generate.side_effect = ai_transport.AITransportError("provider unavailable")

    ai_triage_worker._process(make_job())

    generate.assert_called_once()
    save.assert_not_called()


def _pool_and_queue(jobs):
    remaining = list(jobs)
    queue = Mock(pop=Mock(side_effect=lambda **_kwargs: remaining.pop(0) if remaining else None))
    return Pool(1), queue


def _use_short_job_timeout(monkeypatch):
    monkeypatch.setattr(
        ai_triage_worker,
        "config",
        SimpleNamespace(core=SimpleNamespace(ai=SimpleNamespace(timeout_seconds=0.02))),
    )


def test_pre_provider_read_timeout_frees_pool_and_next_job_proceeds(monkeypatch):
    generate, save, _can_run, _eligible, load_user, load_hit = setup_worker(monkeypatch)
    _use_short_job_timeout(monkeypatch)
    load_user.side_effect = lambda uname: gevent.sleep(0.05) if load_user.call_count == 1 else load_user.return_value
    pool, queue = _pool_and_queue([make_job("slow-read"), make_job("next-alert")])

    ai_triage_worker._consume_one(queue, pool)
    pool.wait_available(timeout=1)

    assert generate.call_count == 0
    assert save.call_count == 0

    ai_triage_worker._consume_one(queue, pool)
    pool.wait_available(timeout=1)

    assert queue.pop.call_count == 2
    assert load_hit.call_args.args[0] == "next-alert"
    generate.assert_called_once()
    save.assert_called_once_with("next-alert", load_user.return_value, "generated opinion", "generation-v1")


def test_save_timeout_frees_pool_without_requeue_or_regeneration(monkeypatch):
    generate, save, _can_run, _eligible, load_user, load_hit = setup_worker(monkeypatch)
    _use_short_job_timeout(monkeypatch)
    save.side_effect = lambda *_args: gevent.sleep(0.05)
    pool, queue = _pool_and_queue([make_job("slow-save"), make_job("next-alert")])

    ai_triage_worker._consume_one(queue, pool)
    pool.wait_available(timeout=1)

    assert generate.call_count == 1
    assert save.call_count == 1

    save.side_effect = None
    save.return_value = True
    ai_triage_worker._consume_one(queue, pool)
    pool.wait_available(timeout=1)

    assert queue.pop.call_count == 2
    assert load_hit.call_args_list[0].args[0] == "slow-save"
    assert load_hit.call_args_list[1].args[0] == "next-alert"
    assert [call.args[0] for call in save.call_args_list] == ["slow-save", "next-alert"]
    assert generate.call_count == 2
    queue.unpop.assert_not_called()


def test_consumer_waits_for_pool_before_popping_and_spawns_one_job():
    order = []
    queue = Mock(pop=Mock(side_effect=lambda **_kwargs: order.append("pop") or {"hit_id": "hit-1"}))
    pool = Mock(
        wait_available=Mock(side_effect=lambda: order.append("capacity")),
        spawn=Mock(side_effect=lambda *_args: order.append("spawn")),
    )

    ai_triage_worker._consume_one(queue, pool)

    assert order == ["capacity", "pop", "spawn"]
    queue.pop.assert_called_once_with(blocking=True, timeout=1)


def test_setup_starts_one_daemon_consumer(monkeypatch):
    thread = Mock(is_alive=Mock(return_value=True))
    factory = Mock(return_value=thread)
    monkeypatch.setattr(ai_triage_worker, "_consumer", None)
    monkeypatch.setattr(ai_triage_worker.threading, "Thread", factory)
    monkeypatch.setattr(ai_triage_worker.monkey, "is_module_patched", lambda _module: True)
    monkeypatch.setattr(ai_triage_service, "is_available", lambda: True)

    ai_triage_worker.setup_job(Mock())
    ai_triage_worker.setup_job(Mock())

    factory.assert_called_once_with(target=ai_triage_worker.run_worker, name="ai-triage-consumer", daemon=True)
    thread.start.assert_called_once()


def test_setup_fails_closed_without_early_gevent_socket_patch(monkeypatch):
    factory = Mock()
    monkeypatch.setattr(ai_triage_worker, "_consumer", None)
    monkeypatch.setattr(ai_triage_worker.threading, "Thread", factory)
    monkeypatch.setattr(ai_triage_worker.monkey, "is_module_patched", lambda _module: False)
    monkeypatch.setattr(ai_triage_service, "is_available", lambda: True)

    try:
        ai_triage_worker.setup_job(Mock())
    except RuntimeError as exc:
        assert "early-gevent-patched" in str(exc)
    else:
        raise AssertionError("expected unpatched runtime to fail closed")

    factory.assert_not_called()
