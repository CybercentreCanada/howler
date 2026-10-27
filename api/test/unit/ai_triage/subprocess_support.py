"""Controlled child environments and disposable hostile-environment sentinels."""

import json
import os
import threading
from contextlib import contextmanager
from socketserver import BaseRequestHandler, ThreadingTCPServer


def controlled_environment(backend_path, settings, **overrides):
    # Allowlist process-launch essentials, rather than trying to enumerate every
    # Pydantic config group, mixed-case spelling, reloader or plugin indicator.
    # In particular no inherited HWL_*, APP_NAME, FLASK_*, WERKZEUG_*, TESTING,
    # coverage hook, proxy, Python startup hook, or top-level JSON group survives.
    keep = {"PATH", "VIRTUAL_ENV", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "LC_CTYPE", "TMPDIR"}
    env = {key: value for key, value in os.environ.items() if key in keep}
    env.update(
        APP_NAME="howler",
        PYTHONPATH=str(backend_path),
        PYTHONSAFEPATH="1",
        PYTHONUNBUFFERED="1",
        PYTHONDONTWRITEBYTECODE="1",
        PYTHON_DOTENV_DISABLED="1",
        **{f"HWL_{group.upper()}": json.dumps(value) for group, value in settings.items()},
        **overrides,
    )
    return env


@contextmanager
def hostile_parent_environment(monkeypatch, tmp_path):
    """All hostile addresses point to our disposable TCP sink, never live queues."""
    attempts = []

    class SentinelHandler(BaseRequestHandler):
        def handle(self):
            attempts.append(self.client_address)

    with ThreadingTCPServer(("127.0.0.1", 0), SentinelHandler) as sentinel:
        thread = threading.Thread(target=sentinel.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
        thread.start()
        port = sentinel.server_address[1]
        host = {"host": "127.0.0.1", "port": port}
        core = {"redis": {kind: host for kind in ("persistent", "nonpersistent")}, "ai": {"enabled": True}}
        system = {name: {"enabled": True} for name in ("action_queue", "correlation", "retention", "view_cleanup")}
        hostile = {
            "HWL_CORE": json.dumps(core),
            "hwl_core": json.dumps(core),
            "HwL_CoRe__ReDiS__PeRsIsTeNt__PoRt": str(port),
            "HWL_SYSTEM": json.dumps(system),
            "hwl_system": json.dumps(system),
            "HWL_SYSTEM__ACTION_QUEUE__ENABLED": "true",
            "hwl_system__correlation__enabled": "true",
            "HWL_DATASTORE": json.dumps({"hosts": [{"name": "hostile", "host": f"127.0.0.1:{port}"}]}),
            "hwl_auth": json.dumps({"oauth": {"enabled": True}}),
            "HWL_UI": json.dumps({"debug": False}),
            "hwl_ui__debug": "true",
            "HWL_START_BACKGROUND_SERVICES": "true",
            "hwl_start_background_services": "true",
            "WERKZEUG_RUN_MAIN": "true",
            "werkzeug_run_main": "true",
            "FLASK_RUN_FROM_CLI": "true",
            "TESTING": "false",
            "APP_NAME": "hostile-howler",
            "HWL_CONF_FOLDER": str(tmp_path / "hostile-config"),
            "HWL_PLUGIN_DIRECTORY": str(tmp_path / "hostile-plugins"),
            "COV_CORE_SOURCE": "hostile-coverage-hook",
        }
        for key, value in hostile.items():
            monkeypatch.setenv(key, value)
        try:
            yield attempts
        finally:
            sentinel.shutdown()
            thread.join(timeout=2)
            assert not attempts, "A subprocess contacted the disposable hostile configuration sentinel"
