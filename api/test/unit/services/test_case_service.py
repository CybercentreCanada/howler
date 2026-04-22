from unittest.mock import MagicMock, patch

import pytest

from howler.common.exceptions import InvalidDataException, NotFoundException
from howler.odm.models.case import Case, CaseItem, CaseRule
from howler.odm.models.ecs.related import Related
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
    def test_create_case_returns_odm(self, mock_ds_fn):
        """create_case returns the created case as a plain dict."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        result = case_service.create_case({"title": "Title", "summary": "Summary"}, user="admin")

        assert isinstance(result, Case)
        assert result.title == "Title"
        assert result.summary == "Summary"
        assert result.case_id

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

    @patch("howler.services.case_service.datastore")
    def test_create_case_raises_when_none_data(self, mock_ds_fn):
        """create_case raises InvalidDataException when case data is None."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        with pytest.raises(InvalidDataException):
            case_service.create_case(None)  # type: ignore[arg-type]

        mock_ds.case.save.assert_not_called()

    @patch("howler.services.case_service.datastore")
    def test_create_case_strips_case_id(self, mock_ds_fn):
        """create_case ignores any case_id supplied in the input dict."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        result = case_service.create_case({"case_id": "should-be-removed", "title": "T", "summary": "S"}, user="admin")

        assert result["case_id"] != "should-be-removed"


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
        mock_ds.case.get.return_value = None

        mock_user = MagicMock()
        mock_user.uname = "analyst"

        with pytest.raises(NotFoundException):
            case_service.update_case("case-missing", {"title": "Updated"}, mock_user)

    @patch("howler.services.case_service.datastore")
    def test_update_case_raises_invalid_data_for_immutable_field(self, mock_ds_fn):
        """update_case raises InvalidDataException when an immutable field is supplied."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.get.return_value = Case(
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
        mock_ds.case.get.return_value = Case(
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
        mock_ds.case.get.return_value = Case(
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
        mock_ds.case.get.return_value = Case(
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
        mock_ds.case.get.return_value = Case(
            {"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "low"}
        )
        mock_user = MagicMock()
        mock_user.uname = "analyst"

        with pytest.raises(InvalidDataException):
            case_service.update_case("case-001", {}, mock_user)

    @patch("howler.services.case_service.datastore")
    def test_update_case_list_field_logs_diff(self, mock_ds_fn):
        """update_case logs added/removed entries when a list field is changed."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.get.return_value = Case(
            {
                "case_id": "case-001",
                "title": "T",
                "summary": "S",
                "overview": "O",
                "escalation": "low",
                "targets": ["host-a", "host-b"],
            }
        )
        mock_user = MagicMock()
        mock_user.uname = "analyst"

        result = case_service.update_case("case-001", {"targets": ["host-a"]}, mock_user)

        log_explanations = [entry.explanation for entry in result.log]
        assert any("removed" in e for e in log_explanations)

    @pytest.mark.parametrize("field", ["case_id", "created", "updated"])
    @patch("howler.services.case_service.datastore")
    def test_update_case_raises_for_all_immutable_fields(self, mock_ds_fn, field):
        """update_case raises InvalidDataException for every immutable field."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.get.return_value = Case(
            {"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "low"}
        )
        mock_user = MagicMock()
        mock_user.uname = "analyst"

        with pytest.raises(InvalidDataException, match="immutable"):
            case_service.update_case("case-001", {field: "x"}, mock_user)


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
        mock_ds.case.get.return_value = case_obj

        case_service.hide_cases({"case-001"}, user="analyst")

        mock_ds.case.get.assert_called_with("case-001")
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
        related_item.value = "case-001"
        related_item.visible = True

        unrelated_item = MagicMock()
        unrelated_item.value = "something-else"
        unrelated_item.visible = True

        related_case_obj = MagicMock()
        related_case_obj.items = [related_item, unrelated_item]

        # The target case itself
        target_case_obj = MagicMock()
        target_case_obj.items = []

        mock_ds.case.get.side_effect = lambda case_id, as_obj=False: (
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
        non_matching_item.value = "unrelated-id"

        related_case_obj = MagicMock()
        related_case_obj.items = [non_matching_item]

        target_case_obj = MagicMock()
        target_case_obj.items = []

        mock_ds.case.get.side_effect = lambda case_id, as_obj=False: (
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
        mock_ds.case.get.return_value = case_obj

        case_service.hide_cases({"case-001"}, user="analyst")

        # stream_search returned "case-001" but the loop must have skipped it (continue).
        # The only get call should be from the direct hide loop that runs afterwards.
        mock_ds.case.get.assert_called_once_with("case-001")

    @patch("howler.services.case_service.logger")
    @patch("howler.services.case_service.datastore")
    def test_hide_cases_logs_warning_when_case_not_found(self, mock_ds_fn, mock_logger):
        """hide_cases logs a warning when a target case_id does not exist."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_ds.case.stream_search.return_value = iter([])
        mock_ds.case.get.return_value = None

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

        mock_ds.case.get.side_effect = lambda case_id, as_obj=False: case_a if case_id == "case-a" else case_b

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
        mock_ds.case.get.return_value = case_obj

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
        matching_item.value = "case-del"
        unrelated_item = MagicMock()
        unrelated_item.value = "other-id"

        related_case = MagicMock()
        related_case.items = [matching_item, unrelated_item]
        mock_ds.case.get.return_value = related_case

        case_service.delete_cases({"case-del"})

        assert len(related_case.items) == 1
        assert related_case.items[0].value == "other-id"
        mock_ds.case.save.assert_called_once_with("case-other", related_case)

    @patch("howler.services.case_service.datastore")
    def test_delete_cases_skips_stream_results_in_delete_set(self, mock_ds_fn):
        """delete_cases does not attempt cross-reference cleanup on cases being deleted."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        # stream_search returns the very case being deleted
        mock_ds.case.stream_search.return_value = iter([{"case_id": "case-del"}])

        case_service.delete_cases({"case-del"})

        # The skip (continue) must prevent get from being called
        mock_ds.case.get.assert_not_called()

    @patch("howler.services.case_service.datastore")
    def test_delete_cases_returns_delete_by_query_result(self, mock_ds_fn):
        """delete_cases returns the boolean result of delete_by_query."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.stream_search.return_value = iter([])
        mock_ds.case.delete_by_query.return_value = True

        result = case_service.delete_cases({"case-del"})

        assert result is True


# ---------------------------------------------------------------------------
# append_case_item() routing
# ---------------------------------------------------------------------------


class TestAppendCaseItemRouting:
    """Tests for the append_case_item dispatcher."""

    @patch("howler.services.case_service.datastore")
    def test_append_case_item_requires_type_and_value(self, mock_ds_fn):
        """append_case_item raises InvalidDataException when item_type or item_value is missing."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        with pytest.raises(InvalidDataException):
            case_service.append_case_item("case-001", item_type="hit")

        with pytest.raises(InvalidDataException):
            case_service.append_case_item("case-001", item_value="some-id")

    @patch("howler.services.case_service.datastore")
    def test_append_case_item_invalid_type_raises(self, mock_ds_fn):
        """append_case_item raises InvalidDataException when item_type is unrecognized."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        with pytest.raises(InvalidDataException):
            case_service.append_case_item("case-001", item_type="unicorn", item_value="some-id")

    @pytest.mark.parametrize("item_type", ["table", "lead"])
    @patch("howler.services.case_service.datastore")
    def test_append_not_implemented_types_raise(self, mock_ds_fn, item_type):
        """append_case_item raises NotImplementedError for table/lead/reference item types."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        item = CaseItem({"type": item_type, "value": "x", "path": "misc"})
        with pytest.raises(NotImplementedError):
            case_service.append_case_item("case-001", item=item)

    @patch("howler.services.case_service.datastore")
    def test_append_case_item_raises_if_item_path_ends_with_slash(self, mock_ds_fn):
        """append_case_item raises InvalidDataException when the pre-built item's path ends with '/'."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        item = CaseItem({"type": "hit", "value": "hit-001", "path": "alerts/"})
        with pytest.raises(InvalidDataException, match="trailing"):
            case_service.append_case_item("case-001", item=item)

    @patch("howler.services.case_service.datastore")
    def test_append_case_item_raises_if_item_type_path_ends_with_slash(self, mock_ds_fn):
        """append_case_item raises InvalidDataException when item_path param ends with '/'."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        with pytest.raises(InvalidDataException, match="trailing"):
            case_service.append_case_item("case-001", item_type="hit", item_value="hit-001", item_path="alerts/")


# ---------------------------------------------------------------------------
# append_hit()
# ---------------------------------------------------------------------------


class TestAppendHit:
    """Tests for case_service.append_hit."""

    @patch("howler.services.case_service._sync_case_metadata")
    @patch("howler.services.case_service._add_backreference")
    @patch("howler.services.case_service.datastore")
    def test_append_hit_adds_item(self, mock_ds_fn, mock_backref, mock_sync):
        """append_hit appends the item to the case and delegates save to _sync_case_metadata."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_case = MagicMock()
        mock_case.case_id = "case-001"
        mock_case.items = []
        mock_ds.case.get.return_value = mock_case

        mock_hit = MagicMock()
        mock_ds.hit.get.return_value = mock_hit

        item = CaseItem({"type": "hit", "value": "hit-001", "path": "related/"})
        case_service.append_hit("case-001", item)

        assert len(mock_case.items) == 1
        mock_backref.assert_called_once_with(mock_hit, "case-001")
        mock_sync.assert_called_once_with("case-001")

    @patch("howler.services.case_service._sync_case_metadata")
    @patch("howler.services.case_service._add_backreference")
    @patch("howler.services.case_service.datastore")
    def test_append_hit_preserves_path(self, mock_ds_fn, mock_backref, mock_sync):
        """append_hit preserves the item path as-is without any manipulation."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_case = MagicMock()
        mock_case.case_id = "case-001"
        mock_case.items = []
        mock_ds.case.get.return_value = mock_case

        mock_hit = MagicMock()
        mock_ds.hit.get.return_value = mock_hit

        item = CaseItem({"type": "hit", "value": "hit-001", "path": "related/"})
        case_service.append_hit("case-001", item)

        assert item.path == "related/"

    @patch("howler.services.case_service.datastore")
    def test_append_hit_missing_case_raises(self, mock_ds_fn):
        """append_hit raises NotFoundException when the case does not exist."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.get.return_value = None

        item = CaseItem({"type": "hit", "value": "hit-001", "path": "related/"})
        with pytest.raises(NotFoundException):
            case_service.append_hit("nonexistent-case", item)

    @patch("howler.services.case_service.datastore")
    def test_append_hit_missing_hit_raises(self, mock_ds_fn):
        """append_hit raises NotFoundException when the hit does not exist."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_case = MagicMock()
        mock_case.items = []
        mock_ds.case.get.return_value = mock_case
        mock_ds.hit.get.return_value = None

        item = CaseItem({"type": "hit", "value": "nonexistent-hit", "path": "related/"})
        with pytest.raises(NotFoundException):
            case_service.append_hit("case-001", item)

        # Case must NOT have been saved when the hit doesn't exist.
        mock_ds.case.save.assert_not_called()

    @patch("howler.services.case_service.datastore")
    def test_append_hit_duplicate_raises(self, mock_ds_fn):
        """append_hit raises InvalidDataException when the hit is already in the case."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        existing = CaseItem({"type": "hit", "value": "hit-001", "path": "alerts/test"})
        mock_case = MagicMock()
        mock_case.items = [existing]
        mock_ds.case.get.return_value = mock_case

        item = CaseItem({"type": "hit", "value": "hit-001", "path": "related/"})
        with pytest.raises(InvalidDataException):
            case_service.append_hit("case-001", item)


# ---------------------------------------------------------------------------
# append_observable()
# ---------------------------------------------------------------------------


class TestAppendObservable:
    """Tests for case_service.append_observable."""

    @patch("howler.services.case_service._sync_case_metadata")
    @patch("howler.services.case_service._add_backreference")
    @patch("howler.services.case_service.datastore")
    def test_append_observable_adds_item(self, mock_ds_fn, mock_backref, mock_sync):
        """append_observable appends the item to the case and saves."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_case = MagicMock()
        mock_case.case_id = "case-001"
        mock_case.items = []
        mock_ds.case.get.return_value = mock_case
        mock_ds.case.save.return_value = True

        mock_obs = MagicMock()
        mock_obs.howler.id = "obs-001"
        mock_ds.observable.get.return_value = mock_obs

        item = CaseItem({"type": "observable", "value": "obs-001", "path": "related/"})
        case_service.append_observable("case-001", item)

        mock_ds.case.save.assert_called_once()
        assert len(mock_case.items) == 1
        mock_backref.assert_called_once_with(mock_obs, "case-001")
        mock_sync.assert_called_once_with("case-001")

    @patch("howler.services.case_service.datastore")
    def test_append_observable_missing_case_raises(self, mock_ds_fn):
        """append_observable raises NotFoundException when the case does not exist."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.get.return_value = None

        item = CaseItem({"type": "observable", "value": "obs-001", "path": "related/"})
        with pytest.raises(NotFoundException):
            case_service.append_observable("nonexistent-case", item)

    @patch("howler.services.case_service.datastore")
    def test_append_observable_missing_observable_raises(self, mock_ds_fn):
        """append_observable raises NotFoundException when the observable does not exist."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_case = MagicMock()
        mock_case.items = []
        mock_ds.case.get.return_value = mock_case
        mock_ds.observable.get.return_value = None

        item = CaseItem({"type": "observable", "value": "nonexistent-obs", "path": "related/"})
        with pytest.raises(NotFoundException):
            case_service.append_observable("case-001", item)

    @patch("howler.services.case_service.datastore")
    def test_append_observable_duplicate_raises(self, mock_ds_fn):
        """append_observable raises InvalidDataException when the observable is already in the case."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        existing = CaseItem({"type": "observable", "value": "obs-001", "path": "observables/obs-001"})
        mock_case = MagicMock()
        mock_case.items = [existing]
        mock_ds.case.get.return_value = mock_case

        item = CaseItem({"type": "observable", "value": "obs-001", "path": "related/"})
        with pytest.raises(InvalidDataException):
            case_service.append_observable("case-001", item)


# ---------------------------------------------------------------------------
# append_case()
# ---------------------------------------------------------------------------


class TestAppendCase:
    """Tests for case_service.append_case."""

    @patch("howler.services.case_service.datastore")
    def test_append_case_adds_item(self, mock_ds_fn):
        """append_case appends a case reference item and saves the parent case."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_parent = MagicMock()
        mock_parent.case_id = "parent-001"
        mock_parent.items = []

        mock_child = MagicMock()
        mock_child.case_id = "child-001"

        mock_ds.case.get.side_effect = lambda key, as_obj=False: mock_parent if key == "parent-001" else mock_child
        mock_ds.case.save.return_value = True

        item = CaseItem({"type": "case", "value": "child-001", "path": "related/child-001"})
        case_service.append_case("parent-001", item)

        mock_ds.case.save.assert_called_once()
        assert len(mock_parent.items) == 1
        assert "child-001" in item.path

    @patch("howler.services.case_service.datastore")
    def test_append_case_missing_parent_raises(self, mock_ds_fn):
        """append_case raises NotFoundException when the parent case does not exist."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.get.return_value = None

        item = CaseItem({"type": "case", "value": "child-001", "path": "related/"})
        with pytest.raises(NotFoundException):
            case_service.append_case("nonexistent-parent", item)

    @patch("howler.services.case_service.datastore")
    def test_append_case_missing_referenced_case_raises(self, mock_ds_fn):
        """append_case raises NotFoundException when the referenced case does not exist."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_parent = MagicMock()
        mock_parent.items = []

        mock_ds.case.get.side_effect = lambda key, as_obj=False: mock_parent if key == "parent-001" else None

        item = CaseItem({"type": "case", "value": "nonexistent-child", "path": "related/"})
        with pytest.raises(NotFoundException):
            case_service.append_case("parent-001", item)

    @patch("howler.services.case_service.datastore")
    def test_append_case_duplicate_raises(self, mock_ds_fn):
        """append_case raises InvalidDataException when the reference already exists."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        existing = CaseItem({"type": "case", "value": "child-001", "path": "cases/child-001"})
        mock_parent = MagicMock()
        mock_parent.items = [existing]
        mock_ds.case.get.return_value = mock_parent

        item = CaseItem({"type": "case", "value": "child-001", "path": "related/"})
        with pytest.raises(InvalidDataException):
            case_service.append_case("parent-001", item)


# ---------------------------------------------------------------------------
# remove_case_item()
# ---------------------------------------------------------------------------


class TestRemoveCaseItem:
    """Tests for case_service.remove_case_item."""

    @patch("howler.services.case_service.datastore")
    def test_remove_case_item_raises_not_found_for_missing_case(self, mock_ds_fn):
        """remove_case_item raises NotFoundException when the case does not exist."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.get.return_value = None

        with pytest.raises(NotFoundException):
            case_service.remove_case_items("nonexistent-case", ["some-value"])

    @patch("howler.services.case_service.datastore")
    def test_remove_case_item_raises_not_found_for_missing_item(self, mock_ds_fn):
        """remove_case_item raises NotFoundException when the item value is not in the case."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_case = MagicMock()
        mock_case.items = [CaseItem({"type": "hit", "value": "other-id", "path": "alerts/x"})]
        mock_ds.case.get.return_value = mock_case

        with pytest.raises(NotFoundException):
            case_service.remove_case_items("case-001", ["nonexistent-item-value"])

    @patch("howler.services.case_service._sync_case_metadata")
    @patch("howler.services.case_service.datastore")
    def test_remove_hit_item_clears_backreference(self, mock_ds_fn, mock_sync):
        """remove_case_item removes the item from the case and removes the hit back-reference."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        hit_item = CaseItem({"type": "hit", "value": "hit-001", "path": "alerts/test"})

        mock_case = MagicMock()
        mock_case.case_id = "case-001"
        mock_case.items = [hit_item]
        mock_ds.case.get.return_value = mock_case
        mock_ds.case.save.return_value = True

        mock_hit = MagicMock()
        mock_hit.howler.related = ["case-001"]
        mock_ds.hit.get.return_value = mock_hit

        case_service.remove_case_items("case-001", ["hit-001"])

        assert hit_item not in mock_case.items
        mock_ds.case.save.assert_called_once()
        mock_sync.assert_called_once_with("case-001")

    @patch("howler.services.case_service._sync_case_metadata")
    @patch("howler.services.case_service.datastore")
    def test_remove_observable_item_clears_backreference(self, mock_ds_fn, mock_sync):
        """remove_case_item removes an observable item from the case."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        obs_item = CaseItem({"type": "observable", "value": "obs-001", "path": "observables/obs-001"})

        mock_case = MagicMock()
        mock_case.case_id = "case-001"
        mock_case.items = [obs_item]
        mock_ds.case.get.return_value = mock_case
        mock_ds.case.save.return_value = True

        mock_obs = MagicMock()
        mock_obs.howler.related = ["case-001"]
        mock_ds.observable.get.return_value = mock_obs

        case_service.remove_case_items("case-001", ["obs-001"])

        assert obs_item not in mock_case.items
        mock_ds.case.save.assert_called_once()
        mock_sync.assert_called_once_with("case-001")


# ---------------------------------------------------------------------------
# rename_case_item()
# ---------------------------------------------------------------------------


class TestRenameCaseItem:
    """Tests for case_service.rename_case_item."""

    @patch("howler.services.case_service.datastore")
    def test_rename_item_success(self, mock_ds_fn):
        """Updates the item path and saves the case once."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        item = CaseItem({"type": "hit", "value": "hit-001", "path": "folder/Old Name"})
        mock_case = MagicMock()
        mock_case.case_id = "case-001"
        mock_case.items = [item]
        mock_ds.case.get.return_value = mock_case
        mock_ds.case.save.return_value = True

        result = case_service.rename_case_item("case-001", "hit-001", "folder/New Name")

        assert item.path == "folder/New Name"
        mock_ds.case.save.assert_called_once_with("case-001", mock_case)
        assert result is mock_case

    @patch("howler.services.case_service.datastore")
    def test_rename_item_raises_not_found_for_missing_case(self, mock_ds_fn):
        """Raises NotFoundException when the case does not exist."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.get.return_value = None

        with pytest.raises(NotFoundException):
            case_service.rename_case_item("nonexistent", "hit-001", "folder/New Name")

        mock_ds.case.save.assert_not_called()

    @patch("howler.services.case_service.datastore")
    def test_rename_item_raises_not_found_for_missing_item(self, mock_ds_fn):
        """Raises NotFoundException when the item value is not in the case."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_case = MagicMock()
        mock_case.items = [CaseItem({"type": "hit", "value": "other-id", "path": "folder/x"})]
        mock_ds.case.get.return_value = mock_case

        with pytest.raises(NotFoundException):
            case_service.rename_case_item("case-001", "hit-001", "folder/New Name")

        mock_ds.case.save.assert_not_called()

    @patch("howler.services.case_service.datastore")
    def test_rename_item_raises_invalid_data_when_path_taken(self, mock_ds_fn):
        """Raises InvalidDataException when new_path is already used by another item."""
        from howler.common.exceptions import InvalidDataException

        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        item_a = CaseItem({"type": "hit", "value": "hit-001", "path": "folder/A"})
        item_b = CaseItem({"type": "hit", "value": "hit-002", "path": "folder/B"})
        mock_case = MagicMock()
        mock_case.items = [item_a, item_b]
        mock_ds.case.get.return_value = mock_case

        with pytest.raises(InvalidDataException):
            case_service.rename_case_item("case-001", "hit-001", "folder/B")

        mock_ds.case.save.assert_not_called()

    def test_rename_item_raises_invalid_data_for_trailing_slash(self):
        """Raises InvalidDataException without touching the datastore for a bad path."""
        from howler.common.exceptions import InvalidDataException

        with pytest.raises(InvalidDataException):
            case_service.rename_case_item("case-001", "hit-001", "folder/")

    def test_rename_item_raises_invalid_data_for_empty_path(self):
        """Raises InvalidDataException for an empty new_path."""
        from howler.common.exceptions import InvalidDataException

        with pytest.raises(InvalidDataException):
            case_service.rename_case_item("case-001", "hit-001", "")

    @patch("howler.services.case_service.datastore")
    def test_rename_item_raises_datastore_error_on_save_failure(self, mock_ds_fn):
        """Raises DataStoreException when ds.case.save returns False."""
        from howler.datastore.exceptions import DataStoreException

        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        item = CaseItem({"type": "hit", "value": "hit-001", "path": "folder/Old Name"})
        mock_case = MagicMock()
        mock_case.case_id = "case-001"
        mock_case.items = [item]
        mock_ds.case.get.return_value = mock_case
        mock_ds.case.save.return_value = False

        with pytest.raises(DataStoreException):
            case_service.rename_case_item("case-001", "hit-001", "folder/New Name")

    @patch("howler.services.case_service.datastore")
    def test_rename_item_allows_same_path_on_same_item(self, mock_ds_fn):
        """Renaming an item to its current path is allowed (no conflict with itself)."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        item = CaseItem({"type": "hit", "value": "hit-001", "path": "folder/Same"})
        mock_case = MagicMock()
        mock_case.case_id = "case-001"
        mock_case.items = [item]
        mock_ds.case.get.return_value = mock_case
        mock_ds.case.save.return_value = True

        case_service.rename_case_item("case-001", "hit-001", "folder/Same")

        mock_ds.case.save.assert_called_once()


# ---------------------------------------------------------------------------
# _collect_indicators_from_related()
# ---------------------------------------------------------------------------


class TestCollectIndicatorsFromRelated:
    """Tests for case_service._collect_indicators_from_related."""

    def test_collect_indicators_from_related_none(self):
        """Returns an empty set when related is None."""
        assert case_service._collect_indicators_from_related(None) == set()

    def test_collect_indicators_from_related_values(self):
        """Collects all non-empty values across all fields of a Related object."""
        related = Related(
            {
                "hash": ["abc123"],
                "hosts": ["host-a", "host-b"],
                "ip": ["1.2.3.4"],
                "user": [],
            }
        )

        result = case_service._collect_indicators_from_related(related)
        assert "abc123" in result
        assert "host-a" in result
        assert "host-b" in result
        assert "1.2.3.4" in result


# ---------------------------------------------------------------------------
# _sync_case_metadata()
# ---------------------------------------------------------------------------


class TestSyncCaseMetadata:
    """Tests for case_service._sync_case_metadata."""

    @patch("howler.services.case_service.datastore")
    def test_sync_case_metadata_noop_on_missing_case(self, mock_ds_fn):
        """_sync_case_metadata does nothing when the case does not exist."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.get.return_value = None

        case_service._sync_case_metadata("nonexistent-id")

        mock_ds.case.save.assert_not_called()

    @patch("howler.services.case_service.datastore")
    def test_sync_case_metadata_updates_from_hit_outline(self, mock_ds_fn):
        """_sync_case_metadata populates threats/targets/indicators from hit outline data."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        hit_item = CaseItem({"type": "hit", "value": "hit-001", "path": "alerts/test"})

        mock_case = MagicMock()
        mock_case.items = [hit_item]
        mock_ds.case.get.return_value = mock_case

        mock_outline = MagicMock()
        mock_outline.threat = "evil.example.com"
        mock_outline.target = "workstation-01"
        mock_outline.indicators = ["hash-abc"]

        mock_hit = MagicMock()
        mock_hit.related = None
        mock_hit.howler.outline = mock_outline
        mock_ds.hit.get.return_value = mock_hit

        case_service._sync_case_metadata("case-001")

        mock_ds.case.save.assert_called_once()
        assert mock_case.threats == ["evil.example.com"]
        assert mock_case.targets == ["workstation-01"]
        assert mock_case.indicators == ["hash-abc"]

    @patch("howler.services.case_service.datastore")
    def test_sync_case_metadata_clears_when_no_items(self, mock_ds_fn):
        """_sync_case_metadata resets threats/targets/indicators to empty lists when no items exist."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_case = MagicMock()
        mock_case.items = []
        mock_ds.case.get.return_value = mock_case

        case_service._sync_case_metadata("case-001")

        mock_ds.case.save.assert_called_once()
        assert mock_case.targets == []
        assert mock_case.threats == []
        assert mock_case.indicators == []


# ---------------------------------------------------------------------------
# _add_backreference()
# ---------------------------------------------------------------------------


class TestAddBackreference:
    """Tests for case_service._add_backreference."""

    def test_add_backreference_raises_on_none_object(self):
        """_add_backreference raises InvalidDataException when backing_obj is None."""
        with pytest.raises(InvalidDataException):
            case_service._add_backreference(None, "case-id")

    def test_add_backreference_raises_on_empty_case_id(self):
        """_add_backreference raises InvalidDataException when case_id is empty."""
        mock_obj = MagicMock()

        with pytest.raises(InvalidDataException):
            case_service._add_backreference(mock_obj, "")

    @patch("howler.services.case_service.datastore")
    def test_add_backreference_appends_and_saves(self, mock_ds_fn):
        """_add_backreference appends the case_id to related and saves the object."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_obj = MagicMock()
        mock_obj.howler.related = []
        mock_obj.howler.id = "obj-001"

        case_service._add_backreference(mock_obj, "case-abc")

        assert "case-abc" in mock_obj.howler.related
        mock_ds.__getitem__.return_value.save.assert_called_once()

    @patch("howler.services.case_service.datastore")
    def test_add_backreference_is_idempotent(self, mock_ds_fn):
        """_add_backreference does not add a duplicate if the case_id is already present."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_obj = MagicMock()
        mock_obj.howler.related = ["case-abc"]
        mock_obj.howler.id = "obj-001"

        case_service._add_backreference(mock_obj, "case-abc")

        assert mock_obj.howler.related.count("case-abc") == 1
        mock_ds.__getitem__.return_value.save.assert_not_called()


# ---------------------------------------------------------------------------
# remove_backreference()
# ---------------------------------------------------------------------------


class TestRemoveBackreference:
    """Tests for case_service.remove_backreference."""

    def test_remove_backreference_raises_on_none_object(self):
        """remove_backreference raises InvalidDataException when backing_obj is None."""
        with pytest.raises(InvalidDataException):
            case_service.remove_backreference(None, "case-id")

    @patch("howler.services.case_service.datastore")
    def test_remove_backreference_noop_when_not_present(self, mock_ds_fn):
        """remove_backreference does nothing when case_id is not in related."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_obj = MagicMock()
        mock_obj.howler.related = ["other-case"]

        case_service.remove_backreference(mock_obj, "case-that-was-never-added")

        assert "other-case" in mock_obj.howler.related
        mock_ds.__getitem__.return_value.save.assert_not_called()

    @patch("howler.services.case_service.datastore")
    def test_remove_backreference_removes_and_saves(self, mock_ds_fn):
        """remove_backreference removes the case_id from related and saves."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_obj = MagicMock()
        mock_obj.howler.related = ["case-abc", "other-case"]
        mock_obj.howler.id = "obj-001"

        case_service.remove_backreference(mock_obj, "case-abc")

        assert "case-abc" not in mock_obj.howler.related
        assert "other-case" in mock_obj.howler.related
        mock_ds.__getitem__.return_value.save.assert_called_once()


# ---------------------------------------------------------------------------
# Event emission on case mutations
# ---------------------------------------------------------------------------


class TestCaseEventEmission:
    """Tests that case mutations emit 'cases' events via event_service."""

    @patch("howler.services.case_service.event_service")
    @patch("howler.services.case_service.datastore")
    def test_update_case_emits_event(self, mock_ds_fn, mock_events):
        """update_case emits a 'cases' event containing the updated case primitives."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.get.return_value = Case(
            {"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "low"}
        )

        mock_user = MagicMock()
        mock_user.uname = "analyst"

        case_service.update_case("case-001", {"title": "New"}, mock_user)

        mock_events.emit.assert_called_once()
        args = mock_events.emit.call_args
        assert args[0][0] == "cases"
        assert "case" in args[0][1]
        assert args[0][1]["case"]["title"] == "New"

    @patch("howler.services.case_service.event_service")
    @patch("howler.services.case_service.datastore")
    def test_create_case_emits_event(self, mock_ds_fn, mock_events):
        """create_case emits a 'cases' event with the new case."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        case_service.create_case({"title": "New", "summary": "S"}, user="admin")

        mock_events.emit.assert_called_once()
        args = mock_events.emit.call_args
        assert args[0][0] == "cases"
        assert "case" in args[0][1]
        assert args[0][1]["case"]["title"] == "New"

    @patch("howler.services.case_service._sync_case_metadata")
    @patch("howler.services.case_service.event_service")
    @patch("howler.services.case_service.datastore")
    def test_append_hit_emits_event(self, mock_ds_fn, mock_events, mock_sync):
        """append_hit emits a 'cases' event after adding a hit."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_case = Case({"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "low"})
        mock_hit = MagicMock()
        mock_hit.howler.related = []
        mock_hit.howler.id = "hit-001"

        mock_ds.case.get.return_value = mock_case
        mock_ds.hit.get.return_value = mock_hit
        mock_ds.case.save.return_value = True

        item = CaseItem({"type": "hit", "value": "hit-001", "path": "alerts/test"})
        case_service.append_hit("case-001", item)

        mock_events.emit.assert_called_once()
        args = mock_events.emit.call_args
        assert args[0][0] == "cases"
        assert "case" in args[0][1]

    @patch("howler.services.case_service._sync_case_metadata")
    @patch("howler.services.case_service.event_service")
    @patch("howler.services.case_service.datastore")
    def test_append_hit_skips_emit_when_refetch_returns_none(self, mock_ds_fn, mock_events, mock_sync):
        """append_hit does not emit when the re-fetch returns None."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_case = Case({"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "low"})
        mock_hit = MagicMock()
        mock_hit.howler.related = []
        mock_hit.howler.id = "hit-001"

        # First get returns the case, second get (refetch) returns None
        mock_ds.case.get.side_effect = [mock_case, None]
        mock_ds.hit.get.return_value = mock_hit
        mock_ds.case.save.return_value = True

        item = CaseItem({"type": "hit", "value": "hit-001", "path": "alerts/test"})
        case_service.append_hit("case-001", item)

        mock_events.emit.assert_not_called()


# ---------------------------------------------------------------------------
# add_case_rule()
# ---------------------------------------------------------------------------


class TestAddCaseRule:
    """Tests for case_service.add_case_rule."""

    @patch("howler.services.case_service.event_service")
    @patch("howler.services.case_service.datastore")
    def test_add_rule_success(self, mock_ds_fn, mock_events):
        """add_case_rule appends a rule and saves the case."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_case = Case({"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "low"})
        mock_ds.case.get.return_value = mock_case

        user = MagicMock()
        user.uname = "analyst1"

        result = case_service.add_case_rule(
            "case-001",
            {"query": "event.kind:alert", "destination": "alerts/incoming"},
            user,
        )

        assert len(result.rules) == 1
        assert result.rules[0].query == "event.kind:alert"
        assert result.rules[0].destination == "alerts/incoming"
        assert result.rules[0].author == "analyst1"
        assert result.rules[0].enabled is True
        assert result.rules[0].rule_id is not None
        mock_ds.case.save.assert_called_once()

    @patch("howler.services.case_service.event_service")
    @patch("howler.services.case_service.datastore")
    def test_add_rule_with_timeframe(self, mock_ds_fn, mock_events):
        """add_case_rule stores the timeframe when provided."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_case = Case({"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "low"})
        mock_ds.case.get.return_value = mock_case

        user = MagicMock()
        user.uname = "analyst1"

        result = case_service.add_case_rule(
            "case-001",
            {"query": "*:*", "destination": "alerts/all", "timeframe": "2026-06-01T00:00:00Z"},
            user,
        )

        assert result.rules[0].timeframe is not None

    @patch("howler.services.case_service.datastore")
    def test_add_rule_case_not_found(self, mock_ds_fn):
        """add_case_rule raises NotFoundException when the case doesn't exist."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.get.return_value = None

        user = MagicMock()
        user.uname = "analyst1"

        with pytest.raises(NotFoundException):
            case_service.add_case_rule(
                "nonexistent",
                {"query": "*:*", "destination": "alerts/incoming"},
                user,
            )

    @patch("howler.services.case_service.datastore")
    def test_add_rule_missing_query(self, mock_ds_fn):
        """add_case_rule raises InvalidDataException when query is missing."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_case = Case({"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "low"})
        mock_ds.case.get.return_value = mock_case

        user = MagicMock()
        user.uname = "analyst1"

        with pytest.raises(InvalidDataException, match="query"):
            case_service.add_case_rule("case-001", {"destination": "alerts/incoming"}, user)

    @patch("howler.services.case_service.datastore")
    def test_add_rule_missing_destination(self, mock_ds_fn):
        """add_case_rule raises InvalidDataException when destination is missing."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_case = Case({"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "low"})
        mock_ds.case.get.return_value = mock_case

        user = MagicMock()
        user.uname = "analyst1"

        with pytest.raises(InvalidDataException, match="destination"):
            case_service.add_case_rule("case-001", {"query": "event.kind:alert"}, user)

    @patch("howler.services.case_service.event_service")
    @patch("howler.services.case_service.datastore")
    def test_add_rule_strips_client_rule_id(self, mock_ds_fn, mock_events):
        """add_case_rule ignores any 'id' provided by the client."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_case = Case({"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "low"})
        mock_ds.case.get.return_value = mock_case

        user = MagicMock()
        user.uname = "analyst1"

        result = case_service.add_case_rule(
            "case-001",
            {"query": "*:*", "destination": "alerts/all", "rule_id": "client-supplied-id"},
            user,
        )

        assert result.rules[0].rule_id != "client-supplied-id"


# ---------------------------------------------------------------------------
# remove_case_rule()
# ---------------------------------------------------------------------------


class TestRemoveCaseRule:
    """Tests for case_service.remove_case_rule."""

    @patch("howler.services.case_service.event_service")
    @patch("howler.services.case_service.datastore")
    def test_remove_rule_success(self, mock_ds_fn, mock_events):
        """remove_case_rule removes the rule and saves."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        rule = CaseRule({"query": "*:*", "destination": "alerts/all", "author": "admin"})
        mock_case = Case({"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "low"})
        mock_case.rules.append(rule)
        mock_ds.case.get.return_value = mock_case

        user = MagicMock()
        user.uname = "analyst1"

        result = case_service.remove_case_rule("case-001", rule.rule_id, user)

        assert len(result.rules) == 0
        mock_ds.case.save.assert_called_once()

    @patch("howler.services.case_service.datastore")
    def test_remove_rule_not_found(self, mock_ds_fn):
        """remove_case_rule raises NotFoundException when rule doesn't exist."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_case = Case({"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "low"})
        mock_ds.case.get.return_value = mock_case

        user = MagicMock()
        user.uname = "analyst1"

        with pytest.raises(NotFoundException, match="Rule"):
            case_service.remove_case_rule("case-001", "nonexistent-id", user)

    @patch("howler.services.case_service.datastore")
    def test_remove_rule_case_not_found(self, mock_ds_fn):
        """remove_case_rule raises NotFoundException when case doesn't exist."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.get.return_value = None

        user = MagicMock()
        user.uname = "analyst1"

        with pytest.raises(NotFoundException, match="Case"):
            case_service.remove_case_rule("nonexistent", "rule-id", user)


# ---------------------------------------------------------------------------
# update_case_rule()
# ---------------------------------------------------------------------------


class TestUpdateCaseRule:
    """Tests for case_service.update_case_rule."""

    @patch("howler.services.case_service.event_service")
    @patch("howler.services.case_service.datastore")
    def test_update_rule_toggle_enabled(self, mock_ds_fn, mock_events):
        """update_case_rule can toggle the enabled field."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        rule = CaseRule({"query": "*:*", "destination": "alerts/all", "author": "admin", "enabled": True})
        mock_case = Case({"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "low"})
        mock_case.rules.append(rule)
        mock_ds.case.get.return_value = mock_case

        user = MagicMock()
        user.uname = "analyst1"

        result = case_service.update_case_rule("case-001", rule.rule_id, {"enabled": False}, user)

        assert result.rules[0].enabled is False
        mock_ds.case.save.assert_called_once()

    @patch("howler.services.case_service.event_service")
    @patch("howler.services.case_service.datastore")
    def test_update_rule_change_query(self, mock_ds_fn, mock_events):
        """update_case_rule can update the query field."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        rule = CaseRule({"query": "old:query", "destination": "alerts/all", "author": "admin"})
        mock_case = Case({"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "low"})
        mock_case.rules.append(rule)
        mock_ds.case.get.return_value = mock_case

        user = MagicMock()
        user.uname = "analyst1"

        result = case_service.update_case_rule("case-001", rule.rule_id, {"query": "new:query"}, user)

        assert result.rules[0].query == "new:query"

    @patch("howler.services.case_service.datastore")
    def test_update_rule_no_valid_fields(self, mock_ds_fn):
        """update_case_rule raises InvalidDataException when no allowed fields are provided."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        rule = CaseRule({"query": "*:*", "destination": "alerts/all", "author": "admin"})
        mock_case = Case({"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "low"})
        mock_case.rules.append(rule)
        mock_ds.case.get.return_value = mock_case

        user = MagicMock()
        user.uname = "analyst1"

        with pytest.raises(InvalidDataException, match="No valid fields"):
            case_service.update_case_rule("case-001", rule.rule_id, {"author": "hacker"}, user)

    @patch("howler.services.case_service.datastore")
    def test_update_rule_not_found(self, mock_ds_fn):
        """update_case_rule raises NotFoundException when rule doesn't exist."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_case = Case({"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "low"})
        mock_ds.case.get.return_value = mock_case

        user = MagicMock()
        user.uname = "analyst1"

        with pytest.raises(NotFoundException, match="Rule"):
            case_service.update_case_rule("case-001", "nonexistent", {"enabled": False}, user)

    @patch("howler.services.case_service.datastore")
    def test_update_rule_case_not_found(self, mock_ds_fn):
        """update_case_rule raises NotFoundException when case doesn't exist."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.get.return_value = None

        user = MagicMock()
        user.uname = "analyst1"

        with pytest.raises(NotFoundException, match="Case"):
            case_service.update_case_rule("nonexistent", "rule-id", {"enabled": False}, user)
