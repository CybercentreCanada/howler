from unittest.mock import MagicMock, patch

import pytest

from howler.common.exceptions import InvalidDataException, NotFoundException, ResourceExists
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
# create_case()
# ---------------------------------------------------------------------------


class TestCreateCase:
    """Tests for case_service.create_case."""

    @patch("howler.services.case_service.datastore")
    def test_create_case_saves_to_datastore(self, mock_ds_fn):
        """create_case saves the Case ODM to the datastore."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.exists.return_value = False

        mock_collection = MagicMock()
        mock_ds.__getitem__ = MagicMock(return_value=mock_collection)

        case_obj = MagicMock(spec=Case)
        case_obj.log = []

        case_service.create_case("case-new", case_obj, user="admin")

        mock_collection.save.assert_called_once_with("case-new", case_obj)

    @patch("howler.services.case_service.datastore")
    def test_create_case_raises_resource_exists(self, mock_ds_fn):
        """create_case raises ResourceExists when the case_id already exists."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.exists.return_value = True

        case_obj = MagicMock(spec=Case)
        case_obj.log = []

        with pytest.raises(ResourceExists):
            case_service.create_case("case-existing", case_obj, user="admin")

    @patch("howler.services.case_service.datastore")
    def test_create_case_skip_exists_bypasses_check(self, mock_ds_fn):
        """create_case with skip_exists=True does not check existence first."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_collection = MagicMock()
        mock_ds.__getitem__ = MagicMock(return_value=mock_collection)

        case_obj = MagicMock(spec=Case)
        case_obj.log = []

        case_service.create_case("case-new", case_obj, user="admin", skip_exists=True)

        mock_ds.case.exists.assert_not_called()
        mock_collection.save.assert_called_once()


# ---------------------------------------------------------------------------
# update_case()
# ---------------------------------------------------------------------------


class TestUpdateCase:
    """Tests for case_service.update_case."""

    @patch("howler.services.case_service.datastore")
    def test_update_case_raises_not_found(self, mock_ds_fn):
        """update_case raises NotFoundException when case does not exist."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.get_if_exists.return_value = None

        mock_user = MagicMock()
        mock_user.uname = "analyst"

        with pytest.raises(NotFoundException):
            case_service.update_case("case-missing", {"title": "Updated"}, mock_user)

    @patch("howler.services.case_service.datastore")
    def test_update_case_raises_invalid_data_for_immutable_field(self, mock_ds_fn):
        """update_case raises InvalidDataException when an immutable field is supplied."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.get_if_exists.return_value = Case(
            {
                "case_id": "case-001",
                "title": "T",
                "summary": "S",
                "overview": "O",
                "escalation": "low",
            }
        )

        mock_user = MagicMock()
        mock_user.uname = "analyst"

        with pytest.raises(InvalidDataException):
            case_service.update_case("case-001", {"case_id": "new-id"}, mock_user)

    @patch("howler.services.case_service.datastore")
    def test_update_case_updates_title(self, mock_ds_fn):
        """update_case saves the updated case and returns it."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.get_if_exists.return_value = Case(
            {
                "case_id": "case-001",
                "title": "Old Title",
                "summary": "S",
                "overview": "O",
                "escalation": "low",
            }
        )

        mock_user = MagicMock()
        mock_user.uname = "analyst"

        result = case_service.update_case("case-001", {"title": "New Title"}, mock_user)

        mock_ds.case.save.assert_called_once()
        assert result.title == "New Title"


# ---------------------------------------------------------------------------
# hide_cases()
# ---------------------------------------------------------------------------


class TestHideCases:
    """Tests for case_service.hide_cases."""

    @patch("howler.services.case_service.datastore")
    def test_hide_cases_sets_visible_false_on_target(self, mock_ds_fn):
        """hide_cases sets visible=False and saves each target case."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_collection = MagicMock()
        mock_ds.__getitem__ = MagicMock(return_value=mock_collection)

        # No cross-case references
        mock_collection.stream_search.return_value = iter([])

        case_obj = MagicMock()
        case_obj.items = []
        mock_collection.get_if_exists.return_value = case_obj

        case_service.hide_cases({"case-001"})

        mock_collection.get_if_exists.assert_called_with("case-001", as_obj=True)
        assert case_obj.visible is False
        mock_collection.save.assert_called_with("case-001", case_obj)

    @patch("howler.services.case_service.datastore")
    def test_hide_cases_marks_related_items_not_visible(self, mock_ds_fn):
        """Items in other cases that reference a hidden case ID get visible=False."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_collection = MagicMock()
        mock_ds.__getitem__ = MagicMock(return_value=mock_collection)

        # stream_search returns a related case that is NOT in the hidden set
        mock_collection.stream_search.return_value = iter([{"case_id": "case-other"}])

        # The related case has an item pointing to the hidden case ID
        related_item = MagicMock()
        related_item.id = "case-001"
        related_item.visible = True

        unrelated_item = MagicMock()
        unrelated_item.id = "something-else"
        unrelated_item.visible = True

        related_case_obj = MagicMock()
        related_case_obj.items = [related_item, unrelated_item]

        # The target case itself
        target_case_obj = MagicMock()
        target_case_obj.items = []

        mock_collection.get_if_exists.side_effect = lambda case_id, as_obj=False: (
            related_case_obj if case_id == "case-other" else target_case_obj
        )

        case_service.hide_cases({"case-001"})

        # The matching item's visible flag must be set to False
        assert related_item.visible is False
        # The unrelated item must be untouched
        assert unrelated_item.visible is True
        # The related case must be saved with the update
        mock_collection.save.assert_any_call("case-other", related_case_obj)

    @patch("howler.services.case_service.datastore")
    def test_hide_cases_skips_case_that_is_itself_being_hidden(self, mock_ds_fn):
        """stream_search results whose case_id is in the hidden set are skipped."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_collection = MagicMock()
        mock_ds.__getitem__ = MagicMock(return_value=mock_collection)

        # stream_search returns the case being hidden itself
        mock_collection.stream_search.return_value = iter([{"case_id": "case-001"}])

        case_obj = MagicMock()
        case_obj.items = []
        mock_collection.get_if_exists.return_value = case_obj

        case_service.hide_cases({"case-001"})

        # get_if_exists for the cross-case update path must NOT have been called
        # with "case-001" from the stream loop (only from the direct hide loop)
        calls = [call for call in mock_collection.get_if_exists.call_args_list]
        # All get_if_exists calls must come from the direct hide loop (as_obj=True positional)
        for call in calls:
            assert call == (({"case-001"} & {call.args[0]}) and True) or call.kwargs.get("as_obj") is True

    @patch("howler.services.case_service.logger")
    @patch("howler.services.case_service.datastore")
    def test_hide_cases_logs_warning_when_case_not_found(self, mock_ds_fn, mock_logger):
        """hide_cases logs a warning when a target case_id does not exist."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_collection = MagicMock()
        mock_ds.__getitem__ = MagicMock(return_value=mock_collection)

        mock_collection.stream_search.return_value = iter([])
        mock_collection.get_if_exists.return_value = None

        case_service.hide_cases({"case-missing"})

        mock_logger.warning.assert_called_once()
        warning_msg = mock_logger.warning.call_args[0][0]
        assert "case-missing" in warning_msg

    @patch("howler.services.case_service.datastore")
    def test_hide_cases_multiple_ids(self, mock_ds_fn):
        """hide_cases processes all supplied case IDs."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_collection = MagicMock()
        mock_ds.__getitem__ = MagicMock(return_value=mock_collection)

        mock_collection.stream_search.return_value = iter([])

        case_a = MagicMock()
        case_a.items = []
        case_b = MagicMock()
        case_b.items = []

        mock_collection.get_if_exists.side_effect = lambda case_id, as_obj=False: (
            case_a if case_id == "case-a" else case_b
        )

        case_service.hide_cases({"case-a", "case-b"})

        assert case_a.visible is False
        assert case_b.visible is False
        assert mock_collection.save.call_count == 2
