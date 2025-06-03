import pytest
from flask import Flask
from flask import Response as FlaskResponse

from howler.api.v1.configs import configs


@pytest.fixture(scope="module")
def request_context():
    app = Flask("test_app")

    app.config.update(SECRET_KEY="test test")

    return app


def test_configs(request_context):
    with request_context.test_request_context():
        response: FlaskResponse = configs()

        assert response.status_code == 200

        assert "configuration" in response.get_json()["api_response"]

        assert "mapping" in response.get_json()["api_response"]["configuration"]
