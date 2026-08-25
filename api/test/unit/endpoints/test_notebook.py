import json

import pytest
from authlib.integrations.flask_client import OAuth
from flask import Flask
from flask import Response as FlaskResponse
from mock import MagicMock, patch

from howler.config import cache


@pytest.fixture(scope="module", autouse=True)
def request_context():
    app = Flask("test_app")

    app.config.update(SECRET_KEY="test test", TESTING=True)

    OAuth().init_app(app)
    cache.init_app(app)
    with app.test_request_context(
        headers={
            "Authorization": "Bearer .",
            "Content-Type": "application/json",
        },
    ):
        yield app


@pytest.fixture(autouse=True)
def mock_auth_service():
    with patch("howler.security.login.auth_service") as auth_service:
        auth_service.bearer_auth = MagicMock(
            return_value=(
                {"uname": "test", "type": ["user"], "api_quota": 1000},
                ["R"],
            )
        )
        yield auth_service


@patch("howler.security.login.audit")
@patch("howler.services.notebook_service.get_user_envs", return_value={"test": "test"})
def test_get_user_envs(get_user_envs, audit):
    from howler.api.v1.notebook import get_user_environments

    result: FlaskResponse = get_user_environments()

    get_user_envs.assert_called_once()

    assert result.status_code == 200
    assert json.loads(result.data.decode())["api_response"]["envs"]["test"] == "test"


@patch("howler.security.login.audit")
def test_get_notebook_missing_link(audit, request_context):
    with patch(
        "howler.api.v1.notebook.request",
    ) as request:
        request.json = {}

        from howler.api.v1.notebook import get_notebook

        result = get_notebook()

        assert result.status_code == 400
        assert json.loads(result.data.decode())["api_error_message"] == "You must provide a link"


@patch("howler.security.login.audit")
def test_get_notebook_missing_analytic(audit, request_context):
    with patch(
        "howler.api.v1.notebook.request",
    ) as request:
        request.json = {"link": "nbgallery"}

        from howler.api.v1.notebook import get_notebook

        result = get_notebook()

        assert result.status_code == 400
        assert json.loads(result.data.decode())["api_error_message"] == "You must provide an analytic"


@patch("howler.security.login.audit")
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
