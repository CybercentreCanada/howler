from unittest.mock import MagicMock, patch

import pytest

from howler.common.exceptions import InvalidDataException, NotFoundException
from howler.odm.models.case import Case
from howler.services import case_service

# ---------------------------------------------------------------------------
# create_case()
# ---------------------------------------------------------------------------


class TestCreateCase:
    """Tests for case_service.create_case."""

    @patch("howler.services.case_service.datastore")
    def test_create_case_saves_to_datastore(self, mock_ds_fn):
        """create_case constructs a Case from title/summary and saves it."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        case_service.create_case({"title": "New Case", "summary": "A summary"}, user="admin")

        mock_ds.case.save.assert_called_once()
        saved_id, saved_case = mock_ds.case.save.call_args[0]
        assert saved_id == saved_case.case_id
        assert saved_case.title == "New Case"
        assert saved_case.summary == "A summary"

    @patch("howler.services.case_service.datastore")
    def test_create_case_generates_unique_id(self, mock_ds_fn):
        """create_case auto-generates a unique UUID for each case."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        case_service.create_case({"title": "Title A", "summary": "Summary A"}, user="admin")
        case_service.create_case({"title": "Title B", "summary": "Summary B"}, user="admin")

        calls = mock_ds.case.save.call_args_list
        id_a = calls[0][0][0]
        id_b = calls[1][0][0]
        assert id_a != id_b

    @patch("howler.services.case_service.datastore")
    def test_create_case_returns_primitives_dict(self, mock_ds_fn):
        """create_case returns the created case as a plain dict."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        result = case_service.create_case({"title": "Title", "summary": "Summary"}, user="admin")

        assert isinstance(result, dict)
        assert result["title"] == "Title"
        assert result["summary"] == "Summary"
        assert "case_id" in result

    @patch("howler.services.case_service.datastore")
    def test_create_case_sets_log_entry(self, mock_ds_fn):
        """create_case adds a creation log entry for the given user."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        case_service.create_case({"title": "Title", "summary": "Summary"}, user="admin")

        _, saved_case = mock_ds.case.save.call_args[0]
        assert len(saved_case.log) == 1
        assert saved_case.log[0].user == "admin"

    @patch("howler.services.case_service.datastore")
    def test_create_case_no_user_defaults_to_system(self, mock_ds_fn):
        """create_case uses 'system' as the log user when user='' (the default)."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        case_service.create_case({"title": "Title", "summary": "Summary"})

        _, saved_case = mock_ds.case.save.call_args[0]
        assert len(saved_case.log) == 1
        assert saved_case.log[0].user == "system"

    @patch("howler.services.case_service.datastore")
    def test_create_case_raises_when_empty_data(self, mock_ds_fn):
        """create_case raises InvalidDataException when case data is empty."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        with pytest.raises(InvalidDataException):
            case_service.create_case({})

        mock_ds.case.save.assert_not_called()


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
        assert result.updated is not None
        assert len(result.log) == 1
        assert result.log[0].key == "title"
        assert result.log[0].user == "analyst"
        assert result.log[0].previous_value == "Old Title"
        assert result.log[0].new_value == "New Title"

    @patch("howler.services.case_service.datastore")
    def test_update_case_raises_invalid_for_updated_field(self, mock_ds_fn):
        """update_case raises InvalidDataException when the immutable 'updated' field is supplied."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.get_if_exists.return_value = Case(
            {"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "low"}
        )
        mock_user = MagicMock()
        mock_user.uname = "analyst"

        with pytest.raises(InvalidDataException):
            case_service.update_case("case-001", {"updated": "2024-01-01T00:00:00Z"}, mock_user)

    @patch("howler.services.case_service.datastore")
    def test_update_case_raises_invalid_for_items_field(self, mock_ds_fn):
        """update_case accepts 'items' as a compound field (not immutable) and does not raise."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.get_if_exists.return_value = Case(
            {"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "low"}
        )
        mock_user = MagicMock()
        mock_user.uname = "analyst"

        # items is now a compound field — update must succeed without raising
        result = case_service.update_case("case-001", {"items": []}, mock_user)
        assert result is not None
        mock_ds.case.save.assert_called_once()

    @patch("howler.services.case_service.datastore")
    def test_update_case_raises_invalid_when_no_updatable_fields(self, mock_ds_fn):
        """update_case raises InvalidDataException when the update dict is empty."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.get_if_exists.return_value = Case(
            {"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "low"}
        )
        mock_user = MagicMock()
        mock_user.uname = "analyst"

        with pytest.raises(InvalidDataException):
            case_service.update_case("case-001", {}, mock_user)


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

        mock_ds.case.stream_search.return_value = iter([])

        case_obj = MagicMock()
        case_obj.items = []
        mock_ds.case.get_if_exists.return_value = case_obj

        case_service.hide_cases({"case-001"}, user="analyst")

        mock_ds.case.get_if_exists.assert_called_with("case-001", as_obj=True)
        assert case_obj.visible is False
        mock_ds.case.save.assert_called_with("case-001", case_obj)

    @patch("howler.services.case_service.datastore")
    def test_hide_cases_marks_related_items_not_visible(self, mock_ds_fn):
        """Items in other cases that reference a hidden case ID get visible=False."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        # stream_search returns a related case that is NOT in the hidden set
        mock_ds.case.stream_search.return_value = iter([{"case_id": "case-other"}])

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

        mock_ds.case.get_if_exists.side_effect = lambda case_id, as_obj=False: (
            related_case_obj if case_id == "case-other" else target_case_obj
        )

        case_service.hide_cases({"case-001"}, user="analyst")

        # The matching item's visible flag must be set to False
        assert related_item.visible is False
        # The unrelated item must be untouched
        assert unrelated_item.visible is True
        # The related case must be saved with the update
        mock_ds.case.save.assert_any_call("case-other", related_case_obj)
        # A log entry must have been appended to the related case documenting the hidden reference
        related_case_obj.log.append.assert_called_once()
        appended_log = related_case_obj.log.append.call_args[0][0]
        assert "case-001" in appended_log.explanation

    @patch("howler.services.case_service.datastore")
    def test_hide_cases_does_not_save_related_case_when_no_items_match(self, mock_ds_fn):
        """hide_cases does NOT save a related case when none of its items match the hidden IDs."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        # stream_search returns a case whose items don't actually match (stale index)
        mock_ds.case.stream_search.return_value = iter([{"case_id": "case-other"}])

        non_matching_item = MagicMock()
        non_matching_item.id = "unrelated-id"

        related_case_obj = MagicMock()
        related_case_obj.items = [non_matching_item]

        target_case_obj = MagicMock()
        target_case_obj.items = []

        mock_ds.case.get_if_exists.side_effect = lambda case_id, as_obj=False: (
            related_case_obj if case_id == "case-other" else target_case_obj
        )

        case_service.hide_cases(["case-001"], user="analyst")

        # No matching items → related case must NOT be saved
        saved_ids = [call[0][0] for call in mock_ds.case.save.call_args_list]
        assert "case-other" not in saved_ids
        # The target case itself must still be saved
        assert "case-001" in saved_ids

    @patch("howler.services.case_service.datastore")
    def test_hide_cases_skips_case_that_is_itself_being_hidden(self, mock_ds_fn):
        """stream_search results whose case_id is in the hidden set are skipped."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        # stream_search returns the case being hidden itself
        mock_ds.case.stream_search.return_value = iter([{"case_id": "case-001"}])

        case_obj = MagicMock()
        case_obj.items = []
        mock_ds.case.get_if_exists.return_value = case_obj

        case_service.hide_cases({"case-001"}, user="analyst")

        # stream_search returned "case-001" but the loop must have skipped it (continue).
        # The only get_if_exists call should be from the direct hide loop that runs afterwards.
        mock_ds.case.get_if_exists.assert_called_once_with("case-001", as_obj=True)

    @patch("howler.services.case_service.logger")
    @patch("howler.services.case_service.datastore")
    def test_hide_cases_logs_warning_when_case_not_found(self, mock_ds_fn, mock_logger):
        """hide_cases logs a warning when a target case_id does not exist."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_ds.case.stream_search.return_value = iter([])
        mock_ds.case.get_if_exists.return_value = None

        case_service.hide_cases({"case-missing"}, user="analyst")

        mock_logger.warning.assert_called_once()
        warning_msg = mock_logger.warning.call_args[0][0]
        assert "case-missing" in warning_msg

    @patch("howler.services.case_service.datastore")
    def test_hide_cases_multiple_ids(self, mock_ds_fn):
        """hide_cases processes all supplied case IDs."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_ds.case.stream_search.return_value = iter([])

        case_a = MagicMock()
        case_a.items = []
        case_b = MagicMock()
        case_b.items = []

        mock_ds.case.get_if_exists.side_effect = lambda case_id, as_obj=False: case_a if case_id == "case-a" else case_b

        case_service.hide_cases({"case-a", "case-b"}, user="analyst")

        assert case_a.visible is False
        assert case_b.visible is False
        assert mock_ds.case.save.call_count == 2

    @patch("howler.services.case_service.datastore")
    def test_hide_cases_appends_log_to_hidden_case(self, mock_ds_fn):
        """hide_cases appends a CaseLog entry to each hidden case."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_ds.case.stream_search.return_value = iter([])

        case_obj = MagicMock()
        case_obj.items = []
        case_obj.log = []  # use a real list so append actually works
        mock_ds.case.get_if_exists.return_value = case_obj

        case_service.hide_cases({"case-001"}, user="admin")

        assert len(case_obj.log) == 1
        assert case_obj.log[0].user == "admin"
        assert "hidden" in case_obj.log[0].explanation.lower()


# ---------------------------------------------------------------------------
# delete_cases()
# ---------------------------------------------------------------------------


class TestDeleteCases:
    """Tests for case_service.delete_cases."""

    @patch("howler.services.case_service.datastore")
    def test_delete_cases_calls_delete_by_query(self, mock_ds_fn):
        """delete_cases calls delete_by_query with a query covering all supplied case IDs."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.stream_search.return_value = iter([])

        case_service.delete_cases({"case-del"})

        mock_ds.case.delete_by_query.assert_called_once_with("case_id:(case-del)")

    @patch("howler.services.case_service.datastore")
    def test_delete_cases_removes_cross_case_item_references(self, mock_ds_fn):
        """delete_cases removes CaseItem entries that reference a deleted case from other cases."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.stream_search.return_value = iter([{"case_id": "case-other"}])

        matching_item = MagicMock()
        matching_item.id = "case-del"
        unrelated_item = MagicMock()
        unrelated_item.id = "other-id"

        related_case = MagicMock()
        related_case.items = [matching_item, unrelated_item]
        mock_ds.case.get_if_exists.return_value = related_case

        case_service.delete_cases({"case-del"})

        assert len(related_case.items) == 1
        assert related_case.items[0].id == "other-id"
        mock_ds.case.save.assert_called_once_with("case-other", related_case)

    @patch("howler.services.case_service.datastore")
    def test_delete_cases_skips_stream_results_in_delete_set(self, mock_ds_fn):
        """delete_cases does not attempt cross-reference cleanup on cases being deleted."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        # stream_search returns the very case being deleted
        mock_ds.case.stream_search.return_value = iter([{"case_id": "case-del"}])

        case_service.delete_cases({"case-del"})

        # The skip (continue) must prevent get_if_exists from being called
        mock_ds.case.get_if_exists.assert_not_called()

    @patch("howler.services.case_service.datastore")
    def test_delete_cases_returns_delete_by_query_result(self, mock_ds_fn):
        """delete_cases returns the boolean result of delete_by_query."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.stream_search.return_value = iter([])
        mock_ds.case.delete_by_query.return_value = True

        result = case_service.delete_cases({"case-del"})

        assert result is True
