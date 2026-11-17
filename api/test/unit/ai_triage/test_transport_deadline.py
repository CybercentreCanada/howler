import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import cast

import pytest
from gevent import sleep

from howler.odm.models.config import AITriage
from howler.services import ai_transport as transport


class SlowStreamServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, phase):
        super().__init__(("127.0.0.1", 0), SlowStreamHandler)
        self.phase = phase
        self.started = threading.Event()
        self.stop_stream = threading.Event()
        self.completed = threading.Event()
        self.sent_chunks = 0

    def finish_request(self, request, client_address):
        if self.phase == "tls":
            self.started.set()
            self.stop_stream.wait(5)
        else:
            super().finish_request(request, client_address)


class SlowStreamHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        server = cast(SlowStreamServer, self.server)
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        server.started.set()
        if server.phase == "headers":
            self.wfile.write(b"HTTP/1.1 200 OK\r\nX-Trickle: ")
            chunk, count = b"x", 100
        else:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", "1000000")
            self.end_headers()
            chunk, count = b"x" * 64, 1000000 // 64
        self.wfile.flush()

        try:
            for _ in range(count):
                if server.stop_stream.wait(0.05):
                    return
                self.wfile.write(chunk)
                self.wfile.flush()
                server.sent_chunks += 1
            if server.phase == "headers":
                self.wfile.write(b"\r\nContent-Length: 2\r\n\r\n{}")
                self.wfile.flush()
            server.completed.set()
        except OSError:
            return

    def log_message(self, format: str, *_args: object) -> None:
        return


@pytest.fixture
def slow_server(allow_local_http, phase):
    server = SlowStreamServer(phase)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    endpoint = f"{'https' if phase == 'tls' else 'http'}://127.0.0.1:{server.server_port}/slow-stream"
    allow_local_http(endpoint)
    try:
        yield server, endpoint
    finally:
        server.stop_stream.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)


@pytest.mark.parametrize("phase", ["body", "headers"])
def test_slow_response_is_aborted_at_absolute_deadline(slow_server, phase):
    server, endpoint = slow_server
    started_at = time.monotonic()
    with pytest.raises(transport.AITransportError, match="Provider exceeded its timeout") as error:
        transport.generate(
            AITriage(enabled=True, endpoint=endpoint, model="qa-model"),
            "local-test-token",
            "safe prompt",
            {},
            deadline=started_at + 1,
        )

    assert "local-test-token" not in str(error.value)
    assert server.started.is_set()
    assert 3 <= server.sent_chunks < 8192 // 64
    assert not server.completed.is_set()
    # Idle timeouts cannot stop these reads: headers take 5s, one body read 6.4s.
    assert 0.8 <= time.monotonic() - started_at < 3


@pytest.mark.parametrize("phase", ["dns", "tls"])
def test_connection_setup_is_included_in_absolute_deadline(slow_server, monkeypatch, phase):
    server, endpoint = slow_server
    resolve = transport.socket.getaddrinfo

    def slow_lookup(*args, **kwargs):
        sleep(0.8 if phase == "tls" else 5)
        return resolve(*args, **kwargs)

    monkeypatch.setattr(transport.socket, "getaddrinfo", slow_lookup)
    started_at = time.monotonic()
    with pytest.raises(transport.AITransportError, match="Provider exceeded its timeout"):
        transport.generate(
            AITriage(enabled=True, endpoint=endpoint, model="qa-model"),
            "local-test-token",
            "safe prompt",
            {},
            deadline=started_at + 1,
        )
    assert 0.8 <= time.monotonic() - started_at < 1.4
    assert server.started.is_set() == (phase == "tls")
