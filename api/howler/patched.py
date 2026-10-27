import signal

_signal = signal.signal

from gevent.monkey import patch_all

patch_all()

from howler.app import app  # noqa: E402
from howler.app import main as app_main  # noqa: E402
from howler.services import ai_triage_worker  # noqa: E402

__all__ = ["app"]


def main() -> None:
    """Run the patched Flask application without a second reloader process."""
    previous_sigterm = _signal(signal.SIGTERM, _terminate_cli_server)
    try:
        app_main(use_reloader=False)
    finally:
        ai_triage_worker.stop_workers(timeout=3.0)
        _signal(signal.SIGTERM, previous_sigterm)


def _terminate_cli_server(signum: int, _frame: object) -> None:
    """Let main unwind through worker cleanup on the supported CLI entrypoint."""
    raise SystemExit(128 + signum)


if __name__ == "__main__":
    main()
