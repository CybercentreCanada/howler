from unittest.mock import MagicMock, patch

import pytest
import werkzeug
from flask.app import Flask

# No clue why this is necessary
werkzeug.__version__ = "1.0.0"  # type: ignore


@pytest.fixture(scope="module")
def client():
    from tsx_user_tags.routes.healthz import healthz_api

    app = Flask("test_app")
    app.config.update(SECRET_KEY="test test", TESTING=True)  # noqa: S106
    app.register_blueprint(healthz_api)

    return app.test_client()


def test_plugin_alive(client):
    """Test liveness endpoint always returns 200."""
    assert client.get("/api/v1/tags/healthz/live").status_code == 200


def test_plugin_ready(client):
    """Test readiness endpoint returns 200 when datastore is available."""
    mock_ds = MagicMock()
    mock_ds.ds.ping.return_value = True

    with patch("howler.common.loader.datastore", return_value=mock_ds):
        assert client.get("/api/v1/tags/healthz/ready").status_code == 200


def test_plugin_ready_fails_when_datastore_unavailable(client):
    """Test readiness endpoint returns 503 when datastore ping fails."""
    mock_ds = MagicMock()
    mock_ds.ds.ping.return_value = False

    with patch("howler.common.loader.datastore", return_value=mock_ds):
        assert client.get("/api/v1/tags/healthz/ready").status_code == 503
