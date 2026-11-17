import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import cast

import pytest

from howler.odm.models.config import AITriage
from howler.services import ai_service as transport


class ProviderServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, phase):
        super().__init__(("127.0.0.1", 0), ProviderHandler)
        self.phase = phase
        self.started = threading.Event()
        self.stop_stream = threading.Event()
        self.request_count = 0


class ProviderHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        server = cast(ProviderServer, self.server)
        server.request_count += 1
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        server.started.set()
        if server.phase == "headers":
            server.stop_stream.wait(5)
            return

        if server.phase in {"redirect", "error"}:
            self.send_response(302 if server.phase == "redirect" else 503)
            if server.phase == "redirect":
                self.send_header("Location", "/elsewhere")
            self.send_header("Content-Length", "1000000")
            self.end_headers()
            self.wfile.flush()
            server.stop_stream.wait(5)
            return

        content = "x" * 100_001 if server.phase == "large" else "opinion"
        body = json.dumps({"choices": [{"message": {"content": content}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.flush()
        if server.phase == "body":
            server.stop_stream.wait(5)
            return
        if server.phase == "large":
            self.wfile.write(body)
            return

        try:
            # More than the configured one-second timeout in total, but each
            # read receives data before its inactivity timeout expires.
            for start in range(0, len(body), 10):
                self.wfile.write(body[start : start + 10])
                self.wfile.flush()
                if server.stop_stream.wait(0.3):
                    return
        except OSError:
            return

    def log_message(self, format: str, *_args: object) -> None:
        return


@pytest.fixture
def provider_server(allow_local_http, phase):
    server = ProviderServer(phase)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    endpoint = f"http://127.0.0.1:{server.server_port}/slow-stream"
    allow_local_http(endpoint)
    try:
        yield server, endpoint
    finally:
        server.stop_stream.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)


def generate(endpoint):
    return transport.generate(
        AITriage(enabled=True, endpoint=endpoint, model="qa-model", timeout_seconds=1),
        "local-test-token",
        "safe prompt",
        {},
    )


@pytest.mark.parametrize("phase", ["headers", "body"])
def test_inactive_provider_times_out(provider_server, phase):
    server, endpoint = provider_server
    started_at = time.monotonic()
    with pytest.raises(transport.AITransportError, match="Provider response timed out") as error:
        generate(endpoint)
    assert "local-test-token" not in str(error.value)
    assert server.started.is_set()
    assert 0.8 <= time.monotonic() - started_at < 3


@pytest.mark.parametrize("phase", ["trickle"])
def test_active_provider_can_exceed_read_timeout(provider_server, phase):
    _server, endpoint = provider_server
    started_at = time.monotonic()
    assert generate(endpoint) == "opinion"
    assert time.monotonic() - started_at > 1


@pytest.mark.parametrize("phase", ["redirect"])
def test_redirect_is_rejected_without_waiting_for_its_body(provider_server, phase):
    server, endpoint = provider_server
    started_at = time.monotonic()
    with pytest.raises(transport.AITransportError, match="Provider returned HTTP 302"):
        generate(endpoint)
    assert server.started.is_set()
    assert time.monotonic() - started_at < 0.8


@pytest.mark.parametrize("phase", ["error"])
def test_provider_error_is_not_retried_or_buffered(provider_server, phase):
    server, endpoint = provider_server
    started_at = time.monotonic()
    with pytest.raises(transport.AITransportError, match="Provider returned HTTP 503"):
        generate(endpoint)
    assert server.request_count == 1
    assert time.monotonic() - started_at < 0.8


@pytest.mark.parametrize("phase", ["large"])
def test_response_larger_than_previous_limit_is_accepted(provider_server, phase):
    _server, endpoint = provider_server
    assert generate(endpoint) == "x" * 100_001
