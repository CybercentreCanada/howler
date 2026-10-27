"""Called only inside worker_probe's production early-patched subprocess."""

import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import gevent
import requests

from howler.odm.models.config import config
from howler.services import ai_transport
from howler.services import ai_triage_queue as queue
from howler.services import ai_triage_service as service
from howler.services import ai_triage_worker as worker


def exercise_runtime(payload, storage):  # noqa: C901 -- one lifecycle for real cancellation boundaries
    scenario = payload["runtime"]
    body = (
        json.dumps(
            {"choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": "complete opinion"}}]}
        ).encode()
        + b" " * 10000
    )
    assert len(body) > 8192
    arrived = threading.Event()
    closed = threading.Event()
    read_entered = threading.Event()
    read_cancelled = threading.Event()
    closed_times = []
    requests_seen = []

    class TrickleHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *_args: object) -> None:
            pass

        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            response_body = body
            if config.core.ai.provider == "a2a":
                response_body = (
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": request["id"],
                            "result": {
                                "kind": "task",
                                "id": "loopback-task",
                                "status": {"state": "completed"},
                                "artifacts": [
                                    {"artifactId": "opinion", "parts": [{"kind": "text", "text": "complete opinion"}]}
                                ],
                            },
                        }
                    ).encode()
                    + b" " * 10000
                )
            content_type = "application/json"
            if payload.get("response_mode") == "sse":
                assert config.core.ai.provider == "a2a"
                response_body = b"data: " + response_body + b"\n\n"
                content_type = "text/event-stream"
            assert len(response_body) > 8192
            requests_seen.append(time.monotonic())
            arrived.set()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(response_body)))
            self.end_headers()
            try:
                for byte in response_body:
                    self.wfile.write(bytes([byte]))
                    self.wfile.flush()
                    time.sleep(0.005)
            except OSError:
                closed_times.append(time.monotonic())
                closed.set()

    server = ThreadingHTTPServer(("127.0.0.1", 0), TrickleHandler)
    serving = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    serving.start()
    config.core.ai.endpoint = f"http://127.0.0.1:{server.server_port}/chat"
    config.core.ai.max_concurrent_jobs = 1
    config.core.ai.lease_seconds = 1
    run = queue.read_run(payload["run_id"])
    budget = 3.0 if scenario == "lease_loss" else 0.5
    run["results"][0]["_deadline_at"] = time.time() + budget
    queue.redis_client().set(queue._run_key(run["run_id"]), json.dumps(run))
    original_heartbeat = queue.heartbeat
    original_user = service.get_user
    original_session = requests.Session
    if scenario == "lease_loss":
        queue.heartbeat = lambda *_: None  # renewal failure, not a forged ownership decision
    elif scenario == "slow_user_read":

        def slow_user(uname):
            read_entered.set()
            try:
                time.sleep(2)
                return original_user(uname)
            finally:
                read_cancelled.set()

        service.get_user = slow_user
    started = time.monotonic()
    try:
        if scenario == "provider_timeout":
            config.core.ai.timeout_seconds = 1
            response_closes = []
            session_closes = []

            class ObservedSession(original_session):
                def send(self, *args, **kwargs):
                    response = super().send(*args, **kwargs)
                    original_close = response.close

                    def close_response():
                        response_closes.append(time.monotonic())
                        return original_close()

                    response.close = close_response
                    return response

                def close(self):
                    session_closes.append(time.monotonic())
                    return super().close()

            requests.Session = ObservedSession
            # There is deliberately no worker-level item timeout here. The real
            # adapter must bound its own shorter provider budget while blocked
            # inside a fixed-length read that never reaches an 8192-byte chunk.
            with gevent.Timeout(2.5, AssertionError("Shorter provider timeout did not interrupt the HTTP read")):
                try:
                    ai_transport.generate(
                        config.core.ai,
                        "qa-loopback-token",
                        config.core.ai.system_prompt,
                        {"event": "trickle"},
                        deadline=started + 5,
                        checkpoint=lambda *_: True,
                    )
                except ai_transport.AITransportError as exc:
                    assert exc.transient
                else:
                    raise AssertionError("A provider must not succeed after its shorter timeout")
            elapsed = time.monotonic() - started
            assert 0.75 < elapsed < 1.7
            assert arrived.is_set() and closed.wait(0.5)
            assert len(requests_seen) == 1
            assert response_closes and session_closes  # Repeated close() calls are harmless/idempotent.
            assert response_closes[0] <= session_closes[0] < started + 1.7
            assert closed_times[0] < started + 1.8
            assert not storage.hit.get(payload["hit_id"]).howler.dossier
            sys.stdout.write(
                "QA_RESULT="
                + json.dumps(
                    {
                        "runtime": scenario,
                        "provider_calls": len(requests_seen),
                        "cancelled_in": elapsed,
                        "response_closed": True,
                        "session_closed": True,
                        "response_mode": payload.get("response_mode", "json"),
                    }
                )
                + "\n"
            )
            return
        assert worker.start_workers()
        if scenario == "slow_user_read":
            assert read_entered.wait(1), "Worker did not enter the user read"
            assert read_cancelled.wait(1), "The item deadline did not cancel its pre-provider user read"
            assert time.monotonic() - started < 1.2
            assert not requests_seen
        else:
            assert arrived.wait(1), "The real provider request did not reach loopback"
            assert closed.wait(1), "The provider connection stayed open beyond its cancellation budget"
            assert closed_times[0] - started < 1.2
            assert len(requests_seen) == 1
        raw = queue.read_run(run["run_id"])
        item = raw["results"][0]
        expiry = item.get("_lease_expires_at", item["_deadline_at"])
        if scenario == "lease_loss":
            assert closed_times[0] < started + 0.9
            assert queue.claim_next()[0] is None, "A permit was reused before the original lease expired"
        worker.stop_workers(timeout=2)
        gevent.sleep(0)
        time.sleep(max(0, expiry - time.time()) + 0.05)
        next_job, _ = queue.claim_next()
        if scenario == "lease_loss":
            assert next_job is not None and next_job["run_id"] == run["run_id"]
            assert closed.is_set(), "Permit reuse preceded local HTTP cleanup"
        else:
            assert next_job is None
            assert queue.read_run(run["run_id"])["counts"]["failed"] == 1
        assert not storage.hit.get(payload["hit_id"]).howler.dossier
        sys.stdout.write(
            "QA_RESULT="
            + json.dumps(
                {
                    "runtime": scenario,
                    "provider_calls": len(requests_seen),
                    "cancelled_in": (closed_times[0] if closed_times else time.monotonic()) - started,
                }
            )
            + "\n"
        )
    finally:
        worker.stop_workers(timeout=2)
        queue.heartbeat = original_heartbeat
        service.get_user = original_user
        requests.Session = original_session
        server.shutdown()
        server.server_close()
        serving.join(timeout=2)
