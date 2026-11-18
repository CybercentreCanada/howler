"""Real-socket checks of read-timeout semantics, which mocked sessions cannot exercise."""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from howler.odm.models.config import AITriage
from howler.services import ai_service as transport

BODY = json.dumps({"choices": [{"message": {"content": "opinion"}}]}).encode()


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        stop = self.server.stop
        phase = self.server.phase
        if phase == "headers":
            stop.wait(5)
            return

        self.send_response(200)
        self.send_header("Content-Length", str(len(BODY)))
        self.end_headers()
        self.wfile.flush()
        if phase == "body":
            stop.wait(5)
            return

        # Total duration exceeds the 1s timeout, but every read receives data in time.
        for start in range(0, len(BODY), 10):
            self.wfile.write(BODY[start : start + 10])
            self.wfile.flush()
            if stop.wait(0.3):
                return

    def log_message(self, format: str, *args: object) -> None:
        pass


@pytest.fixture
def endpoint(request):
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    server.phase = request.param
    server.stop = threading.Event()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/chat"
    server.stop.set()
    server.shutdown()
    server.server_close()
    thread.join(timeout=1)


def generate(url):
    config = AITriage(enabled=True, endpoint=url, model="m", timeout_seconds=1)
    return transport.generate(config, "local-test-token", "prompt", {})


@pytest.mark.parametrize("endpoint", ["headers", "body"], indirect=True)
def test_inactive_provider_times_out(endpoint):
    started = time.monotonic()

    with pytest.raises(transport.AITransportError, match="timed out") as error:
        generate(endpoint)

    assert "local-test-token" not in str(error.value)
    assert 0.8 <= time.monotonic() - started < 3


@pytest.mark.parametrize("endpoint", ["trickle"], indirect=True)
def test_active_provider_can_exceed_read_timeout(endpoint):
    started = time.monotonic()

    assert generate(endpoint) == "opinion"
    assert time.monotonic() - started > 1
