"""Unit tests for the task search endpoint."""

from unittest.mock import MagicMock, patch

import pytest
from flask import Flask, Response

from howler.odm.models.user import User


@pytest.fixture(scope="module")
def request_context():
    app = Flask("task_endpoint_test")
    app.config.update(SECRET_KEY="test secret")
    return app


def _user(access_control: str | None = "classification:UNRESTRICTED") -> User:
    return User(
        {
            "uname": "authenticated-user",
            "name": "Authenticated User",
            "password": "__NO_PASSWORD__",
            "type": ["user"],
            "api_quota": 1000,
            "access_control": access_control,
        }
    )


def _configure_auth(mock_auth_service, user: User):
    mock_auth_service.bearer_auth = MagicMock(return_value=(user, ["R"]))


class TestTaskSearchEndpoint:
    """Tests for GET /api/v2/task/search."""

    @patch("howler.api.QUOTA_TRACKER")
    @patch("howler.security.login.QUOTA_TRACKER")
    @patch("howler.security.login.auth_service")
    @patch("howler.api.v2.task.task_service")
    def test_defaults_and_standard_response_envelope(
        self,
        mock_task_service,
        mock_auth_service,
        mock_login_quota,
        mock_api_quota,
        request_context: Flask,
    ):
        user = _user()
        _configure_auth(mock_auth_service, user)
        mock_login_quota.begin.return_value = True
        mock_task_service.search_tasks.return_value = {
            "items": [{"task": {"id": "task-1"}, "case": {"case_id": "case-1"}}],
            "offset": 0,
            "rows": 25,
            "has_more": False,
        }

        with request_context.test_request_context(
            method="GET", path="/api/v2/task/search", headers={"Authorization": "Bearer token"}
        ):
            from howler.api.v2.task import search_tasks

            result: Response = search_tasks()

        assert result.status_code == 200
        assert result.get_json()["api_response"] == mock_task_service.search_tasks.return_value
        mock_task_service.search_tasks.assert_called_once_with(user, offset=0, rows=25, task_filter="incomplete")
        mock_api_quota.end.assert_called_once_with("authenticated-user")

    @patch("howler.api.QUOTA_TRACKER")
    @patch("howler.security.login.QUOTA_TRACKER")
    @patch("howler.security.login.auth_service")
    @patch("howler.api.v2.task.task_service")
    def test_parses_explicit_pagination_and_filter(
        self, mock_task_service, mock_auth_service, mock_login_quota, _mock_api_quota, request_context: Flask
    ):
        user = _user()
        _configure_auth(mock_auth_service, user)
        mock_login_quota.begin.return_value = True
        mock_task_service.search_tasks.return_value = {"items": [], "offset": 4, "rows": 17, "has_more": False}

        with request_context.test_request_context(
            method="GET",
            path="/api/v2/task/search",
            query_string={"offset": "4", "rows": "17", "filter": "complete"},
            headers={"Authorization": "Bearer token"},
        ):
            from howler.api.v2.task import search_tasks

            result: Response = search_tasks()

        assert result.status_code == 200
        mock_task_service.search_tasks.assert_called_once_with(user, offset=4, rows=17, task_filter="complete")

    @pytest.mark.parametrize(
        ("query_string", "error_fragment"),
        [
            ({"offset": "-1"}, "offset"),
            ({"offset": "invalid"}, "offset"),
            ({"rows": "0"}, "rows"),
            ({"rows": "101"}, "rows"),
            ({"rows": "many"}, "rows"),
            ({"filter": "pending"}, "filter"),
        ],
    )
    @patch("howler.api.QUOTA_TRACKER")
    @patch("howler.security.login.QUOTA_TRACKER")
    @patch("howler.security.login.auth_service")
    @patch("howler.api.v2.task.task_service")
    def test_invalid_query_parameters_return_400(
        self,
        mock_task_service,
        mock_auth_service,
        mock_login_quota,
        _mock_api_quota,
        request_context: Flask,
        query_string: dict[str, str],
        error_fragment: str,
    ):
        _configure_auth(mock_auth_service, _user())
        mock_login_quota.begin.return_value = True

        with request_context.test_request_context(
            method="GET",
            path="/api/v2/task/search",
            query_string=query_string,
            headers={"Authorization": "Bearer token"},
        ):
            from howler.api.v2.task import search_tasks

            result: Response = search_tasks()

        assert result.status_code == 400
        assert error_fragment in result.get_json()["api_error_message"]
        mock_task_service.search_tasks.assert_not_called()

    @patch("howler.security.login.auth_service")
    def test_requires_authentication(self, mock_auth_service, request_context: Flask):
        with request_context.test_request_context(method="GET", path="/api/v2/task/search"):
            from howler.api.v2.task import search_tasks

            result: Response = search_tasks()

        assert result.status_code == 401
        mock_auth_service.bearer_auth.assert_not_called()

    @patch("howler.api.QUOTA_TRACKER")
    @patch("howler.security.login.QUOTA_TRACKER")
    @patch("howler.security.login.auth_service")
    @patch("howler.api.v2.task.task_service")
    def test_missing_access_control_fails_closed(
        self, mock_task_service, mock_auth_service, mock_login_quota, _mock_api_quota, request_context: Flask
    ):
        user = _user(access_control=None)
        _configure_auth(mock_auth_service, user)
        mock_login_quota.begin.return_value = True
        from howler.common.exceptions import ForbiddenException

        mock_task_service.search_tasks.side_effect = ForbiddenException("Case access controls are unavailable.")

        with request_context.test_request_context(
            method="GET", path="/api/v2/task/search", headers={"Authorization": "Bearer token"}
        ):
            from howler.api.v2.task import search_tasks

            result: Response = search_tasks()

        assert result.status_code == 403
        mock_task_service.search_tasks.assert_called_once_with(user, offset=0, rows=25, task_filter="incomplete")
