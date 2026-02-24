from typing import cast
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask, Response

from howler.common.loader import datastore
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
    return user_data


def _mock_auth(mock_auth_service, user, priv=None):
    """Configure auth mocks so api_login passes."""
    if priv is None:
        priv = ["R", "W", "E"]
    mock_auth_service.bearer_auth = MagicMock(return_value=(user, priv))
    datastore().user.save(user.uname, user)


# ---------------------------------------------------------------------------
# GET /api/v2/case/<id>
# ---------------------------------------------------------------------------


class TestGetCase:
    """Tests for the GET case endpoint."""

    @patch("howler.api.v2.case.datastore")
    @patch("howler.security.auth_service")
    def test_get_case_success(self, mock_auth_service, mock_ds_fn, request_context: Flask):
        """Returns 200 and the case dict when it exists."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        case_data = {
            "case_id": "case-001",
            "title": "Test Case",
            "summary": "summary",
            "overview": "overview",
            "escalation": "high",
        }
        mock_ds.case.search.return_value = {"items": [case_data]}

        with request_context.test_request_context(
            headers={"Authorization": "Bearer .", "Content-Type": "application/json"},
        ):
            from howler.api.v2.case import get_case

            result: Response = get_case(id="case-001")

            assert result.status_code == 200
            body = result.get_json()
            assert body["api_response"]["case_id"] == "case-001"
            assert body["api_response"]["title"] == "Test Case"
            assert body["api_response"]["escalation"] == "high"
            mock_ds.case.search.assert_called_once_with("case_id:case-001", as_obj=False, rows=1)

    @patch("howler.api.v2.case.datastore")
    @patch("howler.security.auth_service")
    def test_get_case_not_found(self, mock_auth_service, mock_ds_fn, request_context: Flask):
        """Returns 404 when the case does not exist."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.search.return_value = {"items": []}

        with request_context.test_request_context(
            headers={"Authorization": "Bearer .", "Content-Type": "application/json"},
        ):
            from howler.api.v2.case import get_case

            result: Response = get_case(id="nonexistent")

            assert result.status_code == 404
            mock_ds.case.search.assert_called_once_with("case_id:nonexistent", as_obj=False, rows=1)

    @patch("howler.api.v2.case.datastore")
    @patch("howler.security.auth_service")
    def test_get_case_bad_query(self, mock_auth_service, mock_ds_fn, request_context: Flask):
        """Returns 400 when the search raises a ValueError."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.search.side_effect = ValueError("bad query")

        with request_context.test_request_context(
            headers={"Authorization": "Bearer .", "Content-Type": "application/json"},
        ):
            from howler.api.v2.case import get_case

            result: Response = get_case(id="bad-id")

            assert result.status_code == 400
            mock_ds.case.search.assert_called_once_with("case_id:bad-id", as_obj=False, rows=1)


# ---------------------------------------------------------------------------
# DELETE /api/v2/case/<id>
# ---------------------------------------------------------------------------


class TestDeleteCase:
    """Tests for the DELETE case endpoint."""

    @patch("howler.api.v2.case.datastore")
    @patch("howler.security.auth_service")
    def test_delete_case_success_admin(self, mock_auth_service, mock_ds_fn, request_context: Flask):
        """Admin user can delete a case and gets 204."""
        user = _build_user(["admin", "user"])
        _mock_auth(mock_auth_service, user, ["R", "W"])

        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_ds.case.get_if_exists.return_value = {"case_id": "case-del"}
        mock_ds.case.delete.return_value = True

        with request_context.test_request_context(
            headers={"Authorization": "Bearer .", "Content-Type": "application/json"},
        ):
            from howler.api.v2.case import delete_case

            result: Response = delete_case(id="case-del")

            assert result.status_code == 204
            mock_ds.case.get_if_exists.assert_called_once_with("case-del")
            mock_ds.case.delete.assert_called_once_with("case-del")
            mock_ds.case.commit.assert_called_once()

    @patch("howler.api.v2.case.datastore")
    @patch("howler.security.auth_service")
    def test_delete_case_not_found(self, mock_auth_service, mock_ds_fn, request_context: Flask):
        """Returns 404 when the case does not exist."""
        user = _build_user(["admin", "user"])
        _mock_auth(mock_auth_service, user, ["R", "W"])

        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.get_if_exists.return_value = None

        with request_context.test_request_context(
            headers={"Authorization": "Bearer .", "Content-Type": "application/json"},
        ):
            from howler.api.v2.case import delete_case

            result: Response = delete_case(id="nonexistent")

            assert result.status_code == 404
            mock_ds.case.get_if_exists.assert_called_once_with("nonexistent")
            mock_ds.case.delete.assert_not_called()

    @patch("howler.api.v2.case.datastore")
    @patch("howler.security.auth_service")
    def test_delete_case_forbidden_non_admin(self, mock_auth_service, mock_ds_fn, request_context: Flask):
        """Non-admin user gets 403 when trying to delete."""
        user = _build_user(["user"])
        _mock_auth(mock_auth_service, user, ["R", "W"])

        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.get_if_exists.return_value = {"case_id": "case-del"}

        with request_context.test_request_context(
            headers={"Authorization": "Bearer .", "Content-Type": "application/json"},
        ):
            from howler.api.v2.case import delete_case

            result: Response = delete_case(id="case-del")

            assert result.status_code == 403
            mock_ds.case.get_if_exists.assert_called_once_with("case-del")
            mock_ds.case.delete.assert_not_called()


# ---------------------------------------------------------------------------
# POST /api/v2/case/ — stub raises NotImplementedError
# ---------------------------------------------------------------------------


class TestCreateCaseEndpoint:
    """Tests for the POST case endpoint."""

    @patch("howler.api.v2.case.datastore")
    @patch("howler.security.auth_service")
    def test_create_case_not_implemented(self, mock_auth_service, mock_ds_fn, request_context: Flask):
        """create_case endpoint raises NotImplementedError until implemented."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        with request_context.test_request_context(
            headers={"Authorization": "Bearer .", "Content-Type": "application/json"},
        ):
            from howler.api.v2.case import create_case

            with pytest.raises(NotImplementedError):
                create_case()


# ---------------------------------------------------------------------------
# PUT /api/v2/case/<id> — stub raises NotImplementedError
# ---------------------------------------------------------------------------


class TestUpdateCaseEndpoint:
    """Tests for the PUT case endpoint."""

    @patch("howler.api.v2.case.datastore")
    @patch("howler.security.auth_service")
    def test_update_case_not_implemented(self, mock_auth_service, mock_ds_fn, request_context: Flask):
        """update_case endpoint raises NotImplementedError until implemented."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        with request_context.test_request_context(
            headers={"Authorization": "Bearer .", "Content-Type": "application/json"},
        ):
            from howler.api.v2.case import update_case

            with pytest.raises(NotImplementedError):
                update_case(id="case-001")
