import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock
from urllib.parse import urlparse
from uuid import uuid4

import pytest
import redis

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


def test_ai_triage_startup_does_not_start_action_queue_consumers(monkeypatch):
    """AI workers start independently without implicitly starting action consumers."""
    from howler.cronjobs import action_queue_worker
    from howler.services import ai_triage_service, ai_triage_worker

    monkeypatch.setattr(howler_app, "HWL_USE_REST_API", True)
    monkeypatch.setattr(howler_app, "HWL_USE_JOB_SYSTEM", False)
    monkeypatch.setattr(howler_app, "DEBUG", False)
    monkeypatch.setattr(howler_app, "_should_start_background_services", lambda: True)
    monkeypatch.setattr(howler_app.config.system.action_queue, "enabled", True)
    monkeypatch.setattr(ai_triage_service, "is_available", lambda: True)
    monkeypatch.setattr(ai_triage_worker, "start_workers", lambda: True)
    setup_action_workers = Mock()
    monkeypatch.setattr(action_queue_worker, "setup_job", setup_action_workers)

    assert howler_app._start_ai_triage_workers()
    setup_action_workers.assert_not_called()


def test_configured_ai_fails_fast_on_unpatched_serving_entrypoint(monkeypatch):
    import pytest

    from howler.services import ai_triage_worker

    monkeypatch.setattr(howler_app, "HWL_USE_REST_API", True)
    monkeypatch.setattr(howler_app, "DEBUG", False)
    monkeypatch.setattr(howler_app, "_should_start_background_services", lambda: True)
    monkeypatch.setattr(howler_app, "_background_services_started", False)
    monkeypatch.setattr(howler_app.config.core.ai, "enabled", True)
    monkeypatch.setattr(ai_triage_worker.monkey, "is_module_patched", lambda _module: False)

    with pytest.raises(RuntimeError, match="early-gevent-patched"):
        howler_app._start_ai_triage_workers()


@pytest.mark.parametrize("ai_enabled", [False, True], ids=["ai-disabled", "ai-enabled"])
def test_gunicorn_target_exports_patched_wsgi_app_and_starts_production_services(tmp_path, ai_enabled):
    """The container's actual Gunicorn target exports the patched Flask WSGI app."""
    redis_url = urlparse(os.environ.get("AI_TRIAGE_TEST_REDIS_URL", "redis://127.0.0.1:6379/15"))
    redis_host = redis_url.hostname or "127.0.0.1"
    redis_port = redis_url.port or 6379
    client = redis.Redis(host=redis_host, port=redis_port, socket_connect_timeout=2, socket_timeout=2)
    try:
        assert client.ping(), "Gunicorn import regression requires the isolated Redis service"
        assert not list(client.scan_iter(match="howler.ai_triage:{jobs}:*")), (
            "Gunicorn import regression requires an empty AI triage queue"
        )
    finally:
        client.close()

    settings = {
        "ui": {"debug": False, "audit": False},
        "auth": {"oauth": {"enabled": False}},
        "core": {
            "ai": {
                "enabled": ai_enabled,
                "endpoint": "http://127.0.0.1:1/chat",
                "model": "gunicorn-import-test",
            },
            "plugins": [],
            "telemetry": {"enabled": False},
            "redis": {name: {"host": redis_host, "port": redis_port} for name in ("persistent", "nonpersistent")},
        },
        "system": {
            "encryption_key": "0123456789abcdef0123456789abcdef",
            **{name: {"enabled": False} for name in ("action_queue", "correlation", "retention", "view_cleanup")},
        },
        "datastore": {"hosts": [{"name": "gunicorn-test", "scheme": "http", "host": "127.0.0.1:19289"}]},
    }
    (tmp_path / "config.yml").write_text(json.dumps(settings))
    (tmp_path / "classification.yml").write_text(
        (Path(__file__).parents[2] / "build_scripts" / "classification.yml").read_text()
    )
    plugins = tmp_path / "plugins"
    plugins.mkdir()

    # Use an allowlist, not inherited process state: importing the production
    # target must not be tricked into test, reloader, alternate config or
    # background-service override modes.
    keep = {"PATH", "VIRTUAL_ENV", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "LC_CTYPE", "TMPDIR"}
    env = {key: value for key, value in os.environ.items() if key in keep}
    env.update(
        APP_NAME="howler",
        HWL_CONF_FOLDER=str(tmp_path),
        HWL_PLUGIN_DIRECTORY=str(plugins),
        HWL_DATASTORE_INDEX_PREFIX=f"ai-triage-gunicorn-{uuid4().hex}",
        HWL_USE_REST_API="true",
        HWL_USE_WEBSOCKET_API="false",
        HWL_USE_JOB_SYSTEM="false",
        PYTHONPATH=str(Path(__file__).parents[2]),
        PYTHONSAFEPATH="1",
        PYTHONDONTWRITEBYTECODE="1",
        PYTHON_DOTENV_DISABLED="1",
        PYTHONUNBUFFERED="1",
    )
    code = """
from gevent import monkey
assert not monkey.is_module_patched('socket')
from gunicorn.util import import_app
application = import_app('howler.patched:app')
assert monkey.is_module_patched('socket')
from flask import Flask
from howler.services import ai_triage_worker
from howler.odm.models.config import config
assert isinstance(application, Flask) and callable(application)
assert ai_triage_worker._started
expected = config.core.ai.max_concurrent_jobs if config.core.ai.enabled else 1
assert len(ai_triage_worker._workers) == expected
ai_triage_worker.stop_workers(timeout=2)
print('GUNICORN_WSGI_IMPORT_OK')
"""
    result = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "GUNICORN_WSGI_IMPORT_OK" in result.stdout


def test_native_worker_timeout_retains_thread_handle_until_it_really_stops(monkeypatch):
    import threading

    from howler.services import ai_triage_worker

    ai_triage_worker.stop_workers(timeout=1)
    monkeypatch.setattr(ai_triage_worker, "_workers", [])
    monkeypatch.setattr(ai_triage_worker, "_started", True)
    monkeypatch.setattr(ai_triage_worker, "_stopping", False)
    monkeypatch.setattr(ai_triage_worker, "_use_gevent", False)
    entered, finish = threading.Event(), threading.Event()

    def deliberately_uninterruptible_worker():
        entered.set()
        finish.wait(timeout=2)

    worker = threading.Thread(target=deliberately_uninterruptible_worker, daemon=True)
    worker.start()
    ai_triage_worker._workers.append(worker)
    assert entered.wait(timeout=1)

    with pytest.raises(ai_triage_worker.WorkerShutdownError, match="did not join"):
        ai_triage_worker.stop_workers(timeout=0.05)

    assert worker in ai_triage_worker._workers
    assert ai_triage_worker._started and ai_triage_worker._stopping
    finish.set()
    worker.join(timeout=1)
    assert not worker.is_alive()
    ai_triage_worker.stop_workers(timeout=1)
    assert not ai_triage_worker._workers
    assert not ai_triage_worker._started and not ai_triage_worker._stopping
