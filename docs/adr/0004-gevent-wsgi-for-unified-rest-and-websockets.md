---
status: accepted
---

# Monkey-patch WSGI workers with gevent for unified REST and WebSockets

Howler serves both synchronous Flask REST endpoints and long-lived WebSocket connections (`api/howler/api/socket.py`) from the same Gunicorn/Flask worker pool by invoking `gevent.monkey.patch_all()` at process entry (`api/howler/patched.py`). This avoids deploying and routing a separate WebSocket service while allowing a single worker process to multiplex many open client sockets.

## Consequences

- All Python dependencies and background threads running in the API process must be compatible with `gevent` monkey-patching, and `howler.patched` must remain the WSGI entrypoint before socket/HTTP libraries are imported.
