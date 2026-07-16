from unittest.mock import patch

import pytest
from flask import Flask
from flask import Response as FlaskResponse

from howler.api import ok


@pytest.fixture(scope="module")
def request_context():
    app = Flask("test_app")
    app.config.update(SECRET_KEY="test test")

    return app


def _auth_user():
    return {"uname": "admin", "type": ["admin", "user"], "api_quota": 1000}


@patch("howler.security.auth_service.basic_auth")
@patch("howler.security.audit")
def test_action_multi_permission_endpoint_exists(audit, mock_basic_auth, request_context: Flask):
    mock_basic_auth.return_value = (_auth_user(), ["R", "W", "E"])

    with request_context.test_request_context(
        headers={"Authorization": "Basic potato", "Content-Type": "application/json"},
        json={"privilege": "members", "user_id": ["user1", "user2"]},
    ):
        from howler.api.v1.action import give_multi_privilege

        with patch("howler.api.v1.action.permission_helper.give_multi_privilege", return_value=ok({"exists": True})):
            response: FlaskResponse = give_multi_privilege("action-1")

    assert response.status_code == 200
    assert response.get_json()["api_response"]["exists"] is True


@patch("howler.security.auth_service.basic_auth")
@patch("howler.security.audit")
def test_dossier_multi_permission_endpoint_exists(audit, mock_basic_auth, request_context: Flask):
    mock_basic_auth.return_value = (_auth_user(), ["R", "W", "E"])

    with request_context.test_request_context(
        headers={"Authorization": "Basic potato", "Content-Type": "application/json"},
        json={"privilege": "members", "user_id": ["user1", "user2"]},
    ):
        from howler.api.v1.dossier import give_multi_privilege

        with patch("howler.api.v1.dossier.permission_helper.give_multi_privilege", return_value=ok({"exists": True})):
            response: FlaskResponse = give_multi_privilege("dossier-1")

    assert response.status_code == 200
    assert response.get_json()["api_response"]["exists"] is True


@patch("howler.security.auth_service.basic_auth")
@patch("howler.security.audit")
def test_view_multi_permission_endpoint_exists(audit, mock_basic_auth, request_context: Flask):
    mock_basic_auth.return_value = (_auth_user(), ["R", "W", "E"])

    with request_context.test_request_context(
        headers={"Authorization": "Basic potato", "Content-Type": "application/json"},
        json={"privilege": "members", "user_id": ["user1", "user2"]},
    ):
        from howler.api.v1.view import give_multi_privilege

        with patch("howler.api.v1.view.permission_helper.give_multi_privilege", return_value=ok({"exists": True})):
            response: FlaskResponse = give_multi_privilege("view-1")

    assert response.status_code == 200
    assert response.get_json()["api_response"]["exists"] is True
