from gevent.monkey import patch_all

patch_all()

from howler.app import app  # noqa: E402
from howler.app import main as app_main  # noqa: E402

__all__ = ["app"]


def main() -> None:
    """Run the patched Flask application without a second reloader process."""
    app_main(use_reloader=False)


if __name__ == "__main__":
    main()
