import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import cast
from unittest.mock import Mock

import pytest

from howler.odm.models.config import AITriage
from howler.services import ai_transport as transport


class SlowStreamServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self):
        super().__init__(("127.0.0.1", 0), SlowStreamHandler)
        self.started = threading.Event()
        self.stop_stream = threading.Event()
        self.completed = threading.Event()
        self.sent_chunks = 0
        self.body_bytes = 0


class SlowStreamHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        server = cast(SlowStreamServer, self.server)
        server.started.set()
        server.body_bytes = 1_000_000
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(server.body_bytes))
        self.end_headers()

        for _ in range(server.body_bytes // 64):
            if server.stop_stream.wait(0.05):
                return
            try:
                self.wfile.write(b"x" * 64)
                self.wfile.flush()
            except OSError:
                return
            server.sent_chunks += 1
        server.completed.set()

    def log_message(self, format: str, *_args: object) -> None:
        return


def test_slow_stream_is_aborted_at_absolute_deadline(allow_local_http):
    server = SlowStreamServer()
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    endpoint = f"http://127.0.0.1:{server.server_port}/slow-stream"
    allow_local_http(endpoint)

    deadline = time.monotonic() + 1.0
    started_at = time.monotonic()
    try:
        with pytest.raises(transport.AITransportError, match="Provider exceeded its timeout") as error:
            transport.generate(
                AITriage(
                    enabled=True,
                    endpoint=endpoint,
                    model="qa-model",
                    headers={},
                ),
                "local-test-token",
                "Conservative system prompt",
                {"event": "alert"},
                deadline=deadline,
            )

        elapsed = time.monotonic() - started_at
        assert "local-test-token" not in str(error.value)
        assert server.started.is_set()
        assert server.sent_chunks >= 3
        assert server.sent_chunks * 64 < 8192
        assert not server.completed.is_set()
        # A non-aborting read waits for 8192 bytes (about 6.4 seconds at this
        # cadence), while the deadline watchdog should wake it well before 3s.
        assert 0.8 <= elapsed < 3.0
    finally:
        server.stop_stream.set()
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=1)


def test_watchdog_ignores_already_released_response_race(monkeypatch):
    response = Mock()
    response.raw.shutdown.side_effect = RuntimeError("response was already released")
    deadline_reached = threading.Event()
    thread_errors = []
    monkeypatch.setattr(threading, "excepthook", thread_errors.append)

    cancelled, watchdog = transport._start_deadline_watchdog(response, time.monotonic() - 1, deadline_reached)
    watchdog.join(timeout=1)
    cancelled.set()

    assert not watchdog.is_alive()
    assert deadline_reached.is_set()
    assert thread_errors == []
    response.raw.shutdown.assert_called_once_with()
