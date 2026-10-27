from unittest.mock import Mock

import pytest

from howler.services import ai_triage_worker as worker


def test_start_and_stop_use_mock_threads_without_running_workers(monkeypatch):
    thread = Mock(is_alive=Mock(return_value=False))
    thread_factory = Mock(return_value=thread)
    monkeypatch.setattr(worker, "_started", False)
    monkeypatch.setattr(worker, "_stopping", False)
    monkeypatch.setattr(worker, "_workers", [])
    monkeypatch.setattr(worker, "_stop_event", Mock())
    monkeypatch.setattr(worker.threading, "Thread", thread_factory)
    monkeypatch.setattr(worker.monkey, "is_module_patched", lambda _name: False)
    monkeypatch.setattr(worker.config.core.ai, "enabled", False)
    monkeypatch.setattr(worker.ai_triage_service, "is_available", lambda: False)

    assert worker.start_workers()
    thread_factory.assert_called_once_with(target=worker.run_worker, name="ai-triage-worker-0", daemon=True)
    thread.start.assert_called_once()

    worker.stop_workers(timeout=0)

    thread.join.assert_called_once_with(timeout=0.0)
    assert not worker._workers


def test_enabled_workers_reject_unpatched_runtime_before_starting_threads(monkeypatch):
    monkeypatch.setattr(worker, "_started", False)
    monkeypatch.setattr(worker, "_stopping", False)
    monkeypatch.setattr(worker, "_workers", [])
    monkeypatch.setattr(worker.monkey, "is_module_patched", lambda _name: False)
    monkeypatch.setattr(worker.config.core.ai, "enabled", True)
    thread_factory = Mock()
    monkeypatch.setattr(worker, "threading", Mock(Thread=thread_factory))

    with pytest.raises(RuntimeError, match="early-gevent-patched"):
        worker.start_workers()

    thread_factory.assert_not_called()
