"""Tests for tsx_user_status routes."""

import functools
import json
from unittest.mock import MagicMock, patch

import pytest
import werkzeug
from flask.app import Flask

from tsx_user_status.services.user_status_service import UNSET

# Flask's test client reads `werkzeug.__version__`; provide a fallback only
# when the installed Werkzeug package does not expose that attribute.
if not hasattr(werkzeug, "__version__"):
    werkzeug.__version__ = "1.0.0"  # type: ignore[attr-defined]


TEST_USER = {"uname": "test_user", "name": "Test User"}


def mock_api_login(*args, **kwargs):
    """Mock api_login decorator that injects TEST_USER."""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*fargs, **fkwargs):
            fkwargs["user"] = TEST_USER
            return func(*fargs, **fkwargs)

        return wrapper

    return decorator


class TestHealthzRoutes:
    """Tests for healthz endpoints."""

    def test_live_returns_200(self):
        """Verify /healthz/live returns 200 OK."""
        from tsx_user_status.routes.healthz import healthz_api

        app = Flask("test_app")
        app.config.update(SECRET_KEY="test test", TESTING=True)  # noqa: S106
        app.register_blueprint(healthz_api)

        client = app.test_client()
        assert client.get("/api/v1/status/healthz/live").status_code == 200

    @patch("tsx_user_status.routes.healthz._check_schedules_blob", return_value=[])
    @patch("tsx_user_status.routes.healthz.howler_config")
    def test_ready_returns_200_when_redis_healthy(self, mock_config, _mock_schedules):
        """Verify /healthz/ready returns 200 when Redis and schedules are healthy."""
        from tsx_user_status.routes.healthz import healthz_api

        mock_config.redis_persistent.ping.return_value = True

        app = Flask("test_app")
        app.config.update(SECRET_KEY="test test", TESTING=True)  # noqa: S106
        app.register_blueprint(healthz_api)

        client = app.test_client()
        response = client.get("/api/v1/status/healthz/ready")
        assert response.status_code == 200

    @patch("tsx_user_status.routes.healthz._check_schedules_blob", return_value=[])
    @patch("tsx_user_status.routes.healthz.howler_config")
    def test_ready_returns_503_when_redis_unhealthy(self, mock_config, _mock_schedules):
        """Verify /healthz/ready returns 503 when Redis is down."""
        from redis import ConnectionError

        from tsx_user_status.routes.healthz import healthz_api

        mock_config.redis_persistent.ping.side_effect = ConnectionError("Connection refused")

        app = Flask("test_app")
        app.config.update(SECRET_KEY="test test", TESTING=True)  # noqa: S106
        app.register_blueprint(healthz_api)

        client = app.test_client()
        response = client.get("/api/v1/status/healthz/ready")
        assert response.status_code == 503

    @patch("tsx_user_status.routes.healthz._check_schedules_blob", return_value=["Schedules blob is empty"])
    @patch("tsx_user_status.routes.healthz.howler_config")
    def test_ready_returns_503_when_schedules_unhealthy(self, mock_config, _mock_schedules):
        """Verify /healthz/ready returns 503 when the schedules blob is unhealthy."""
        from tsx_user_status.routes.healthz import healthz_api

        mock_config.redis_persistent.ping.return_value = True

        app = Flask("test_app")
        app.config.update(SECRET_KEY="test test", TESTING=True)  # noqa: S106
        app.register_blueprint(healthz_api)

        client = app.test_client()
        response = client.get("/api/v1/status/healthz/ready")
        assert response.status_code == 503


@pytest.fixture
def user_status_app():
    """Create Flask app with mocked user_status routes."""
    # Patch api_login before importing the module
    with patch("howler.security.api_login", mock_api_login):
        # Clear cached module to force reimport with patched decorator
        import sys

        if "tsx_user_status.routes.user_status" in sys.modules:
            del sys.modules["tsx_user_status.routes.user_status"]

        from tsx_user_status.routes.user_status import status_api

        app = Flask("test_app")
        app.config.update(SECRET_KEY="test", TESTING=True)  # noqa: S106
        app.register_blueprint(status_api)
        yield app


class TestUserStatusRoutes:
    """Tests for user status endpoints."""

    @patch("howler.common.loader.datastore")
    @patch("tsx_user_status.config.status_service")
    def test_get_user_state(self, mock_service, mock_ds_func, user_status_app):
        """Verify GET /users/<uname> returns status, schedule, and team."""
        mock_ds = MagicMock()
        mock_ds.user.get.return_value = {"uname": "test_user", "name": "Test User"}
        mock_ds_func.return_value = mock_ds
        mock_service.get_status.return_value = "available"
        mock_service.get_shift.return_value = {"team": "MS", "schedule": "Day 7-15"}

        client = user_status_app.test_client()
        response = client.get("/api/v1/status/users/test_user")

        assert response.status_code == 200
        data = response.get_json()
        assert data["api_response"]["uname"] == "test_user"
        assert data["api_response"]["name"] == "Test User"
        assert data["api_response"]["status"] == "available"
        assert data["api_response"]["schedule"] == "Day 7-15"
        assert data["api_response"]["team"] == "MS"
        mock_service.get_status.assert_called_once_with("test_user")
        mock_service.get_shift.assert_called_once_with("test_user")

    @patch("howler.common.loader.datastore")
    @patch("tsx_user_status.config.status_service")
    def test_get_nonexistent_user_returns_404(self, mock_service, mock_ds_func, user_status_app):
        """Verify GET /users/<uname> returns 404 for unknown user."""
        mock_ds = MagicMock()
        mock_ds.user.get.return_value = None
        mock_ds_func.return_value = mock_ds

        client = user_status_app.test_client()
        response = client.get("/api/v1/status/users/ghost")

        assert response.status_code == 404

    @patch("howler.common.loader.datastore")
    @patch("tsx_user_status.config.status_service")
    @pytest.mark.parametrize(
        ("body", "expected"),
        [
            ({"status": "available"}, {"status": "available", "schedule": UNSET, "team": UNSET}),
            ({"schedule": "Day 7-15"}, {"status": UNSET, "schedule": "Day 7-15", "team": UNSET}),
            ({"team": "MS"}, {"status": UNSET, "schedule": UNSET, "team": "MS"}),
            (
                {"status": "available", "schedule": "Day 7-15", "team": "MS"},
                {"status": "available", "schedule": "Day 7-15", "team": "MS"},
            ),
            ({"status": None, "schedule": None, "team": None}, {"status": None, "schedule": None, "team": None}),
            ({"schedule": None}, {"status": UNSET, "schedule": None, "team": UNSET}),
        ],
    )
    def test_patch_maps_body_to_apply_patch(self, mock_service, mock_ds_func, user_status_app, body, expected):
        """Present fields map to apply_patch kwargs; omitted fields are UNSET."""
        mock_ds = MagicMock()
        mock_ds.user.get.return_value = {"uname": "test_user", "name": "Test User"}
        mock_ds_func.return_value = mock_ds
        mock_service.get_status.return_value = None
        mock_service.get_shift.return_value = None

        client = user_status_app.test_client()
        response = client.patch(
            "/api/v1/status/users/test_user",
            data=json.dumps(body),
            content_type="application/json",
        )

        assert response.status_code == 200
        mock_service.apply_patch.assert_called_once_with("test_user", **expected)

    @patch("howler.common.loader.datastore")
    @patch("tsx_user_status.config.status_service")
    def test_patch_rejects_invalid_value(self, mock_service, mock_ds_func, user_status_app):
        """A ValueError from apply_patch maps to 400."""
        mock_ds = MagicMock()
        mock_ds.user.get.return_value = {"uname": "test_user"}
        mock_ds_func.return_value = mock_ds
        mock_service.apply_patch.side_effect = ValueError("Invalid status")

        client = user_status_app.test_client()
        response = client.patch(
            "/api/v1/status/users/test_user",
            data=json.dumps({"status": "  "}),
            content_type="application/json",
        )

        assert response.status_code == 400

    @patch("howler.common.loader.datastore")
    @patch("tsx_user_status.config.status_service")
    def test_patch_rejects_empty_body(self, mock_service, mock_ds_func, user_status_app):
        """PATCH with empty object returns 400 (nothing to update)."""
        mock_ds = MagicMock()
        mock_ds.user.get.return_value = {"uname": "test_user"}
        mock_ds_func.return_value = mock_ds

        client = user_status_app.test_client()
        response = client.patch(
            "/api/v1/status/users/test_user",
            data=json.dumps({}),
            content_type="application/json",
        )

        assert response.status_code == 400
        mock_service.apply_patch.assert_not_called()

    @patch("howler.common.loader.datastore")
    @patch("tsx_user_status.config.status_service")
    def test_patch_rejects_non_json(self, mock_service, mock_ds_func, user_status_app):
        """PATCH with non-JSON body returns 400."""
        mock_ds = MagicMock()
        mock_ds.user.get.return_value = {"uname": "test_user"}
        mock_ds_func.return_value = mock_ds

        client = user_status_app.test_client()
        response = client.patch(
            "/api/v1/status/users/test_user",
            data="not json",
            content_type="text/plain",
        )

        assert response.status_code == 400
        mock_service.apply_patch.assert_not_called()

    @patch("howler.common.loader.datastore")
    @patch("tsx_user_status.config.status_service")
    def test_patch_nonexistent_user_returns_404(self, mock_service, mock_ds_func, user_status_app):
        """PATCH for unknown user returns 404."""
        mock_ds = MagicMock()
        mock_ds.user.get.return_value = None
        mock_ds_func.return_value = mock_ds

        client = user_status_app.test_client()
        response = client.patch(
            "/api/v1/status/users/test_user",
            data=json.dumps({"status": "available"}),
            content_type="application/json",
        )

        assert response.status_code == 404
        mock_service.apply_patch.assert_not_called()

    @patch("tsx_user_status.config.status_service")
    def test_get_all_statuses(self, mock_service, user_status_app):
        """Verify GET /users returns all users with status, schedule, team, and tags."""
        mock_service.get_all_statuses.return_value = [
            {
                "uname": "user1",
                "name": "User One",
                "status": "available",
                "schedule": "Day 7-15",
                "team": "MS",
                "tags": {"portfolio": ["Portfolio A"], "products": [], "primary_disciplines": []},
            },
            {
                "uname": "user2",
                "name": "User Two",
                "status": None,
                "schedule": None,
                "team": None,
                "tags": {"portfolio": [], "products": [], "primary_disciplines": []},
            },
        ]

        client = user_status_app.test_client()
        response = client.get("/api/v1/status/users")

        assert response.status_code == 200
        data = response.get_json()
        assert len(data["api_response"]) == 2
        assert data["api_response"][0]["schedule"] == "Day 7-15"
        assert data["api_response"][0]["team"] == "MS"
        assert data["api_response"][0]["tags"] == {
            "portfolio": ["Portfolio A"],
            "products": [],
            "primary_disciplines": [],
        }
        assert data["api_response"][1]["schedule"] is None
        assert data["api_response"][1]["team"] is None
        assert data["api_response"][1]["tags"] == {"portfolio": [], "products": [], "primary_disciplines": []}
