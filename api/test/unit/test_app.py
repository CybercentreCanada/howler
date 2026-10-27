from unittest.mock import Mock

import howler.app as howler_app


def test_should_start_background_services(monkeypatch):
    """Workers start in production, serving, Gunicorn, and functional-test processes."""
    monkeypatch.setattr(howler_app, "DEBUG", True)
    monkeypatch.setattr(howler_app.sys, "argv", ["flask"])
    monkeypatch.delenv("WERKZEUG_RUN_MAIN", raising=False)
    monkeypatch.delenv("HWL_START_BACKGROUND_SERVICES", raising=False)
    monkeypatch.delenv("TESTING", raising=False)

    assert not howler_app._should_start_background_services()

    monkeypatch.setenv("TESTING", "true")
    assert not howler_app._should_start_background_services()

    monkeypatch.setenv("WERKZEUG_RUN_MAIN", "true")
    assert howler_app._should_start_background_services()

    monkeypatch.delenv("WERKZEUG_RUN_MAIN")
    monkeypatch.setenv("HWL_START_BACKGROUND_SERVICES", "true")
    assert howler_app._should_start_background_services()

    monkeypatch.delenv("HWL_START_BACKGROUND_SERVICES")
    monkeypatch.delenv("TESTING")
    monkeypatch.setattr(howler_app.sys, "argv", ["gunicorn"])
    assert howler_app._should_start_background_services()

    monkeypatch.setattr(howler_app, "DEBUG", False)
    monkeypatch.setattr(howler_app.sys, "argv", ["flask"])
    assert howler_app._should_start_background_services()


def test_ai_startup_does_not_start_action_queue_consumers(monkeypatch):
    from howler.cronjobs import action_queue_worker
    from howler.services import ai_triage_worker

    monkeypatch.setattr(howler_app, "HWL_USE_REST_API", True)
    monkeypatch.setattr(howler_app, "DEBUG", False)
    monkeypatch.setattr(howler_app, "_background_services_started", False)
    monkeypatch.setattr(howler_app, "_should_start_background_services", lambda: True)
    monkeypatch.setattr(howler_app.config.system.action_queue, "enabled", True)
    start_workers = Mock(return_value=True)
    setup_action_workers = Mock()
    monkeypatch.setattr(ai_triage_worker, "start_workers", start_workers)
    monkeypatch.setattr(action_queue_worker, "setup_job", setup_action_workers)

    assert howler_app._start_ai_triage_workers()

    start_workers.assert_called_once_with()
    setup_action_workers.assert_not_called()
