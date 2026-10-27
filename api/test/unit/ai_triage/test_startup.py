"""Exercise the installed server entrypoint, not a forced startup helper invocation."""

import json
import os
import socket
import subprocess
import sys
import time
from contextlib import ExitStack
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import pytest
from redis import Redis

import howler

from .subprocess_support import controlled_environment, hostile_parent_environment


@pytest.fixture
def startup_environment(tmp_path, monkeypatch, request):
    redis_url = urlparse(os.environ.get("AI_TRIAGE_TEST_REDIS_URL", "redis://127.0.0.1:6379/15"))
    es_url = urlparse(os.environ.get("AI_TRIAGE_TEST_ES_URL", "http://127.0.0.1:9200"))
    # Production's Redis connection uses DB0. Never start a real consumer against
    # unrelated pending jobs. The actual recovery tests use unique DB15 prefixes.
    client = Redis(host=redis_url.hostname, port=redis_url.port, socket_connect_timeout=2, socket_timeout=2)
    try:
        assert client.ping()
        assert not list(client.scan_iter(match="howler.ai_triage:{jobs}:*")), "Startup probe requires an empty AI queue"
    finally:
        client.close()
    settings = {
        "ui": {"debug": True, "audit": False},
        "auth": {"oauth": {"enabled": False}},
        "core": {
            "ai": {"enabled": True, "endpoint": "http://127.0.0.1:1/chat", "model": "qa-startup"},
            "plugins": [],
            "telemetry": {"enabled": False},
            "redis": {
                kind: {"host": redis_url.hostname, "port": redis_url.port} for kind in ("persistent", "nonpersistent")
            },
        },
        "system": {
            "encryption_key": "0123456789abcdef0123456789abcdef",
            **{name: {"enabled": False} for name in ("action_queue", "correlation", "retention", "view_cleanup")},
        },
        "datastore": {"hosts": [{"name": "qa_startup", "scheme": es_url.scheme, "host": es_url.netloc}]},
    }
    (tmp_path / "config.yml").write_text(json.dumps(settings))
    (tmp_path / "classification.yml").write_text(
        (Path(__file__).parents[3] / "build_scripts" / "classification.yml").read_text()
    )
    with ExitStack() as context:
        if getattr(request, "param", False):
            context.enter_context(hostile_parent_environment(monkeypatch, tmp_path))
        yield controlled_environment(
            Path(howler.__file__).resolve().parent.parent,
            settings,
            HWL_CONF_FOLDER=str(tmp_path),
            HWL_PLUGIN_DIRECTORY=str(tmp_path / "empty-plugins"),
            HWL_DATASTORE_INDEX_PREFIX=f"ai-triage-startup-{uuid4().hex}",
        )


@pytest.mark.parametrize("startup_environment", [False, True], indirect=True, ids=["clean", "hostile-parent"])
def test_actual_ordinary_debug_poetry_server_starts_consumers_without_reloader_overrides(startup_environment, tmp_path):
    env = startup_environment
    assert not {"TESTING", "WERKZEUG_RUN_MAIN", "HWL_START_BACKGROUND_SERVICES"} & env.keys()
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    env["FLASK_RUN_PORT"] = str(port)
    log_path = tmp_path / "server.log"
    with log_path.open("w") as log:
        process = subprocess.Popen(
            ["poetry", "run", "server"],
            # Poetry resolves script declarations from the package, not just
            # the installed console script. In cross-worktree QA this must be
            # the read-only backend under test rather than our pre-feature TOML.
            cwd=Path(howler.__file__).resolve().parent.parent,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 15
            ready = False
            while time.monotonic() < deadline and process.poll() is None:
                output = log_path.read_text()
                if "Started 4 AI triage worker consumer(s)" in output and "Debug mode: on" in output:
                    try:
                        with socket.create_connection(("127.0.0.1", port), timeout=0.2) as connection:
                            connection.sendall(b"GET /api/v1/healthz/ HTTP/1.0\r\nHost: localhost\r\n\r\n")
                            ready = connection.recv(1024).startswith(b"HTTP/")
                    except OSError:
                        pass
                    if ready:
                        break
                time.sleep(0.05)
            assert process.poll() is None and ready, log_path.read_text()
            assert "Restarting with" not in log_path.read_text(), "The supported entrypoint must not run a reloader"
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


@pytest.mark.parametrize("testing", [False, True])
def test_unpatched_import_is_inert_but_actual_serving_fails_clearly(startup_environment, testing):
    env = startup_environment
    if testing:
        env["TESTING"] = "true"
        env["HWL_UI__DEBUG"] = "false"
    code = """
import howler.app as application
from howler.services import ai_triage_worker as worker
from gevent import monkey
assert not monkey.is_module_patched('socket')
assert not worker._started and not worker._workers
assert not application._background_services_started
try:
    application.main(use_reloader=False)
except RuntimeError as error:
    assert 'gevent' in str(error) and 'server' in str(error)
else:
    raise AssertionError('Unsupported serving did not fail clearly')
assert not worker._started and not worker._workers
print('QA_IMPORT_AND_REJECTION_OK')
"""
    result = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "QA_IMPORT_AND_REJECTION_OK" in result.stdout
