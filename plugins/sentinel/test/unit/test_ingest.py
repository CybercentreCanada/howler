import logging

import pytest
import werkzeug
from flask.app import Flask

# No clue why this is necessary
werkzeug.__version__ = "1.0.0"  # type: ignore


@pytest.fixture(scope="module")
def client():
    from sentinel.routes.ingest import sentinel_api

    app = Flask("test_app")

    app.config.update(SECRET_KEY="test test", TESTING=True)

    app.register_blueprint(sentinel_api)

    return app.test_client()


def test_ingest_endpoint(client, caplog):
    with caplog.at_level(logging.INFO):
        result = client.post(
            "/api/v1/sentinel/ingest", json={"test": True}, headers={"Authorization": "Basic test_key"}
        )

    assert "tes...key" in caplog.text
    assert "{'test': True}" in caplog.text

    assert result.json["api_response"] == {"success": True}
