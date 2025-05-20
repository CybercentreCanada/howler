import json

import pytest
from authlib.integrations.flask_client import OAuth
from flask import Flask
from flask import Response as FlaskResponse
from mock import patch
from utils.oauth_credentials import get_token

from howler.config import cache


@pytest.fixture(scope="module", autouse=True)
def request_context():
    app = Flask("test_app")
    token = get_token()

    app.config.update(SECRET_KEY="test test", TESTING=True)

    OAuth().init_app(app)
    cache.init_app(app)
    with app.test_request_context(
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    ):
        yield app


@patch("howler.security.audit")
@patch("howler.services.notebook_service.get_user_envs", return_value={"test": "test"})
def test_get_user_envs(get_user_envs, audit):
    from howler.api.v1.notebook import get_user_environments

    result: FlaskResponse = get_user_environments()

    get_user_envs.assert_called_once()

    assert result.status_code == 200
    assert json.loads(result.data.decode())["api_response"]["envs"]["test"] == "test"


@patch("howler.security.audit")
def test_get_notebook_missing_link(audit, request_context):
    with patch(
        "howler.api.v1.notebook.request",
    ) as request:
        request.json = {}

        from howler.api.v1.notebook import get_notebook

        result = get_notebook()

        assert result.status_code == 400
        assert json.loads(result.data.decode())["api_error_message"] == "You must provide a link"


@patch("howler.security.audit")
def test_get_notebook_missing_analytic(audit, request_context):
    with patch(
        "howler.api.v1.notebook.request",
    ) as request:
        request.json = {"link": "nbgallery"}

        from howler.api.v1.notebook import get_notebook

        result = get_notebook()

        assert result.status_code == 400
        assert json.loads(result.data.decode())["api_error_message"] == "You must provide an analytic"


@patch("howler.security.audit")
@patch(
    "howler.api.v1.notebook.notebook_service.get_nb_information",
    return_value=({"nb": "nb"}, "nb"),
)
def test_get_notebook_missing_analytic_with_analytic(audit, get_nb_information, request_context):
    with patch(
        "howler.api.v1.notebook.request",
    ) as request:
        request.json = {"link": "nbgallery", "analytic": "analytic_id"}

        from howler.api.v1.notebook import get_notebook

        result = get_notebook()

        assert result.status_code == 200
        assert json.loads(result.data.decode())["api_response"]["name"] == "nb"
