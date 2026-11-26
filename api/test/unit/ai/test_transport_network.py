"""Real-socket checks of read-timeout semantics, which mocked sessions cannot exercise."""

import gzip
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from howler.odm.models.config import AIConfig
from howler.services import ai_service as transport

BODY = json.dumps({"choices": [{"message": {"content": "opinion"}}]}).encode()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        stop = self.server.stop
        phase = self.server.phase
        if phase == "headers":
            stop.wait(5)
            return

        self.send_response(200)
        if phase == "oversized":
            oversized_body = json.dumps(
                {"choices": [{"message": {"content": "x" * 1_000_000}}]}, separators=(",", ":")
            ).encode("utf-8")
            compressed_body = gzip.compress(oversized_body)
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            for start in range(0, len(compressed_body), 512):
                chunk = compressed_body[start : start + 512]
                self.wfile.write(f"{len(chunk):X}\r\n".encode("ascii") + chunk + b"\r\n")
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()
            return

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
    config = AIConfig(enabled=True, endpoint=url, model="m", timeout_seconds=1)
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


@pytest.mark.parametrize("endpoint", ["oversized"], indirect=True)
def test_compressed_chunked_response_is_limited_after_decompression(endpoint):
    with pytest.raises(transport.AITransportError, match="response exceeded the size limit"):
        generate(endpoint)
