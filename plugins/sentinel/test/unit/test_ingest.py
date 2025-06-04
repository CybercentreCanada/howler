import json
import logging
from pathlib import Path

import pytest
import werkzeug
from flask.app import Flask
from howler.common.loader import datastore

# No clue why this is necessary
werkzeug.__version__ = "1.0.0"  # type: ignore

with (Path(__file__).parent / "sentinel.json").open() as _alert:
    SENTINEL_ALERT = json.load(_alert)


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
            "/api/v1/sentinel/ingest", json=SENTINEL_ALERT, headers={"Authorization": "Basic test_key"}
        )

    assert "tes...key" in caplog.text

    assert result.json["api_response"]["bundle_size"] == 1
    assert len(result.json["api_response"]["individual_hit_ids"]) == 1

    assert datastore().hit.exists(result.json["api_response"]["bundle_hit_id"])
    assert (
        datastore().hit.get(result.json["api_response"]["bundle_hit_id"], as_obj=True).howler.hits
        == result.json["api_response"]["individual_hit_ids"]
    )
    for _id in result.json["api_response"]["individual_hit_ids"]:
        assert datastore().hit.exists(_id)
