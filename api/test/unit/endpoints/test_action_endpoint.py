from unittest.mock import patch

import pytest
from flask import Flask, Response

from howler.odm.models.action import Action


@pytest.fixture(scope="module")
def request_context():
    app = Flask("test_action_endpoint")
    app.config.update(SECRET_KEY="test test", TESTING=True)
    return app


def _build_action() -> Action:
    return Action(
        {
            "action_id": "11111111-1111-4111-8111-111111111111",
            "owner": "test",
            "name": "Test action",
            "query": "howler.id:*",
            "triggers": [],
            "operations": [],
        }
    )


def _configure_auth(mock_auth_service, mock_quota_tracker):
    mock_auth_service.bearer_auth.return_value = (
        {"uname": "test", "type": ["admin"], "api_quota": 1000},
        ["R", "E"],
    )
    mock_quota_tracker.begin.return_value = True


@patch("howler.security.login.audit")
@patch("howler.security.login.QUOTA_TRACKER")
@patch("howler.security.login.auth_service")
@patch("howler.services.action_service.datastore")
def test_get_action_success(
    mock_datastore,
    mock_auth_service,
    mock_quota_tracker,
    mock_audit,
    request_context: Flask,
):
    action = _build_action()
    mock_datastore.return_value.action.get_if_exists.return_value = (action, "v1")
    _configure_auth(mock_auth_service, mock_quota_tracker)

    with request_context.test_request_context(
        "/api/v1/action/11111111-1111-4111-8111-111111111111",
        headers={"Authorization": "Bearer ."},
    ):
        from howler.api.v1.action import get_action

        result: Response = get_action(id="11111111-1111-4111-8111-111111111111")

    assert result.status_code == 200
    assert result.headers["ETag"] == "v1"
    assert result.get_json()["api_response"]["action_id"] == action.action_id
    mock_datastore.return_value.action.get_if_exists.assert_called_once_with(
        key=action.action_id,
        as_obj=True,
        version=True,
    )


@patch("howler.security.login.audit")
@patch("howler.security.login.QUOTA_TRACKER")
@patch("howler.security.login.auth_service")
@patch("howler.services.action_service.datastore")
def test_get_action_not_found(
    mock_datastore,
    mock_auth_service,
    mock_quota_tracker,
    mock_audit,
    request_context: Flask,
):
    mock_datastore.return_value.action.get_if_exists.return_value = (None, "create")
    _configure_auth(mock_auth_service, mock_quota_tracker)

    with request_context.test_request_context(
        "/api/v1/action/missing",
        headers={"Authorization": "Bearer ."},
    ):
        from howler.api.v1.action import get_action

        result: Response = get_action(id="missing")

    assert result.status_code == 404
    assert result.get_json()["api_error_message"] == "The specified action does not exist"
