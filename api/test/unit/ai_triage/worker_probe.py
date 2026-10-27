"""Subprocess-only probe: real patched/unpatched scheduling and real queue/storage."""

import sys

# Patching in the main pytest process would contaminate every other test.
if "--mode=gevent" in sys.argv:
    import howler.patched  # noqa: F401  -- production early-patched entrypoint

import argparse
import json
import os
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse

import requests
from gevent import Greenlet
from redis import Redis

from howler.datastore.store import ESStore
from howler.odm.models.config import AITriage, Host, config
from howler.odm.models.hit import Hit
from howler.odm.models.user import User
from howler.services import ai_transport, hit_service
from howler.services import ai_triage_queue as queue
from howler.services import ai_triage_service as service
from howler.services import ai_triage_worker as worker


def main():  # noqa: C901 -- distinct startup modes share the same isolated lifecycle
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["native", "gevent"], required=True)
    parser.add_argument("--payload", required=True)
    args = parser.parse_args()
    assert not worker._started and not worker._workers, "Import-time workers escaped the controlled bootstrap"
    assert not {key.upper() for key in os.environ} & {"WERKZEUG_RUN_MAIN", "FLASK_RUN_FROM_CLI"}
    assert not config.ui.debug and not config.core.ai.enabled and not config.core.plugins
    assert not config.core.telemetry.enabled and not config.auth.oauth.enabled
    assert not any(
        getattr(config.system, name).enabled for name in ("action_queue", "correlation", "retention", "view_cleanup")
    )
    imported_app = sys.modules.get("howler.app")
    assert imported_app is None or not imported_app._background_services_started
    payload = json.loads(args.payload)
    client = Redis.from_url(payload["redis_url"], socket_connect_timeout=2, socket_timeout=2)
    queue.redis_client = lambda: client
    queue._KEY_PREFIX = payload["prefix"]
    config.core.ai = AITriage(**payload["settings"])
    config.system.encryption_key = "0123456789abcdef0123456789abcdef"
    endpoint = urlparse(payload["es_url"])
    isolated = config.model_copy(deep=True)
    isolated.datastore.hosts = [Host(name="qa_ai_triage", scheme=endpoint.scheme, host=endpoint.netloc)]
    store = ESStore(isolated)
    store.register(payload["hit_collection"], Hit)
    store.register(payload["user_collection"], User)
    storage = SimpleNamespace(hit=store[payload["hit_collection"]], user=store[payload["user_collection"]])
    service.datastore = lambda: storage
    hit_service.datastore = lambda: storage
    service.comms_service.emit = lambda *_args, **_kwargs: None
    calls = []

    def provider(*_args, **_kwargs):
        assert _kwargs["begin_attempt"]()
        calls.append(True)
        return "subprocess opinion"

    def no_http(*_args, **_kwargs):
        raise AssertionError("The scheduling probe must not contact HTTP providers")

    original_generate = ai_transport.generate
    original_request = requests.sessions.Session.request
    ai_transport.generate = provider
    requests.sessions.Session.request = no_http
    legacy_workers = []
    try:
        if payload.get("runtime"):
            # PYTHONSAFEPATH keeps the sibling production package authoritative;
            # explicitly add only this owned probe directory for the helper.
            sys.path.append(str(Path(__file__).resolve().parent))
            from http_runtime_probe import exercise_runtime

            # The runtime probe uses the real transport and only its loopback server.
            ai_transport.generate = original_generate
            requests.sessions.Session.request = original_request
            exercise_runtime(payload, storage)
            return
        if args.mode == "native" and config.core.ai.enabled:
            try:
                worker.start_workers()
            except RuntimeError as exc:
                assert "gevent" in str(exc)
            else:
                raise AssertionError("Enabled unpatched serving must fail rather than start unsafe provider threads")
            assert not worker._started and not worker._workers and not calls
            sys.stdout.write('QA_RESULT={"unsupported":true,"provider_calls":0,"legacy_workers":0}\n')
            return
        assert worker.start_workers()

        assert not worker.start_workers(), "Startup must be idempotent"
        active_workers = list(worker._workers)
        expected_type = Greenlet if args.mode == "gevent" else threading.Thread
        assert all(isinstance(item, expected_type) for item in active_workers)
        assert worker._use_gevent == (args.mode == "gevent")
        assert len(active_workers) == (config.core.ai.max_concurrent_jobs if config.core.ai.enabled else 1)
        if payload.get("late_run"):
            time.sleep(0.2)
            assert all(not item.dead if isinstance(item, Greenlet) else item.is_alive() for item in active_workers)
            queue.create_run(payload["late_run"])
        deadline = time.monotonic() + 12
        run_id = payload.get("run_id")
        final = None
        while time.monotonic() < deadline:
            if run_id is None:
                runs, _ = queue.list_runs(payload["owner"])
                run_id = runs[0]["run_id"] if runs else None
            if run_id:
                final = queue.read_run(run_id)
                if final and final["state"] == "completed":
                    break
            time.sleep(0.02)
        assert final and final["state"] == "completed", "Actual startup workers did not drain the durable run"
        assert final["counts"]["succeeded" if config.core.ai.enabled else "failed"] == 1
        assert len(calls) == (1 if config.core.ai.enabled else 0)
        assert "_encrypted_bearer_token" not in final
        worker.stop_workers(timeout=2)
        assert all(item.dead if isinstance(item, Greenlet) else not item.is_alive() for item in active_workers)
        sys.stdout.write(
            "QA_RESULT="
            + json.dumps(
                {
                    "mode": args.mode,
                    "run_id": run_id,
                    "counts": final["counts"],
                    "provider_calls": len(calls),
                    "legacy_workers": len(legacy_workers),
                }
            )
            + "\n"
        )
    finally:
        worker.stop_workers(timeout=2)
        store.close()
        client.close()


if __name__ == "__main__":
    main()
