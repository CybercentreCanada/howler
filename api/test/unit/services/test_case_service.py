from unittest.mock import MagicMock, patch

import pytest

from howler.odm.models.case import Case
from howler.services import case_service

# ---------------------------------------------------------------------------
# exists()
# ---------------------------------------------------------------------------


class TestExists:
    """Tests for case_service.exists."""

    @patch("howler.services.case_service.datastore")
    def test_exists_returns_true(self, mock_ds_fn):
        """Returns True when the case exists in the datastore."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.exists.return_value = True

        assert case_service.exists("case-001") is True
        mock_ds.case.exists.assert_called_once_with("case-001")

    @patch("howler.services.case_service.datastore")
    def test_exists_returns_false(self, mock_ds_fn):
        """Returns False when the case does not exist."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.exists.return_value = False

        assert case_service.exists("nonexistent") is False
        mock_ds.case.exists.assert_called_once_with("nonexistent")

    @patch("howler.services.case_service.datastore")
    def test_exists_forwards_return_value(self, mock_ds_fn):
        """exists() returns exactly what the datastore returns, not a hardcoded value."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        # Return a truthy non-bool to prove passthrough
        mock_ds.case.exists.return_value = "unexpected"
        result = case_service.exists("case-x")

        assert result == "unexpected"
        mock_ds.case.exists.assert_called_once_with("case-x")


# ---------------------------------------------------------------------------
# get_case()
# ---------------------------------------------------------------------------


class TestGetCase:
    """Tests for case_service.get_case."""

    @patch("howler.services.case_service.datastore")
    def test_get_case_default_params(self, mock_ds_fn):
        """Calls datastore with as_obj=False and version=False by default."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.get_if_exists.return_value = {"case_id": "case-001"}

        result = case_service.get_case("case-001")

        mock_ds.case.get_if_exists.assert_called_once_with(key="case-001", as_obj=False, version=False)
        assert result == {"case_id": "case-001"}

    @patch("howler.services.case_service.datastore")
    def test_get_case_as_odm(self, mock_ds_fn):
        """When as_odm=True, passes as_obj=True to the datastore."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        case_obj = Case(
            {
                "case_id": "case-002",
                "title": "T",
                "summary": "S",
                "overview": "O",
                "escalation": "low",
            }
        )
        mock_ds.case.get_if_exists.return_value = case_obj

        result = case_service.get_case("case-002", as_odm=True)

        mock_ds.case.get_if_exists.assert_called_once_with(key="case-002", as_obj=True, version=False)
        assert result.case_id == "case-002"

    @patch("howler.services.case_service.datastore")
    def test_get_case_with_version(self, mock_ds_fn):
        """When version=True, passes version=True to the datastore."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.get_if_exists.return_value = ({"case_id": "case-003"}, "v1")

        result = case_service.get_case("case-003", as_odm=False, version=True)

        mock_ds.case.get_if_exists.assert_called_once_with(key="case-003", as_obj=False, version=True)
        assert result == ({"case_id": "case-003"}, "v1")

    @patch("howler.services.case_service.datastore")
    def test_get_case_as_odm_with_version(self, mock_ds_fn):
        """When as_odm=True and version=True, returns (Case, str) tuple."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        case_obj = Case(
            {
                "case_id": "case-004",
                "title": "T",
                "summary": "S",
                "overview": "O",
                "escalation": "high",
            }
        )
        mock_ds.case.get_if_exists.return_value = (case_obj, "v2")

        result = case_service.get_case("case-004", as_odm=True, version=True)

        mock_ds.case.get_if_exists.assert_called_once_with(key="case-004", as_obj=True, version=True)
        assert result == (case_obj, "v2")

    @patch("howler.services.case_service.datastore")
    def test_get_case_returns_none_when_missing(self, mock_ds_fn):
        """Returns None when case does not exist (get_if_exists returns None)."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.get_if_exists.return_value = None

        result = case_service.get_case("missing")

        mock_ds.case.get_if_exists.assert_called_once_with(key="missing", as_obj=False, version=False)
        assert result is None


# ---------------------------------------------------------------------------
# create_case() — stub raises NotImplementedError
# ---------------------------------------------------------------------------


class TestCreateCase:
    """Tests for case_service.create_case (currently unimplemented)."""

    def test_create_case_not_implemented(self):
        """create_case raises NotImplementedError until implemented."""
        with pytest.raises(NotImplementedError):
            case_service.create_case({"title": "New"}, "admin")


# ---------------------------------------------------------------------------
# update_case() — stub raises NotImplementedError
# ---------------------------------------------------------------------------


class TestUpdateCase:
    """Tests for case_service.update_case (currently unimplemented)."""

    def test_update_case_not_implemented(self):
        """update_case raises NotImplementedError until implemented."""
        mock_user = MagicMock()
        with pytest.raises(NotImplementedError):
            case_service.update_case("case-001", {"title": "Updated"}, mock_user)
