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
    @patch("howler.api.v2.case.case_service")
    @patch("howler.security.auth_service")
    def test_get_case_success(self, mock_auth_service, mock_case_service, mock_datastore, request_context: Flask):
        """Returns 200 and the case dict when it exists."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        case_data = {
            "case_id": "case-001",
            "title": "Test Case",
            "summary": "summary",
            "overview": "overview",
            "escalation": "high",
        }
        mock_datastore.return_value.case.get_if_exists.return_value = case_data

        with request_context.test_request_context(
            headers={"Authorization": "Bearer .", "Content-Type": "application/json"},
        ):
            from howler.api.v2.case import get_case

            result: Response = get_case("case-001")

            assert result.status_code == 200
            body = result.get_json()
            assert body["api_response"]["case_id"] == "case-001"
            assert body["api_response"]["title"] == "Test Case"
            assert body["api_response"]["escalation"] == "high"
            mock_datastore.return_value.case.get_if_exists.assert_called_once_with(key="case-001", as_obj=False)

    @patch("howler.api.v2.case.datastore")
    @patch("howler.api.v2.case.case_service")
    @patch("howler.security.auth_service")
    def test_get_case_not_found(self, mock_auth_service, mock_case_service, mock_datastore, request_context: Flask):
        """Returns 404 when the case does not exist."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        mock_datastore.return_value.case.get_if_exists.return_value = None

        with request_context.test_request_context(
            headers={"Authorization": "Bearer .", "Content-Type": "application/json"},
        ):
            from howler.api.v2.case import get_case

            result: Response = get_case(id="nonexistent")

            assert result.status_code == 404
            mock_datastore.return_value.case.get_if_exists.assert_called_once_with(key="nonexistent", as_obj=False)


# ---------------------------------------------------------------------------
# DELETE /api/v2/case/
# ---------------------------------------------------------------------------


class TestDeleteCases:
    """Tests for the DELETE cases endpoint (bulk delete via JSON list)."""

    @patch("howler.api.v2.case.case_service")
    @patch("howler.security.auth_service")
    def test_delete_cases_no_body_returns_400(self, mock_auth_service, mock_case_service, request_context: Flask):
        """Returns 400 when no JSON body is provided."""
        user = _build_user(["admin", "user"])
        _mock_auth(mock_auth_service, user, ["R", "W"])

        with request_context.test_request_context(
            method="DELETE",
            data=b"null",
            content_type="application/json",
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.case import delete_cases

            result: Response = delete_cases(user=user)

            assert result.status_code == 400
            mock_case_service.delete_cases.assert_not_called()

    @patch("howler.api.v2.case.datastore")
    @patch("howler.api.v2.case.case_service")
    @patch("howler.security.auth_service")
    def test_delete_cases_success_admin(
        self, mock_auth_service, mock_case_service, mock_datastore, request_context: Flask
    ):
        """Admin user can delete cases and gets 204."""
        user = _build_user(["admin", "user"])
        _mock_auth(mock_auth_service, user, ["R", "W"])

        mock_datastore.return_value.case.exists.return_value = True

        with request_context.test_request_context(
            method="DELETE",
            json=["case-del"],
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.case import delete_cases

            result: Response = delete_cases(user=user)

            assert result.status_code == 204
            mock_case_service.delete_cases.assert_called_once_with(["case-del"])

    @patch("howler.api.v2.case.case_service")
    @patch("howler.security.auth_service")
    def test_delete_cases_not_found(self, mock_auth_service, mock_case_service, request_context: Flask):
        """Returns 404 when a case ID does not exist."""
        user = _build_user(["admin", "user"])
        _mock_auth(mock_auth_service, user, ["R", "W"])

        mock_case_service.exists.return_value = False

        with request_context.test_request_context(
            method="DELETE",
            json=["nonexistent"],
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.case import delete_cases

            result: Response = delete_cases(user=user)

            assert result.status_code == 404
            mock_case_service.delete_cases.assert_not_called()

    @patch("howler.api.v2.case.case_service")
    @patch("howler.security.auth_service")
    def test_delete_cases_forbidden_non_admin(self, mock_auth_service, mock_case_service, request_context: Flask):
        """Non-admin user gets 403 when trying to delete."""
        user = _build_user(["user"])
        _mock_auth(mock_auth_service, user, ["R", "W"])

        with request_context.test_request_context(
            method="DELETE",
            json=["case-del"],
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.case import delete_cases

            result: Response = delete_cases(user=user)

            assert result.status_code == 403
            mock_case_service.delete_cases.assert_not_called()


# ---------------------------------------------------------------------------
# POST /api/v2/case/
# ---------------------------------------------------------------------------


class TestCreateCaseEndpoint:
    """Tests for the POST case endpoint."""

    @patch("howler.api.v2.case.case_service")
    @patch("howler.security.auth_service")
    def test_create_case_success(self, mock_auth_service, mock_case_service, request_context: Flask):
        """Returns 201 with the new case when valid data is provided."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        expected = {"case_id": "case-new-case", "title": "New Case", "summary": "S"}
        mock_case_service.create_case.return_value = expected

        with request_context.test_request_context(
            method="POST",
            json={"title": "New Case", "summary": "S"},
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.case import create_case

            result: Response = create_case(user=user)

            assert result.status_code == 201
            body = result.get_json()
            assert body["api_response"]["case_id"] == "case-new-case"
            mock_case_service.create_case.assert_called_once_with({"title": "New Case", "summary": "S"}, user.uname)

    @patch("howler.api.v2.case.case_service")
    @patch("howler.security.auth_service")
    def test_create_case_no_body_returns_400(self, mock_auth_service, mock_case_service, request_context: Flask):
        """Returns 400 when no JSON body is provided."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        with request_context.test_request_context(
            method="POST",
            data=b"null",
            content_type="application/json",
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.case import create_case

            result: Response = create_case(user=user)

            assert result.status_code == 400
            mock_case_service.create_case.assert_not_called()

    @patch("howler.api.v2.case.case_service")
    @patch("howler.security.auth_service")
    def test_create_case_already_exists_returns_400(self, mock_auth_service, mock_case_service, request_context: Flask):
        """Returns 400 when a case with the derived ID already exists."""
        from howler.common.exceptions import ResourceExists

        user = _build_user()
        _mock_auth(mock_auth_service, user)

        mock_case_service.create_case.side_effect = ResourceExists("Case already exists")

        with request_context.test_request_context(
            method="POST",
            json={"title": "Duplicate", "summary": "S"},
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.case import create_case

            result: Response = create_case(user=user)

            assert result.status_code == 400


# ---------------------------------------------------------------------------
# PUT /api/v2/case/<id>
# ---------------------------------------------------------------------------


class TestUpdateCaseEndpoint:
    """Tests for the PUT case endpoint."""

    @patch("howler.api.v2.case.case_service")
    @patch("howler.security.auth_service")
    def test_update_case_success(self, mock_auth_service, mock_case_service, request_context: Flask):
        """Returns 200 with updated case data when the update succeeds."""
        from howler.odm.models.case import Case

        user = _build_user()
        _mock_auth(mock_auth_service, user)

        updated = Case(
            {
                "case_id": "case-001",
                "title": "Updated Title",
                "summary": "S",
                "overview": "O",
                "escalation": "low",
            }
        )
        mock_case_service.update_case.return_value = updated

        with request_context.test_request_context(
            method="PUT",
            json={"title": "Updated Title"},
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.case import update_case

            result: Response = update_case("case-001", user=user)

            assert result.status_code == 200
            mock_case_service.update_case.assert_called_once_with("case-001", {"title": "Updated Title"}, user)

    @patch("howler.api.v2.case.case_service")
    @patch("howler.security.auth_service")
    def test_update_case_not_found(self, mock_auth_service, mock_case_service, request_context: Flask):
        """Returns 404 when the case does not exist."""
        from howler.common.exceptions import NotFoundException

        user = _build_user()
        _mock_auth(mock_auth_service, user)

        mock_case_service.update_case.side_effect = NotFoundException("Case case-001 does not exist")

        with request_context.test_request_context(
            method="PUT",
            json={"title": "New"},
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.case import update_case

            result: Response = update_case("case-001", user=user)

            assert result.status_code == 404

    @patch("howler.api.v2.case.case_service")
    @patch("howler.security.auth_service")
    def test_update_case_no_body_returns_400(self, mock_auth_service, mock_case_service, request_context: Flask):
        """Returns 400 when no JSON body is provided."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        with request_context.test_request_context(
            method="PUT",
            data=b"null",
            content_type="application/json",
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.case import update_case

            result: Response = update_case("case-001", user=user)

            assert result.status_code == 400

    @patch("howler.api.v2.case.case_service")
    @patch("howler.security.auth_service")
    def test_update_case_invalid_field_returns_400(self, mock_auth_service, mock_case_service, request_context: Flask):
        """Returns 400 when the service raises InvalidDataException (e.g. immutable field)."""
        from howler.common.exceptions import InvalidDataException

        user = _build_user()
        _mock_auth(mock_auth_service, user)

        mock_case_service.update_case.side_effect = InvalidDataException("Cannot modify immutable field(s): case_id")

        with request_context.test_request_context(
            method="PUT",
            json={"case_id": "new-id"},
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.case import update_case

            result: Response = update_case("case-001", user=user)

            assert result.status_code == 400
            mock_case_service.update_case.assert_called_once_with("case-001", {"case_id": "new-id"}, user)


# ---------------------------------------------------------------------------
# POST /api/v2/case/hide
# ---------------------------------------------------------------------------


class TestHideCasesEndpoint:
    """Tests for the POST /hide case endpoint."""

    @patch("howler.api.v2.case.datastore")
    @patch("howler.api.v2.case.case_service")
    @patch("howler.security.auth_service")
    def test_hide_cases_success(self, mock_auth_service, mock_case_service, mock_datastore, request_context: Flask):
        """Returns 204 when all supplied case IDs exist."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        mock_datastore.return_value.case.exists.return_value = True

        with request_context.test_request_context(
            method="POST",
            json=["case-001", "case-002"],
            headers={"Authorization": "Bearer .", "Content-Type": "application/json"},
        ):
            from howler.api.v2.case import hide_cases

            result: Response = hide_cases(user=user)

            assert result.status_code == 204
            mock_case_service.hide_cases.assert_called_once_with(["case-001", "case-002"], user=user.uname)

    @patch("howler.api.v2.case.case_service")
    @patch("howler.security.auth_service")
    def test_hide_cases_no_body_returns_400(self, mock_auth_service, mock_case_service, request_context: Flask):
        """Returns 400 when the JSON body is null (no case IDs sent)."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        with request_context.test_request_context(
            method="POST",
            data=b"null",
            content_type="application/json",
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.case import hide_cases

            result: Response = hide_cases(user=user)

            assert result.status_code == 400
            mock_case_service.hide_cases.assert_not_called()

    @patch("howler.api.v2.case.case_service")
    @patch("howler.security.auth_service")
    def test_hide_cases_nonexistent_id_returns_404(self, mock_auth_service, mock_case_service, request_context: Flask):
        """Returns 404 when a supplied case ID does not exist."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        # Only "case-001" exists
        mock_case_service.exists.side_effect = lambda case_id: case_id == "case-001"

        with request_context.test_request_context(
            method="POST",
            json=["case-001", "nonexistent"],
            headers={"Authorization": "Bearer .", "Content-Type": "application/json"},
        ):
            from howler.api.v2.case import hide_cases

            result: Response = hide_cases(user=user)

            assert result.status_code == 404
            mock_case_service.hide_cases.assert_not_called()

    @patch("howler.api.v2.case.case_service")
    @patch("howler.security.auth_service")
    def test_hide_cases_all_nonexistent_returns_404(self, mock_auth_service, mock_case_service, request_context: Flask):
        """Returns 404 when none of the supplied case IDs exist."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        mock_case_service.exists.return_value = False

        with request_context.test_request_context(
            method="POST",
            json=["ghost-1", "ghost-2"],
            headers={"Authorization": "Bearer .", "Content-Type": "application/json"},
        ):
            from howler.api.v2.case import hide_cases

            result: Response = hide_cases(user=user)

            assert result.status_code == 404
            mock_case_service.hide_cases.assert_not_called()


# ---------------------------------------------------------------------------
# DELETE /api/v2/case/<id>/items
# ---------------------------------------------------------------------------


class TestDeleteItemEndpoint:
    """Tests for the DELETE /<id>/items case endpoint."""

    @patch("howler.api.v2.case.case_service")
    @patch("howler.security.auth_service")
    def test_delete_item_success(self, mock_auth_service, mock_case_service, request_context: Flask):
        """Returns 200 with the updated case when a single item is removed successfully."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        mock_case_service.remove_case_items.return_value = {"case_id": "case-001", "title": "Test"}

        with request_context.test_request_context(
            method="DELETE",
            json={"values": ["hit-001"]},
            headers={"Authorization": "Bearer .", "Content-Type": "application/json"},
        ):
            from howler.api.v2.case import delete_item

            result: Response = delete_item("case-001")

            assert result.status_code == 200
            mock_case_service.remove_case_items.assert_called_once_with("case-001", ["hit-001"])

    @patch("howler.api.v2.case.case_service")
    @patch("howler.security.auth_service")
    def test_delete_item_multiple_values(self, mock_auth_service, mock_case_service, request_context: Flask):
        """Calls remove_case_item once with the full list and returns 200 with the updated case."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        mock_case_service.remove_case_items.return_value = {"case_id": "case-001", "title": "Test"}

        with request_context.test_request_context(
            method="DELETE",
            json={"values": ["hit-001", "hit-002", "obs-003"]},
            headers={"Authorization": "Bearer .", "Content-Type": "application/json"},
        ):
            from howler.api.v2.case import delete_item

            result: Response = delete_item("case-001")

            assert result.status_code == 200
            mock_case_service.remove_case_items.assert_called_once_with("case-001", ["hit-001", "hit-002", "obs-003"])

    @patch("howler.api.v2.case.case_service")
    @patch("howler.security.auth_service")
    def test_delete_item_missing_body_returns_400(self, mock_auth_service, mock_case_service, request_context: Flask):
        """Returns 400 when no JSON body is sent."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        with request_context.test_request_context(
            method="DELETE",
            data=b"null",
            content_type="application/json",
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.case import delete_item

            result: Response = delete_item("case-001")

            assert result.status_code == 400
            mock_case_service.remove_case_items.assert_not_called()

    @patch("howler.api.v2.case.case_service")
    @patch("howler.security.auth_service")
    def test_delete_item_missing_values_field_returns_400(
        self, mock_auth_service, mock_case_service, request_context: Flask
    ):
        """Returns 400 when the JSON body does not contain a 'values' field."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        with request_context.test_request_context(
            method="DELETE",
            json={"type": "hit"},
            headers={"Authorization": "Bearer .", "Content-Type": "application/json"},
        ):
            from howler.api.v2.case import delete_item

            result: Response = delete_item("case-001")

            assert result.status_code == 400
            mock_case_service.remove_case_items.assert_not_called()

    @patch("howler.api.v2.case.case_service")
    @patch("howler.security.auth_service")
    def test_delete_item_empty_values_list_returns_400(
        self, mock_auth_service, mock_case_service, request_context: Flask
    ):
        """Returns 400 when 'values' is an empty list."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        with request_context.test_request_context(
            method="DELETE",
            json={"values": []},
            headers={"Authorization": "Bearer .", "Content-Type": "application/json"},
        ):
            from howler.api.v2.case import delete_item

            result: Response = delete_item("case-001")

            assert result.status_code == 400
            mock_case_service.remove_case_items.assert_not_called()

    @patch("howler.api.v2.case.case_service")
    @patch("howler.security.auth_service")
    def test_delete_item_values_not_a_list_returns_400(
        self, mock_auth_service, mock_case_service, request_context: Flask
    ):
        """Returns 400 when 'values' is not a list."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        with request_context.test_request_context(
            method="DELETE",
            json={"values": "hit-001"},
            headers={"Authorization": "Bearer .", "Content-Type": "application/json"},
        ):
            from howler.api.v2.case import delete_item

            result: Response = delete_item("case-001")

            assert result.status_code == 400
            mock_case_service.remove_case_items.assert_not_called()

    @patch("howler.api.v2.case.case_service")
    @patch("howler.security.auth_service")
    def test_delete_item_not_found_returns_400(self, mock_auth_service, mock_case_service, request_context: Flask):
        """Returns 400 when case_service raises NotFoundException (missing item or case)."""
        from howler.common.exceptions import NotFoundException

        user = _build_user()
        _mock_auth(mock_auth_service, user)

        mock_case_service.remove_case_items.side_effect = NotFoundException(
            "Case item(s) not found in case: missing-item"
        )

        with request_context.test_request_context(
            method="DELETE",
            json={"values": ["missing-item"]},
            headers={"Authorization": "Bearer .", "Content-Type": "application/json"},
        ):
            from howler.api.v2.case import delete_item

            result: Response = delete_item("case-001")

            assert result.status_code == 400
            mock_case_service.remove_case_items.assert_called_once_with("case-001", ["missing-item"])

    @patch("howler.api.v2.case.case_service")
    @patch("howler.security.auth_service")
    def test_delete_item_invalid_data_returns_400(self, mock_auth_service, mock_case_service, request_context: Flask):
        """Returns 400 when case_service raises InvalidDataException."""
        from howler.common.exceptions import InvalidDataException

        user = _build_user()
        _mock_auth(mock_auth_service, user)

        mock_case_service.remove_case_items.side_effect = InvalidDataException("Invalid item data")

        with request_context.test_request_context(
            method="DELETE",
            json={"values": ["hit-001"]},
            headers={"Authorization": "Bearer .", "Content-Type": "application/json"},
        ):
            from howler.api.v2.case import delete_item

            result: Response = delete_item("case-001")

            assert result.status_code == 400

    @patch("howler.api.v2.case.case_service")
    @patch("howler.security.auth_service")
    def test_delete_item_datastore_error_returns_500(
        self, mock_auth_service, mock_case_service, request_context: Flask
    ):
        """Returns 500 when case_service raises DataStoreException."""
        from howler.datastore.exceptions import DataStoreException

        user = _build_user()
        _mock_auth(mock_auth_service, user)

        mock_case_service.remove_case_items.side_effect = DataStoreException("datastore failure")

        with request_context.test_request_context(
            method="DELETE",
            json={"values": ["hit-001"]},
            headers={"Authorization": "Bearer .", "Content-Type": "application/json"},
        ):
            from howler.api.v2.case import delete_item

            result: Response = delete_item("case-001")

            assert result.status_code == 500


# ---------------------------------------------------------------------------
# PATCH /api/v2/case/<case_id>/items
# ---------------------------------------------------------------------------


class TestRenameItemEndpoint:
    """Tests for the PATCH /<case_id>/items endpoint."""

    @patch("howler.api.v2.case.case_service")
    @patch("howler.security.auth_service")
    def test_rename_item_success(self, mock_auth_service, mock_case_service, request_context: Flask):
        """Returns 200 with the updated case when the rename succeeds."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        mock_case_service.rename_case_item.return_value = {"case_id": "case-001", "title": "Test"}

        with request_context.test_request_context(
            method="PATCH",
            json={"value": "hit-001", "new_path": "folder/New Name"},
            headers={"Authorization": "Bearer .", "Content-Type": "application/json"},
        ):
            from howler.api.v2.case import rename_item

            result: Response = rename_item(case_id="case-001")

            assert result.status_code == 200
            mock_case_service.rename_case_item.assert_called_once_with(
                "case-001", item_value="hit-001", new_path="folder/New Name"
            )

    @patch("howler.api.v2.case.case_service")
    @patch("howler.security.auth_service")
    def test_rename_item_missing_body_returns_400(self, mock_auth_service, mock_case_service, request_context: Flask):
        """Returns 400 when no JSON body is provided."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        with request_context.test_request_context(
            method="PATCH",
            data=b"null",
            content_type="application/json",
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.case import rename_item

            result: Response = rename_item(case_id="case-001")

            assert result.status_code == 400
            mock_case_service.rename_case_item.assert_not_called()

    @patch("howler.api.v2.case.case_service")
    @patch("howler.security.auth_service")
    def test_rename_item_missing_value_returns_400(self, mock_auth_service, mock_case_service, request_context: Flask):
        """Returns 400 when 'value' field is missing from the body."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        with request_context.test_request_context(
            method="PATCH",
            json={"new_path": "folder/New Name"},
            headers={"Authorization": "Bearer .", "Content-Type": "application/json"},
        ):
            from howler.api.v2.case import rename_item

            result: Response = rename_item(case_id="case-001")

            assert result.status_code == 400
            mock_case_service.rename_case_item.assert_not_called()

    @patch("howler.api.v2.case.case_service")
    @patch("howler.security.auth_service")
    def test_rename_item_missing_new_path_returns_400(
        self, mock_auth_service, mock_case_service, request_context: Flask
    ):
        """Returns 400 when 'new_path' field is missing from the body."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        with request_context.test_request_context(
            method="PATCH",
            json={"value": "hit-001"},
            headers={"Authorization": "Bearer .", "Content-Type": "application/json"},
        ):
            from howler.api.v2.case import rename_item

            result: Response = rename_item(case_id="case-001")

            assert result.status_code == 400
            mock_case_service.rename_case_item.assert_not_called()

    @patch("howler.api.v2.case.case_service")
    @patch("howler.security.auth_service")
    def test_rename_item_not_found_returns_400(self, mock_auth_service, mock_case_service, request_context: Flask):
        """Returns 400 when case_service raises NotFoundException."""
        from howler.common.exceptions import NotFoundException

        user = _build_user()
        _mock_auth(mock_auth_service, user)

        mock_case_service.rename_case_item.side_effect = NotFoundException("Item not found")

        with request_context.test_request_context(
            method="PATCH",
            json={"value": "missing", "new_path": "folder/New Name"},
            headers={"Authorization": "Bearer .", "Content-Type": "application/json"},
        ):
            from howler.api.v2.case import rename_item

            result: Response = rename_item(case_id="case-001")

            assert result.status_code == 400

    @patch("howler.api.v2.case.case_service")
    @patch("howler.security.auth_service")
    def test_rename_item_path_conflict_returns_400(self, mock_auth_service, mock_case_service, request_context: Flask):
        """Returns 400 when case_service raises InvalidDataException (path already taken)."""
        from howler.common.exceptions import InvalidDataException

        user = _build_user()
        _mock_auth(mock_auth_service, user)

        mock_case_service.rename_case_item.side_effect = InvalidDataException("Path already taken")

        with request_context.test_request_context(
            method="PATCH",
            json={"value": "hit-001", "new_path": "folder/Taken"},
            headers={"Authorization": "Bearer .", "Content-Type": "application/json"},
        ):
            from howler.api.v2.case import rename_item

            result: Response = rename_item(case_id="case-001")

            assert result.status_code == 400

    @patch("howler.api.v2.case.case_service")
    @patch("howler.security.auth_service")
    def test_rename_item_datastore_error_returns_500(
        self, mock_auth_service, mock_case_service, request_context: Flask
    ):
        """Returns 500 when case_service raises DataStoreException."""
        from howler.datastore.exceptions import DataStoreException

        user = _build_user()
        _mock_auth(mock_auth_service, user)

        mock_case_service.rename_case_item.side_effect = DataStoreException("datastore failure")

        with request_context.test_request_context(
            method="PATCH",
            json={"value": "hit-001", "new_path": "folder/New Name"},
            headers={"Authorization": "Bearer .", "Content-Type": "application/json"},
        ):
            from howler.api.v2.case import rename_item

            result: Response = rename_item(case_id="case-001")

            assert result.status_code == 500
