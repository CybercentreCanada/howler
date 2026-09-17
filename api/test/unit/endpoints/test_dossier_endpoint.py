import uuid
from typing import cast
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask, Response

from howler.odm import Model
from howler.odm.models.user import User
from howler.odm.randomizer import random_model_obj


@pytest.fixture(scope="module")
def request_context():
    app = Flask("test_app")
    app.config.update(SECRET_KEY="test test")
    return app


def _build_user(user_type: list[str] | None = None) -> User:
    user_data: User = random_model_obj(cast(Model, User))
    user_data.type = user_type or ["admin", "user"]
    user_data.uname = f"test_{uuid.uuid4().hex[:12]}"
    user_data.api_quota = 1000
    return user_data


def _mock_auth(mock_auth_service, user, priv=None):
    if priv is None:
        priv = ["R", "W", "E"]

    mock_auth_service.bearer_auth = MagicMock(return_value=(user, priv))


@patch("howler.api.v1.dossier.dossier_service")
@patch("howler.api.QUOTA_TRACKER")
@patch("howler.security.login.QUOTA_TRACKER")
@patch("howler.security.login.auth_service")
def test_get_pivot_groups_returns_service_results_for_authenticated_user(
    mock_auth_service, mock_login_quota_tracker, mock_api_quota_tracker, mock_dossier_service, request_context: Flask
):
    user = _build_user()
    _mock_auth(mock_auth_service, user)
    mock_login_quota_tracker.begin.return_value = True
    mock_dossier_service.get_pivot_groups.return_value = ["network/dns"]

    with request_context.test_request_context(
        "/api/v1/dossier/groups?prefix=network/",
        headers={"Authorization": "Bearer .", "Content-Type": "application/json"},
    ):
        from howler.api.v1.dossier import get_pivot_groups

        result: Response = get_pivot_groups()

        assert result.status_code == 200
        assert result.get_json()["api_response"] == ["network/dns"]
        mock_dossier_service.get_pivot_groups.assert_called_once_with("network/", username=user.uname)
        mock_login_quota_tracker.begin.assert_called_once_with(user.uname, user.api_quota)
        mock_api_quota_tracker.end.assert_called_once_with(user.uname)
