"""Unit tests for the user notification endpoint."""

from unittest.mock import MagicMock, patch

import pytest
from flask import Flask, Response

from howler.common.exceptions import InvalidDataException, NotFoundException
from howler.odm.models.user import User


@pytest.fixture(scope="module")
def request_context():
    app = Flask("notification_endpoint_test")
    app.config.update(SECRET_KEY="test secret")
    return app


def _user() -> User:
    return User(
        {
            "uname": "authenticated-user",
            "name": "Authenticated User",
            "password": "__NO_PASSWORD__",
            "type": ["user"],
            "api_quota": 1000,
        }
    )


def _configure_auth(mock_auth_service, user: User, privileges: list[str] | None = None):
    mock_auth_service.bearer_auth = MagicMock(return_value=(user, privileges or ["R"]))


class TestGetUserNotificationsEndpoint:
    """Tests for GET /api/v2/notification/get/user."""

    @patch("howler.api.QUOTA_TRACKER")
    @patch("howler.security.login.QUOTA_TRACKER")
    @patch("howler.security.login.auth_service")
    @patch("howler.api.v2.notification.notification_service")
    def test_defaults_to_first_page_for_authenticated_user(
        self, mock_notification_service, mock_auth_service, mock_login_quota, _mock_api_quota, request_context: Flask
    ):
        _configure_auth(mock_auth_service, _user())
        mock_login_quota.begin.return_value = True
        mock_notification_service.get_user_notifications.return_value = {
            "items": [{"notification_id": "n-1"}],
            "offset": 0,
            "rows": 1,
            "total": 1,
        }

        with request_context.test_request_context(
            method="GET", path="/api/v2/notification/get/user", headers={"Authorization": "Bearer token"}
        ):
            from howler.api.v2.notification import get_user_notifications

            result: Response = get_user_notifications()

        assert result.status_code == 200
        assert result.get_json()["api_response"] == mock_notification_service.get_user_notifications.return_value
        mock_notification_service.get_user_notifications.assert_called_once_with(
            "authenticated-user", offset=0, rows=25
        )

    @patch("howler.api.QUOTA_TRACKER")
    @patch("howler.security.login.QUOTA_TRACKER")
    @patch("howler.security.login.auth_service")
    @patch("howler.api.v2.notification.notification_service")
    def test_parses_pagination(
        self, mock_notification_service, mock_auth_service, mock_login_quota, _mock_api_quota, request_context: Flask
    ):
        _configure_auth(mock_auth_service, _user())
        mock_login_quota.begin.return_value = True
        mock_notification_service.get_user_notifications.return_value = {
            "items": [],
            "offset": 10,
            "rows": 5,
            "total": 0,
        }

        with request_context.test_request_context(
            method="GET",
            path="/api/v2/notification/get/user",
            query_string={"offset": "10", "rows": "5"},
            headers={"Authorization": "Bearer token"},
        ):
            from howler.api.v2.notification import get_user_notifications

            result: Response = get_user_notifications()

        assert result.status_code == 200
        mock_notification_service.get_user_notifications.assert_called_once_with(
            "authenticated-user", offset=10, rows=5
        )

    @pytest.mark.parametrize(
        ("query_string", "error_fragment"),
        [
            ({"offset": "-1"}, "offset"),
            ({"offset": "abc"}, "offset"),
            ({"rows": "0"}, "rows"),
            ({"rows": "101"}, "rows"),
            ({"rows": "many"}, "rows"),
        ],
    )
    @patch("howler.api.QUOTA_TRACKER")
    @patch("howler.security.login.QUOTA_TRACKER")
    @patch("howler.security.login.auth_service")
    @patch("howler.api.v2.notification.notification_service")
    def test_invalid_pagination_returns_400(
        self,
        mock_notification_service,
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
            path="/api/v2/notification/get/user",
            query_string=query_string,
            headers={"Authorization": "Bearer token"},
        ):
            from howler.api.v2.notification import get_user_notifications

            result: Response = get_user_notifications()

        assert result.status_code == 400
        assert error_fragment in result.get_json()["api_error_message"]
        mock_notification_service.get_user_notifications.assert_not_called()

    @patch("howler.api.QUOTA_TRACKER")
    @patch("howler.security.login.QUOTA_TRACKER")
    @patch("howler.security.login.auth_service")
    @patch("howler.api.v2.notification.notification_service")
    def test_search_failure_returns_400(
        self, mock_notification_service, mock_auth_service, mock_login_quota, _mock_api_quota, request_context: Flask
    ):
        _configure_auth(mock_auth_service, _user())
        mock_login_quota.begin.return_value = True
        mock_notification_service.get_user_notifications.side_effect = InvalidDataException("bad search")

        with request_context.test_request_context(
            method="GET", path="/api/v2/notification/get/user", headers={"Authorization": "Bearer token"}
        ):
            from howler.api.v2.notification import get_user_notifications

            result: Response = get_user_notifications()

        assert result.status_code == 400

    @patch("howler.security.login.auth_service")
    def test_requires_authentication(self, mock_auth_service, request_context: Flask):
        with request_context.test_request_context(method="GET", path="/api/v2/notification/get/user"):
            from howler.api.v2.notification import get_user_notifications

            result: Response = get_user_notifications()

        assert result.status_code == 401
        mock_auth_service.bearer_auth.assert_not_called()


class TestMarkNotificationReadEndpoint:
    """Tests for POST /api/v2/notification/<id>/read."""

    @patch("howler.api.QUOTA_TRACKER")
    @patch("howler.security.login.QUOTA_TRACKER")
    @patch("howler.security.login.auth_service")
    @patch("howler.api.v2.notification.notification_service")
    def test_marks_notification_read(
        self, mock_notification_service, mock_auth_service, mock_login_quota, _mock_api_quota, request_context: Flask
    ):
        _configure_auth(mock_auth_service, _user(), ["R", "W"])
        mock_login_quota.begin.return_value = True
        mock_notification_service.mark_notification_read.return_value = {"notification_id": "n-1", "read": True}

        with request_context.test_request_context(
            method="POST", path="/api/v2/notification/n-1/read", headers={"Authorization": "Bearer token"}
        ):
            from howler.api.v2.notification import mark_notification_read

            result: Response = mark_notification_read(notification_id="n-1")

        assert result.status_code == 200
        assert result.get_json()["api_response"] == {"notification_id": "n-1", "read": True}
        mock_notification_service.mark_notification_read.assert_called_once_with("n-1", "authenticated-user")

    @pytest.mark.parametrize(
        ("error", "status_code"),
        [(NotFoundException("missing"), 404), (InvalidDataException("failed"), 400)],
    )
    @patch("howler.api.QUOTA_TRACKER")
    @patch("howler.security.login.QUOTA_TRACKER")
    @patch("howler.security.login.auth_service")
    @patch("howler.api.v2.notification.notification_service")
    def test_maps_service_errors(
        self,
        mock_notification_service,
        mock_auth_service,
        mock_login_quota,
        _mock_api_quota,
        request_context: Flask,
        error: Exception,
        status_code: int,
    ):
        _configure_auth(mock_auth_service, _user(), ["R", "W"])
        mock_login_quota.begin.return_value = True
        mock_notification_service.mark_notification_read.side_effect = error

        with request_context.test_request_context(
            method="POST", path="/api/v2/notification/n-1/read", headers={"Authorization": "Bearer token"}
        ):
            from howler.api.v2.notification import mark_notification_read

            result: Response = mark_notification_read(notification_id="n-1")

        assert result.status_code == status_code


class TestDeleteNotificationEndpoint:
    """Tests for DELETE /api/v2/notification/<id>."""

    @patch("howler.api.QUOTA_TRACKER")
    @patch("howler.security.login.QUOTA_TRACKER")
    @patch("howler.security.login.auth_service")
    @patch("howler.api.v2.notification.notification_service")
    def test_deletes_notification(
        self, mock_notification_service, mock_auth_service, mock_login_quota, _mock_api_quota, request_context: Flask
    ):
        _configure_auth(mock_auth_service, _user(), ["R", "W"])
        mock_login_quota.begin.return_value = True

        with request_context.test_request_context(
            method="DELETE", path="/api/v2/notification/n-1", headers={"Authorization": "Bearer token"}
        ):
            from howler.api.v2.notification import delete_notification

            result: Response = delete_notification(notification_id="n-1")

        assert result.status_code == 204
        mock_notification_service.delete_notification.assert_called_once_with("n-1", "authenticated-user")

    @patch("howler.api.QUOTA_TRACKER")
    @patch("howler.security.login.QUOTA_TRACKER")
    @patch("howler.security.login.auth_service")
    @patch("howler.api.v2.notification.notification_service")
    def test_missing_notification_returns_404(
        self, mock_notification_service, mock_auth_service, mock_login_quota, _mock_api_quota, request_context: Flask
    ):
        _configure_auth(mock_auth_service, _user(), ["R", "W"])
        mock_login_quota.begin.return_value = True
        mock_notification_service.delete_notification.side_effect = NotFoundException("missing")

        with request_context.test_request_context(
            method="DELETE", path="/api/v2/notification/n-1", headers={"Authorization": "Bearer token"}
        ):
            from howler.api.v2.notification import delete_notification

            result: Response = delete_notification(notification_id="n-1")

        assert result.status_code == 404

    @patch("howler.api.QUOTA_TRACKER")
    @patch("howler.security.login.QUOTA_TRACKER")
    @patch("howler.security.login.auth_service")
    @patch("howler.api.v2.notification.notification_service")
    def test_requires_write_privilege(
        self, mock_notification_service, mock_auth_service, mock_login_quota, _mock_api_quota, request_context: Flask
    ):
        _configure_auth(mock_auth_service, _user(), ["R"])
        mock_login_quota.begin.return_value = True

        with request_context.test_request_context(
            method="DELETE", path="/api/v2/notification/n-1", headers={"Authorization": "Bearer token"}
        ):
            from howler.api.v2.notification import delete_notification

            result: Response = delete_notification(notification_id="n-1")

        assert result.status_code == 403
        mock_notification_service.delete_notification.assert_not_called()
