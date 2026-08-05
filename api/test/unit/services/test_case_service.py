from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from howler.common.exceptions import HowlerValueError, InvalidDataException, NotFoundException
from howler.config import CLASSIFICATION
from howler.odm.models.case import Case, CaseItem, CaseRule
from howler.odm.models.ecs.related import Related
from howler.services import case_service


@pytest.fixture(autouse=True)
def _suppress_event_emit():
    """Prevent comms_service.emit from reaching Redis during unit tests."""
    with (
        patch("howler.services.case_service.comms_service"),
        patch("howler.odm.mixins.datastore", side_effect=lambda: case_service.datastore()),
    ):
        yield


def _make_user(uname: str = "admin", classification: str = CLASSIFICATION.UNRESTRICTED):
    user = MagicMock()
    user.uname = uname
    user.classification = classification
    return user


# ---------------------------------------------------------------------------
# create_case()
# ---------------------------------------------------------------------------


class TestCreateCase:
    """Tests for case_service.create_case."""

    @patch("howler.services.case_service.datastore")
    def test_create_case_saves_to_datastore(self, _mock_ds_fn):
        """create_case constructs a Case from title/summary and saves it."""
        result = case_service.create_case({"title": "New Case", "summary": "A summary"}, user=_make_user())

        assert isinstance(result, Case)
        assert result.case_id
        assert result.title == "New Case"
        assert result.summary == "A summary"

    @patch("howler.services.case_service.datastore")
    def test_create_case_generates_unique_id(self, _mock_ds_fn):
        """create_case auto-generates a unique UUID for each case."""
        id_a = case_service.create_case({"title": "Title A", "summary": "Summary A"}, user=_make_user()).case_id
        id_b = case_service.create_case({"title": "Title B", "summary": "Summary B"}, user=_make_user()).case_id
        assert id_a != id_b

    @patch("howler.services.case_service.datastore")
    def test_create_case_returns_odm(self, _mock_ds_fn):
        """create_case returns the created case as a plain dict."""
        result = case_service.create_case({"title": "Title", "summary": "Summary"}, user=_make_user())

        assert isinstance(result, Case)
        assert result.title == "Title"
        assert result.summary == "Summary"
        assert result.case_id

    @patch("howler.services.case_service.datastore")
    def test_create_case_sets_log_entry(self, _mock_ds_fn):
        """create_case adds a creation log entry for the given user."""
        user = _make_user()
        result = case_service.create_case({"title": "Title", "summary": "Summary"}, user=user)

        assert len(result.log) == 1
        assert result.log[0].user == str(user)

    @patch("howler.services.case_service.datastore")
    def test_create_case_no_user_defaults_to_system(self, _mock_ds_fn):
        """create_case uses 'system' as the log user when user='' (the default)."""
        result = case_service.create_case({"title": "Title", "summary": "Summary"})

        assert len(result.log) == 1
        assert result.log[0].user == "system"

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
    def test_create_case_strips_case_id(self, _mock_ds_fn):
        """create_case ignores any case_id supplied in the input dict."""
        result = case_service.create_case(
            {"case_id": "should-be-removed", "title": "T", "summary": "S"}, user=_make_user()
        )

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
                "escalation": "normal",
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
                "escalation": "normal",
            }
        )

        mock_user = MagicMock()
        mock_user.uname = "analyst"

        result = case_service.update_case("case-001", {"title": "New Title"}, mock_user)

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
            {"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "normal"}
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
            {"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "normal"}
        )
        mock_user = MagicMock()
        mock_user.uname = "analyst"

        # items is now a compound field — update must succeed without raising
        result = case_service.update_case("case-001", {"items": []}, mock_user)
        assert result is not None

    @patch("howler.services.case_service.datastore")
    def test_update_case_raises_invalid_when_no_updatable_fields(self, mock_ds_fn):
        """update_case raises InvalidDataException when the update dict is empty."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.get.return_value = Case(
            {"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "normal"}
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
                "escalation": "normal",
                "targets": ["host-a", "host-b"],
            }
        )
        mock_user = MagicMock()
        mock_user.uname = "analyst"

        result = case_service.update_case("case-001", {"targets": ["host-a"]}, mock_user)

        log_explanations = [entry.explanation for entry in result.log]
        assert any("removed" in e for e in log_explanations)

    @patch("howler.services.case_service.datastore")
    def test_update_case_list_field_logs_added(self, mock_ds_fn):
        """update_case logs added entries when new items appear in a list field."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.get.return_value = Case(
            {
                "case_id": "case-001",
                "title": "T",
                "summary": "S",
                "overview": "O",
                "escalation": "normal",
                "targets": ["host-a"],
            }
        )
        mock_user = MagicMock()
        mock_user.uname = "analyst"

        result = case_service.update_case("case-001", {"targets": ["host-a", "host-b"]}, mock_user)

        log_explanations = [entry.explanation for entry in result.log]
        assert any("added" in e for e in log_explanations)

    @pytest.mark.parametrize("field", ["case_id", "created", "updated"])
    @patch("howler.services.case_service.datastore")
    def test_update_case_raises_for_all_immutable_fields(self, mock_ds_fn, field):
        """update_case raises InvalidDataException for every immutable field."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.get.return_value = Case(
            {"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "normal"}
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
        case_obj.save.assert_called_once_with(refresh=None)

    @patch("howler.services.case_service.datastore")
    def test_hide_cases_marks_related_items_not_visible(self, mock_ds_fn):
        """Items in other cases that reference a hidden case ID get visible=False."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        # Build a Case object with items — stream_search returns it directly.
        related_case = Case({"case_id": "case-other", "title": "test case", "summary": "summary"})
        related_case.items = [
            CaseItem({"type": "case", "value": "case-001"}),
            CaseItem({"type": "case", "value": "something-else"}),
        ]
        mock_ds.case.stream_search.return_value = iter([related_case])

        # The target case itself (returned by ds.case.get in the second pass)
        target_case_obj = MagicMock()
        target_case_obj.items = []
        mock_ds.case.get.return_value = target_case_obj

        case_service.hide_cases({"case-001"}, user="analyst")

        # The matching item's visible flag must be set to False
        matching = next(i for i in related_case.items if i.value == "case-001")
        assert matching.visible is False
        # The unrelated item must be untouched
        unrelated = next(i for i in related_case.items if i.value == "something-else")
        assert unrelated.visible is True
        # The related case must be saved with the update
        # A log entry must have been appended documenting the hidden reference
        assert any("case-001" in log.explanation for log in related_case.log)

    @patch("howler.services.case_service.datastore")
    def test_hide_cases_does_not_save_related_case_when_no_items_match(self, mock_ds_fn):
        """hide_cases does NOT save a related case when none of its items match the hidden IDs."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        # stream_search returns a case whose items don't actually match (stale index)
        mock_ds.case.stream_search.return_value = iter(
            [Case({"case_id": "case-other", "title": "test case", "summary": "summary"})]
        )

        non_matching_item = MagicMock()
        non_matching_item.value = "unrelated-id"

        related_case_obj = MagicMock()
        related_case_obj.items = [non_matching_item]
        related_case_obj.case_id = "case-other"

        target_case_obj = MagicMock()
        target_case_obj.items = []
        target_case_obj.case_id = "case-001"

        mock_ds.case.get.side_effect = lambda case_id, as_obj=False: (
            related_case_obj if case_id == "case-other" else target_case_obj
        )

        case_service.hide_cases({"case-001"}, user="analyst")

        # No matching items → related case must NOT be saved
        related_case_obj.save.assert_not_called()
        target_case_obj.save.assert_called_once_with(refresh=None)

    @patch("howler.services.case_service.datastore")
    def test_hide_cases_skips_case_that_is_itself_being_hidden(self, mock_ds_fn):
        """stream_search results whose case_id is in the hidden set are skipped."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        # stream_search returns the case being hidden itself
        mock_ds.case.stream_search.return_value = iter(
            [Case({"case_id": "case-001", "title": "test case", "summary": "summary"})]
        )

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
        # The format string uses %s, so check the interpolated args contain the case ID.
        warning_args = mock_logger.warning.call_args[0]
        assert any("case-missing" in str(a) for a in warning_args)

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
        case_a.save.assert_called_once_with(refresh=None)
        case_b.save.assert_called_once_with(refresh=None)

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

        mock_ds.case.delete_by_query.assert_called_once_with("case_id:(case-del)", refresh=None)

    @patch("howler.services.case_service.datastore")
    def test_delete_cases_removes_cross_case_item_references(self, mock_ds_fn):
        """delete_cases removes CaseItem entries that reference a deleted case from other cases."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.stream_search.return_value = iter(
            [Case({"case_id": "case-other", "title": "test case", "summary": "summary"})]
        )

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
        related_case.save.assert_called_once_with(refresh=None)

    @patch("howler.services.case_service.datastore")
    def test_delete_cases_skips_stream_results_in_delete_set(self, mock_ds_fn):
        """delete_cases does not attempt cross-reference cleanup on cases being deleted."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        # stream_search returns the very case being deleted
        mock_ds.case.stream_search.return_value = iter(
            [Case({"case_id": "case-del", "title": "test case", "summary": "summary"})]
        )

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
        """append_case_item raises InvalidDataException for unsupported item types."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_case = MagicMock()
        mock_case.items = []
        mock_ds.case.get.return_value = mock_case

        with pytest.raises(InvalidDataException):
            case_service.append_case_item("case-001", item_type=item_type, item_value="x", item_name="x")

    @patch("howler.services.case_service.append_event")
    @patch("howler.services.case_service.datastore")
    def test_append_case_item_routes_event(self, mock_ds_fn, mock_append_event):
        """append_case_item dispatches to append_event for 'event' type."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_case = MagicMock()
        mock_case.items = []
        mock_ds.case.get.return_value = mock_case

        mock_append_event.return_value = mock_case

        item = CaseItem({"type": "event", "value": "obs-001"})
        result = case_service.append_case_item("case-001", item=item)

        mock_append_event.assert_called_once_with(mock_case, item, None)
        assert result is mock_case

    @patch("howler.services.case_service.append_case")
    @patch("howler.services.case_service.datastore")
    def test_append_case_item_routes_case(self, mock_ds_fn, mock_append_case):
        """append_case_item dispatches to append_case for 'case' type."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_case = MagicMock()
        mock_case.items = []
        mock_ds.case.get.return_value = mock_case

        mock_append_case.return_value = mock_case

        item = CaseItem({"type": "case", "value": "child-001"})
        result = case_service.append_case_item("case-001", item=item)

        mock_append_case.assert_called_once_with(mock_case, item, None)
        assert result is mock_case

    @patch("howler.services.case_service.datastore")
    def test_append_case_item_raises_not_found_for_missing_case(self, mock_ds_fn):
        """append_case_item raises NotFoundException when the case doesn't exist."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.get.return_value = None

        item = CaseItem({"type": "hit", "value": "hit-001"})
        with pytest.raises(NotFoundException, match="Case does not exist"):
            case_service.append_case_item("nonexistent", item=item)


# ---------------------------------------------------------------------------
# append_hit()
# ---------------------------------------------------------------------------


class TestAppendHit:
    """Tests for case_service.append_hit."""

    @patch("howler.services.case_service.recompute_case_metadata")
    @patch("howler.services.case_service.add_backreference")
    @patch("howler.services.case_service.datastore")
    def test_append_hit_adds_item(self, mock_ds_fn, mock_backref, mock_sync):
        """append_hit appends the item to the case and delegates metadata sync to recompute_case_metadata."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_case = MagicMock()
        mock_case.case_id = "case-001"
        mock_case.items = []
        mock_ds.case.get.return_value = mock_case

        mock_hit = MagicMock()
        mock_hit.classification = CLASSIFICATION.UNRESTRICTED
        mock_ds.hit.get.return_value = mock_hit

        item = CaseItem({"type": "hit", "value": "hit-001"})
        case_service.append_hit(mock_case, item)

        assert len(mock_case.items) == 1
        mock_backref.assert_called_once_with(mock_hit, "case-001")
        mock_sync.assert_called_once_with(mock_case)
        mock_hit.save.assert_called_once()

    @patch("howler.services.case_service.recompute_case_metadata")
    @patch("howler.services.case_service.add_backreference")
    @patch("howler.services.case_service.datastore")
    def test_append_hit_preserves_name_and_parent(self, mock_ds_fn, mock_backref, mock_sync):
        """append_hit preserves the item's name and parent fields without modification."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_case = MagicMock()
        mock_case.case_id = "case-001"
        mock_case.items = []
        mock_ds.case.get.return_value = mock_case

        mock_hit = MagicMock()
        mock_hit.classification = CLASSIFICATION.UNRESTRICTED
        mock_ds.hit.get.return_value = mock_hit

        item = CaseItem({"type": "hit", "value": "hit-001", "name": "My Alert", "parent": None})
        case_service.append_hit(mock_case, item)

        assert item.name == "My Alert"
        assert item.parent is None

    @patch("howler.services.case_service.datastore")
    def test_append_hit_missing_case_raises(self, mock_ds_fn):
        """append_case_item raises NotFoundException when the case does not exist."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.get.return_value = None

        item = CaseItem({"type": "hit", "value": "hit-001"})
        with pytest.raises(NotFoundException):
            case_service.append_case_item("nonexistent-case", item=item)

    @patch("howler.services.case_service.datastore")
    def test_append_hit_missing_hit_raises(self, mock_ds_fn):
        """append_hit raises NotFoundException when the hit does not exist."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_case = MagicMock()
        mock_case.items = []
        mock_ds.case.get.return_value = mock_case
        mock_ds.hit.get.return_value = None

        item = CaseItem({"type": "hit", "value": "nonexistent-hit"})
        with pytest.raises(NotFoundException):
            case_service.append_hit(mock_case, item)

        # Case must NOT have been saved when the hit doesn't exist.
        mock_ds.case.save.assert_not_called()

    @patch("howler.services.case_service.datastore")
    def test_append_hit_duplicate_raises(self, mock_ds_fn):
        """append_case_item raises InvalidDataException when the destination already contains same name/parent."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        existing = CaseItem({"type": "hit", "value": "hit-001", "name": "dup"})
        mock_case = MagicMock()
        mock_case.items = [existing]
        mock_ds.case.get.return_value = mock_case
        mock_ds.hit.get.return_value = MagicMock(classification=CLASSIFICATION.UNRESTRICTED)

        item = CaseItem({"type": "hit", "value": "hit-002", "name": "dup"})
        with pytest.raises(InvalidDataException):
            case_service.append_case_item("case-001", item=item)


# ---------------------------------------------------------------------------
# append_event()
# ---------------------------------------------------------------------------


class TestAppendEvent:
    """Tests for case_service.append_event."""

    @patch("howler.services.case_service.recompute_case_metadata")
    @patch("howler.services.case_service.add_backreference")
    @patch("howler.services.case_service.datastore")
    def test_append_event_adds_item(self, mock_ds_fn, mock_backref, mock_sync):
        """append_event appends the item to the case and saves."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_case = MagicMock()
        mock_case.case_id = "case-001"
        mock_case.items = []
        mock_ds.case.get.return_value = mock_case
        mock_case.save.return_value = True

        mock_obs = MagicMock()
        mock_obs.classification = CLASSIFICATION.UNRESTRICTED
        mock_obs.howler.id = "obs-001"
        mock_ds.event.get.return_value = mock_obs

        item = CaseItem({"type": "event", "value": "obs-001"})
        case_service.append_event(mock_case, item)

        mock_case.save.assert_called_once()
        assert len(mock_case.items) == 1
        mock_backref.assert_called_once_with(mock_obs, "case-001")
        mock_sync.assert_called_once_with(mock_case)
        mock_obs.save.assert_called_once()

    @patch("howler.services.case_service.datastore")
    def test_append_event_missing_case_raises(self, mock_ds_fn):
        """append_case_item raises NotFoundException when the case does not exist."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.get.return_value = None

        item = CaseItem({"type": "event", "value": "obs-001"})
        with pytest.raises(NotFoundException):
            case_service.append_case_item("nonexistent-case", item=item)

    @patch("howler.services.case_service.datastore")
    def test_append_event_missing_event_raises(self, mock_ds_fn):
        """append_event raises NotFoundException when the event does not exist."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_case = MagicMock()
        mock_case.items = []
        mock_ds.case.get.return_value = mock_case
        mock_ds.event.get.return_value = None

        item = CaseItem({"type": "event", "value": "nonexistent-obs"})
        with pytest.raises(NotFoundException):
            case_service.append_event(mock_case, item)

    @patch("howler.services.case_service.datastore")
    def test_append_event_duplicate_raises(self, mock_ds_fn):
        """append_case_item raises InvalidDataException for duplicate destination name/parent."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        existing = CaseItem({"type": "event", "value": "obs-001", "name": "dup"})
        mock_case = MagicMock()
        mock_case.items = [existing]
        mock_ds.case.get.return_value = mock_case
        mock_ds.event.get.return_value = MagicMock(classification=CLASSIFICATION.UNRESTRICTED)

        item = CaseItem({"type": "event", "value": "obs-002", "name": "dup"})
        with pytest.raises(InvalidDataException):
            case_service.append_case_item("case-001", item=item)


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

        mock_ds.case.get.return_value = mock_child
        mock_parent.save.return_value = True

        item = CaseItem({"type": "case", "value": "child-001"})
        case_service.append_case(mock_parent, item)

        mock_parent.save.assert_called_once()
        assert len(mock_parent.items) == 1
        assert item.value == "child-001"

    @patch("howler.services.case_service.datastore")
    def test_append_case_missing_parent_raises(self, mock_ds_fn):
        """append_case_item raises NotFoundException when the parent case does not exist."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.get.return_value = None

        item = CaseItem({"type": "case", "value": "child-001"})
        with pytest.raises(NotFoundException):
            case_service.append_case_item("nonexistent-parent", item=item)

    @patch("howler.services.case_service.datastore")
    def test_append_case_missing_referenced_case_raises(self, mock_ds_fn):
        """append_case raises NotFoundException when the referenced case does not exist."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_parent = MagicMock()
        mock_parent.items = []

        mock_ds.case.get.return_value = None

        item = CaseItem({"type": "case", "value": "nonexistent-child"})
        with pytest.raises(NotFoundException):
            case_service.append_case(mock_parent, item)

    @patch("howler.services.case_service.datastore")
    def test_append_case_duplicate_raises(self, mock_ds_fn):
        """append_case raises InvalidDataException when the reference already exists."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        existing = CaseItem({"type": "case", "value": "child-001"})
        mock_parent = MagicMock()
        mock_parent.items = [existing]
        mock_ds.case.get.return_value = MagicMock()

        item = CaseItem({"type": "case", "value": "child-001"})
        with pytest.raises(InvalidDataException):
            case_service.append_case(mock_parent, item)

    @patch("howler.services.case_service.datastore")
    def test_append_case_places_item_at_root(self, mock_ds_fn):
        """append_case always places case items at root level (parent must be None)."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_parent = MagicMock()
        mock_parent.case_id = "parent-001"
        mock_parent.items = []
        mock_parent.log = []

        mock_child = MagicMock()
        mock_child.case_id = "child-001"

        mock_ds.case.get.return_value = mock_child
        mock_parent.save.return_value = True

        item = CaseItem({"type": "case", "value": "child-001"})
        case_service.append_case(mock_parent, item)

        assert len(mock_parent.items) == 1
        assert item.parent is None

    @patch("howler.services.case_service.datastore")
    def test_append_case_no_log_entry_for_plain_add(self, mock_ds_fn):
        """append_case does not generate a log entry for a normal case reference add."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_parent = MagicMock()
        mock_parent.case_id = "parent-001"
        mock_parent.items = []
        mock_parent.log = []

        mock_child = MagicMock()
        mock_child.case_id = "child-001"

        mock_ds.case.get.return_value = mock_child
        mock_parent.save.return_value = True

        item = CaseItem({"type": "case", "value": "child-001"})
        case_service.append_case(mock_parent, item)

        assert len(mock_parent.items) == 1
        assert len(mock_parent.log) == 0

    @patch("howler.services.case_service.datastore")
    def test_append_case_item_value_unchanged(self, mock_ds_fn):
        """append_case stores the item's value unchanged."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_parent = MagicMock()
        mock_parent.case_id = "parent-001"
        mock_parent.items = []
        mock_parent.log = []

        mock_child = MagicMock()
        mock_child.case_id = "child-001"

        mock_ds.case.get.return_value = mock_child
        mock_parent.save.return_value = True

        item = CaseItem({"type": "case", "value": "child-001"})
        case_service.append_case(mock_parent, item)

        assert item.value == "child-001"
        assert len(mock_parent.log) == 0

    @patch("howler.services.case_service.datastore")
    def test_append_case_with_optional_name(self, mock_ds_fn):
        """append_case correctly stores a case item with an optional display name."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_parent = MagicMock()
        mock_parent.case_id = "parent-001"
        mock_parent.items = []
        mock_parent.log = []

        mock_child = MagicMock()
        mock_child.case_id = "child-001"

        mock_ds.case.get.return_value = mock_child
        mock_parent.save.return_value = True

        item = CaseItem({"type": "case", "value": "child-001", "name": "my-child"})
        case_service.append_case(mock_parent, item)

        assert item.name == "my-child"
        assert len(mock_parent.log) == 0


# ---------------------------------------------------------------------------
# append_reference()
# ---------------------------------------------------------------------------


class TestAppendReference:
    """Tests for case_service.append_case_item with reference items."""

    @patch("howler.services.case_service.datastore")
    def test_append_reference_adds_item(self, mock_ds_fn):
        """append_case_item saves the reference item to the case."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_case = MagicMock()
        mock_case.items = []
        mock_case.case_id = "case-001"
        mock_ds.case.get.return_value = mock_case
        mock_case.save.return_value = True

        item = CaseItem({"type": "reference", "value": "https://example.com", "name": "refs"})
        case_service.append_case_item("case-001", item=item)

        assert item in mock_case.items
        mock_case.save.assert_called_once()

    @patch("howler.services.case_service.datastore")
    def test_append_reference_missing_case_raises(self, mock_ds_fn):
        """append_case_item raises NotFoundException when the case does not exist."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.get.return_value = None

        item = CaseItem({"type": "reference", "value": "https://example.com", "name": "refs"})
        with pytest.raises(NotFoundException):
            case_service.append_case_item("nonexistent", item=item)

    @patch("howler.services.case_service.datastore")
    def test_append_reference_duplicate_raises(self, mock_ds_fn):
        """append_case_item raises InvalidDataException when destination sibling name already exists."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        existing = CaseItem({"type": "reference", "value": "https://example.com", "name": "refs"})
        mock_case = MagicMock()
        mock_case.items = [existing]
        mock_ds.case.get.return_value = mock_case

        item = CaseItem({"type": "reference", "value": "https://another.example.com", "name": "refs"})
        with pytest.raises(InvalidDataException):
            case_service.append_case_item("case-001", item=item)


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
        """remove_case_item raises NotFoundException when the item id is not in the case."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_case = MagicMock()
        mock_case.items = [CaseItem({"type": "hit", "value": "other-id"})]
        mock_ds.case.get.return_value = mock_case

        with pytest.raises(NotFoundException):
            case_service.remove_case_items("case-001", ["00000000-0000-0000-0000-000000000000"])

    @patch("howler.services.case_service.recompute_case_metadata")
    @patch("howler.services.case_service.datastore")
    def test_remove_hit_item_clears_backreference(self, mock_ds_fn, mock_sync):
        """remove_case_item removes the item from the case and removes the hit back-reference."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        hit_item = CaseItem({"type": "hit", "value": "hit-001"})

        mock_case = MagicMock()
        mock_case.case_id = "case-001"
        mock_case.items = [hit_item]
        mock_ds.case.get.return_value = mock_case
        mock_ds.case.save.return_value = True

        mock_hit = MagicMock()
        mock_hit.howler.related = ["case-001"]
        mock_ds.hit.get.return_value = mock_hit

        case_service.remove_case_items("case-001", [hit_item.id])

        assert hit_item not in mock_case.items
        mock_sync.assert_called_once_with(mock_case)

    @patch("howler.services.case_service.recompute_case_metadata")
    @patch("howler.services.case_service.datastore")
    def test_remove_event_item_clears_backreference(self, mock_ds_fn, mock_sync):
        """remove_case_item removes an event item from the case."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        obs_item = CaseItem({"type": "event", "value": "obs-001"})

        mock_case = MagicMock()
        mock_case.case_id = "case-001"
        mock_case.items = [obs_item]
        mock_ds.case.get.return_value = mock_case
        mock_ds.case.save.return_value = True

        mock_obs = MagicMock()
        mock_obs.howler.related = ["case-001"]
        mock_ds.event.get.return_value = mock_obs

        case_service.remove_case_items("case-001", [obs_item.id])

        assert obs_item not in mock_case.items
        mock_case.save.assert_called_once_with(refresh=None)
        mock_sync.assert_called_once_with(mock_case)


# ---------------------------------------------------------------------------
# rename_case_item()
# ---------------------------------------------------------------------------


class TestRenameCaseItem:
    """Tests for case_service.rename_case_item."""

    @patch("howler.services.case_service.datastore")
    def test_rename_item_success(self, mock_ds_fn):
        """Updates the item name and saves the case once."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        item = CaseItem({"type": "hit", "value": "hit-001", "name": "Old Name"})
        mock_case = MagicMock()
        mock_case.case_id = "case-001"
        mock_case.items = [item]
        mock_case.save.return_value = True
        mock_ds.case.get.return_value = mock_case

        result = case_service.rename_case_item("case-001", item.id, "New Name")

        assert item.name == "New Name"
        mock_case.save.assert_called_once_with(refresh=None)
        mock_ds.case.save.assert_not_called()
        assert result is mock_case

    @patch("howler.services.case_service.datastore")
    def test_rename_item_raises_not_found_for_missing_case(self, mock_ds_fn):
        """Raises NotFoundException when the case does not exist."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.get.return_value = None

        with pytest.raises(NotFoundException):
            case_service.rename_case_item("nonexistent", "hit-001", "New Name")

        mock_ds.case.save.assert_not_called()

    @patch("howler.services.case_service.datastore")
    def test_rename_item_raises_not_found_for_missing_item(self, mock_ds_fn):
        """Raises NotFoundException when the item value is not in the case."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_case = MagicMock()
        mock_case.items = [CaseItem({"type": "hit", "value": "other-id", "name": "x"})]
        mock_ds.case.get.return_value = mock_case

        with pytest.raises(NotFoundException):
            case_service.rename_case_item("case-001", "hit-001", "New Name")

        mock_ds.case.save.assert_not_called()

    @patch("howler.services.case_service.datastore")
    def test_rename_item_raises_invalid_data_when_name_taken(self, mock_ds_fn):
        """Raises InvalidDataException when new_name is already used by another item."""
        from howler.common.exceptions import InvalidDataException

        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        item_a = CaseItem({"type": "hit", "value": "hit-001", "name": "A"})
        item_b = CaseItem({"type": "hit", "value": "hit-002", "name": "B"})
        mock_case = MagicMock()
        mock_case.items = [item_a, item_b]
        mock_ds.case.get.return_value = mock_case

        with pytest.raises(InvalidDataException):
            case_service.rename_case_item("case-001", item_a.id, "B")

        mock_ds.case.save.assert_not_called()

    def test_rename_item_raises_invalid_data_for_trailing_slash(self):
        """Raises InvalidDataException without touching the datastore for a bad name."""
        from howler.common.exceptions import InvalidDataException

        with pytest.raises(InvalidDataException):
            case_service.rename_case_item("case-001", "hit-001", "")

    def test_rename_item_raises_invalid_data_for_empty_name(self):
        """Raises InvalidDataException for an empty new_name."""
        from howler.common.exceptions import InvalidDataException

        with pytest.raises(InvalidDataException):
            case_service.rename_case_item("case-001", "hit-001", "")

    @patch("howler.services.case_service.datastore")
    def test_rename_item_raises_datastore_error_on_save_failure(self, mock_ds_fn):
        """Raises DataStoreException when ds.case.save returns False."""
        from howler.datastore.exceptions import DataStoreException

        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        item = CaseItem({"type": "hit", "value": "hit-001", "name": "Old Name"})
        mock_case = MagicMock()
        mock_case.case_id = "case-001"
        mock_case.items = [item]
        mock_case.save.return_value = False
        mock_ds.case.get.return_value = mock_case

        with pytest.raises(DataStoreException):
            case_service.rename_case_item("case-001", item.id, "New Name")

    @patch("howler.services.case_service.datastore")
    def test_rename_item_allows_same_name_on_same_item(self, mock_ds_fn):
        """Renaming an item to its current name is allowed (no conflict with itself)."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        item = CaseItem({"type": "hit", "value": "hit-001", "name": "Same"})
        mock_case = MagicMock()
        mock_case.case_id = "case-001"
        mock_case.items = [item]
        mock_case.save.return_value = True
        mock_ds.case.get.return_value = mock_case

        case_service.rename_case_item("case-001", item.id, "Same")

        mock_case.save.assert_called_once_with(refresh=None)
        mock_ds.case.save.assert_not_called()

    @patch("howler.services.case_service.datastore")
    def test_rename_item_allows_same_name_in_different_folder(self, mock_ds_fn):
        """Items in different folders may share a name; only siblings conflict."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        folder_a = CaseItem({"type": "folder", "name": "folder-a"})
        folder_b = CaseItem({"type": "folder", "name": "folder-b"})
        item_in_a = CaseItem({"type": "hit", "value": "hit-001", "name": "Report", "parent": folder_a.id})
        item_in_b = CaseItem({"type": "hit", "value": "hit-002", "name": "Other", "parent": folder_b.id})
        mock_case = MagicMock()
        mock_case.case_id = "case-001"
        mock_case.items = [folder_a, folder_b, item_in_a, item_in_b]
        mock_case.save.return_value = True
        mock_ds.case.get.return_value = mock_case

        # Renaming item_in_b to "Report" is allowed because it's in a different folder
        case_service.rename_case_item("case-001", item_in_b.id, "Report")

        mock_case.save.assert_called_once_with(refresh=None)
        mock_ds.case.save.assert_not_called()

    @patch("howler.services.case_service.datastore")
    def test_rename_item_raises_when_sibling_has_same_name(self, mock_ds_fn):
        """Renaming to a name already used by a sibling (same parent) raises InvalidDataException."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        folder = CaseItem({"type": "folder", "name": "folder-a"})
        item_a = CaseItem({"type": "hit", "value": "hit-001", "name": "Report", "parent": folder.id})
        item_b = CaseItem({"type": "hit", "value": "hit-002", "name": "Other", "parent": folder.id})
        mock_case = MagicMock()
        mock_case.items = [folder, item_a, item_b]
        mock_ds.case.get.return_value = mock_case

        with pytest.raises(InvalidDataException):
            case_service.rename_case_item("case-001", item_b.id, "Report")

        mock_ds.case.save.assert_not_called()


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
# recompute_case_metadata()
# ---------------------------------------------------------------------------


class TestSyncCaseMetadata:
    """Tests for case_service.recompute_case_metadata."""

    @patch("howler.services.case_service.datastore")
    def test_sync_case_metadata_updates_from_hit_outline(self, mock_ds_fn):
        """recompute_case_metadata populates threats/targets/indicators from hit outline data, in memory only."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        hit_item = CaseItem({"type": "hit", "value": "hit-001", "name": "test"})

        mock_case = MagicMock()
        mock_case.items = [hit_item]

        mock_outline = MagicMock()
        mock_outline.threat = "evil.example.com"
        mock_outline.target = "workstation-01"
        mock_outline.indicators = ["hash-abc"]

        mock_hit = MagicMock()
        mock_hit.related = None
        mock_hit.howler.outline = mock_outline
        mock_ds.hit.get.return_value = mock_hit

        case_service.recompute_case_metadata(mock_case)

        mock_case.save.assert_not_called()
        assert mock_case.threats == ["evil.example.com"]
        assert mock_case.targets == ["workstation-01"]
        assert mock_case.indicators == ["hash-abc"]

    @patch("howler.services.case_service.datastore")
    def test_sync_case_metadata_clears_when_no_items(self, mock_ds_fn):
        """recompute_case_metadata resets threats/targets/indicators to empty lists when no items exist."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_case = MagicMock()
        mock_case.items = []

        case_service.recompute_case_metadata(mock_case)

        mock_case.save.assert_not_called()
        assert mock_case.targets == []
        assert mock_case.threats == []
        assert mock_case.indicators == []

    @patch("howler.services.case_service.datastore")
    def test_sync_case_metadata_collects_from_events(self, mock_ds_fn):
        """recompute_case_metadata collects indicators from event items via their related data."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        obs_item = CaseItem({"type": "event", "value": "obs-001", "name": "obs-001"})

        mock_case = MagicMock()
        mock_case.items = [obs_item]

        mock_related = Related({"ip": ["10.0.0.1"], "hosts": ["host-x"]})
        mock_obs = MagicMock()
        mock_obs.related = mock_related
        mock_ds.event.get.return_value = mock_obs

        case_service.recompute_case_metadata(mock_case)

        mock_case.save.assert_not_called()
        assert "10.0.0.1" in mock_case.indicators
        assert "host-x" in mock_case.indicators

    @patch("howler.services.case_service.datastore")
    def test_sync_case_metadata_skips_missing_event(self, mock_ds_fn):
        """recompute_case_metadata skips event items whose backing object is None."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        obs_item = CaseItem({"type": "event", "value": "obs-missing", "name": "obs-missing"})

        mock_case = MagicMock()
        mock_case.items = [obs_item]

        mock_ds.event.get.return_value = None

        case_service.recompute_case_metadata(mock_case)

        mock_case.save.assert_not_called()
        assert mock_case.indicators == []


# ---------------------------------------------------------------------------
# add_backreference()
# ---------------------------------------------------------------------------


class TestAddBackreference:
    """Tests for case_service.add_backreference."""

    def test_add_backreference_raises_on_none_object(self):
        """add_backreference raises InvalidDataException when backing_obj is None."""
        with pytest.raises(InvalidDataException):
            case_service.add_backreference(None, "case-id")

    def test_add_backreference_raises_on_empty_case_id(self):
        """add_backreference raises InvalidDataException when case_id is empty."""
        mock_obj = MagicMock()

        with pytest.raises(InvalidDataException):
            case_service.add_backreference(mock_obj, "")

    def test_add_backreference_appends_without_saving(self):
        """add_backreference appends the case_id to related, in memory only."""
        mock_obj = MagicMock()
        mock_obj.howler.related = []
        mock_obj.howler.id = "obj-001"

        added = case_service.add_backreference(mock_obj, "case-abc")

        assert added is True
        assert "case-abc" in mock_obj.howler.related
        mock_obj.save.assert_not_called()

    def test_add_backreference_is_idempotent(self):
        """add_backreference does not add a duplicate if the case_id is already present."""
        mock_obj = MagicMock()
        mock_obj.howler.related = ["case-abc"]
        mock_obj.howler.id = "obj-001"

        added = case_service.add_backreference(mock_obj, "case-abc")

        assert added is False
        assert mock_obj.howler.related.count("case-abc") == 1
        mock_obj.save.assert_not_called()


# ---------------------------------------------------------------------------
# remove_backreference()
# ---------------------------------------------------------------------------


class TestRemoveBackreference:
    """Tests for case_service.remove_backreference."""

    def test_remove_backreference_raises_on_none_object(self):
        """remove_backreference raises InvalidDataException when backing_obj is None."""
        with pytest.raises(InvalidDataException):
            case_service.remove_backreference(None, "case-id")

    def test_remove_backreference_noop_when_not_present(self):
        """remove_backreference does nothing when case_id is not in related."""
        mock_obj = MagicMock()
        mock_obj.howler.related = ["other-case"]

        case_service.remove_backreference(mock_obj, "case-that-was-never-added")

        assert "other-case" in mock_obj.howler.related
        mock_obj.save.assert_not_called()

    def test_remove_backreference_removes_without_saving(self):
        """remove_backreference removes the case_id from related, in memory only."""
        mock_obj = MagicMock()
        mock_obj.howler.related = ["case-abc", "other-case"]
        mock_obj.howler.id = "obj-001"

        case_service.remove_backreference(mock_obj, "case-abc")

        assert "case-abc" not in mock_obj.howler.related
        assert "other-case" in mock_obj.howler.related
        mock_obj.save.assert_not_called()


# ---------------------------------------------------------------------------
# Event emission on case mutations
# ---------------------------------------------------------------------------


class TestCaseEventEmission:
    """Tests that case mutations emit 'cases' events via comms_service."""

    @patch("howler.services.case_service.comms_service")
    @patch("howler.services.case_service.datastore")
    def test_update_case_emits_event(self, mock_ds_fn, mock_events):
        """update_case emits a 'cases' event containing the updated case primitives."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.get.return_value = Case(
            {"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "normal"}
        )

        mock_user = MagicMock()
        mock_user.uname = "analyst"

        case_service.update_case("case-001", {"title": "New"}, mock_user)

        mock_events.emit.assert_called_once()
        args = mock_events.emit.call_args
        assert args[0][0] == "cases"
        assert "case" in args[0][1]
        assert args[0][1]["case"]["title"] == "New"

    @patch("howler.services.case_service.comms_service")
    @patch("howler.services.case_service.datastore")
    def test_create_case_emits_event(self, mock_ds_fn, mock_events):
        """create_case emits a 'cases' event with the new case."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        case_service.create_case({"title": "New", "summary": "S"}, user=_make_user())

        mock_events.emit.assert_called_once()
        args = mock_events.emit.call_args
        assert args[0][0] == "cases"
        assert "case" in args[0][1]
        assert args[0][1]["case"]["title"] == "New"

    @patch("howler.services.case_service.recompute_case_metadata")
    @patch("howler.services.case_service.comms_service")
    @patch("howler.services.case_service.datastore")
    def test_append_hit_emits_event(self, mock_ds_fn, mock_events, mock_sync):
        """append_hit emits a 'cases' event after adding a hit."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_case = Case({"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "normal"})
        mock_hit = MagicMock()
        mock_hit.classification = CLASSIFICATION.UNRESTRICTED
        mock_hit.howler.related = []
        mock_hit.howler.id = "hit-001"

        mock_ds.case.get.return_value = mock_case
        mock_ds.hit.get.return_value = mock_hit
        mock_ds.case.save.return_value = True

        item = CaseItem({"type": "hit", "value": "hit-001", "name": "test"})
        case_service.append_hit(mock_case, item)

        mock_events.emit.assert_called_once()
        args = mock_events.emit.call_args
        assert args[0][0] == "cases"
        assert "case" in args[0][1]


# ---------------------------------------------------------------------------
# add_case_rule()
# ---------------------------------------------------------------------------


class TestAddCaseRule:
    """Tests for case_service.add_case_rule."""

    @patch("howler.services.case_service.comms_service")
    @patch("howler.services.case_service.datastore")
    def test_add_rule_success(self, mock_ds_fn, mock_events):
        """add_case_rule appends a rule and saves the case."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_case = Case({"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "normal"})
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

    @patch("howler.services.case_service.comms_service")
    @patch("howler.services.case_service.datastore")
    def test_add_rule_with_timeframe(self, mock_ds_fn, mock_events):
        """add_case_rule stores the timeframe when provided."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_case = Case({"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "normal"})
        mock_ds.case.get.return_value = mock_case

        user = MagicMock()
        user.uname = "analyst1"

        result = case_service.add_case_rule(
            "case-001",
            {"query": "*:*", "destination": "alerts/all", "timeframe": 14},
            user,
        )

        assert result.rules[0].timeframe == 14

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

        mock_case = Case({"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "normal"})
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

        mock_case = Case({"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "normal"})
        mock_ds.case.get.return_value = mock_case

        user = MagicMock()
        user.uname = "analyst1"

        with pytest.raises(InvalidDataException, match="destination"):
            case_service.add_case_rule("case-001", {"query": "event.kind:alert"}, user)

    @patch("howler.services.case_service.comms_service")
    @patch("howler.services.case_service.datastore")
    def test_add_rule_strips_client_rule_id(self, mock_ds_fn, mock_events):
        """add_case_rule ignores any 'id' provided by the client."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_case = Case({"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "normal"})
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

    @patch("howler.services.case_service.comms_service")
    @patch("howler.services.case_service.datastore")
    def test_remove_rule_success(self, mock_ds_fn, mock_events):
        """remove_case_rule removes the rule and saves."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        rule = CaseRule({"query": "*:*", "destination": "alerts/all", "author": "admin"})
        mock_case = Case({"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "normal"})
        mock_case.rules.append(rule)
        mock_ds.case.get.return_value = mock_case

        user = MagicMock()
        user.uname = "analyst1"

        result = case_service.remove_case_rule("case-001", rule.rule_id, user)

        assert len(result.rules) == 0

    @patch("howler.services.case_service.datastore")
    def test_remove_rule_not_found(self, mock_ds_fn):
        """remove_case_rule raises NotFoundException when rule doesn't exist."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_case = Case({"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "normal"})
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

    @patch("howler.services.case_service.comms_service")
    @patch("howler.services.case_service.datastore")
    def test_update_rule_toggle_enabled(self, mock_ds_fn, mock_events):
        """update_case_rule can toggle the enabled field."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        rule = CaseRule({"query": "*:*", "destination": "alerts/all", "author": "admin", "enabled": True})
        mock_case = Case({"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "normal"})
        mock_case.rules.append(rule)
        mock_ds.case.get.return_value = mock_case

        user = MagicMock()
        user.uname = "analyst1"

        result = case_service.update_case_rule("case-001", rule.rule_id, {"enabled": False}, user)

        assert result.rules[0].enabled is False

    @patch("howler.services.case_service.comms_service")
    @patch("howler.services.case_service.datastore")
    def test_update_rule_change_query(self, mock_ds_fn, mock_events):
        """update_case_rule can update the query field."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        rule = CaseRule({"query": "old:query", "destination": "alerts/all", "author": "admin"})
        mock_case = Case({"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "normal"})
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
        mock_case = Case({"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "normal"})
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

        mock_case = Case({"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "normal"})
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


# ---------------------------------------------------------------------------
# get_last_resolved_time()
# ---------------------------------------------------------------------------


class TestGetLastResolvedTime:
    """Tests for case_service.get_last_resolved_time."""

    def test_single_resolution(self):
        """Returns the timestamp when a case has been resolved once."""
        case = Case({"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "normal"})
        case.log = [
            _make_log("Case created"),
            _make_log_change("status", "open", "resolved", "2026-01-15T10:00:00.000000Z"),
        ]
        result = case_service.get_last_resolved_time(case)
        assert result is not None
        assert result.year == 2026
        assert result.month == 1
        assert result.day == 15

    def test_multiple_resolve_cycles_returns_latest(self):
        """Returns the final resolved timestamp after open→resolved→in-progress→resolved."""
        case = Case({"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "normal"})
        case.log = [
            _make_log("Case created"),
            _make_log_change("status", "open", "resolved", "2026-01-10T10:00:00.000000Z"),
            _make_log_change("status", "resolved", "in-progress", "2026-01-12T10:00:00.000000Z"),
            _make_log_change("status", "in-progress", "resolved", "2026-02-20T15:30:00.000000Z"),
        ]
        result = case_service.get_last_resolved_time(case)
        assert result is not None
        assert result.month == 2
        assert result.day == 20

    def test_no_resolution_returns_none(self):
        """Returns None if the case has never been resolved."""
        case = Case({"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "normal"})
        case.log = [
            _make_log("Case created"),
            _make_log_change("status", "open", "in-progress", "2026-01-10T10:00:00.000000Z"),
        ]
        result = case_service.get_last_resolved_time(case)
        assert result is None

    def test_empty_log_returns_none(self):
        """Returns None if the case log is empty."""
        case = Case({"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "normal"})
        case.log = []
        result = case_service.get_last_resolved_time(case)
        assert result is None


# ---------------------------------------------------------------------------
# Rule CRUD: timeframe and expire_after_resolved
# ---------------------------------------------------------------------------


class TestRuleTimeframeAndExpireAfterResolved:
    """Tests for timeframe (days) and expire_after_resolved (boolean) on rules."""

    @patch("howler.services.case_service.datastore")
    def test_add_rule_with_timeframe_and_expire_after_resolved(self, mock_ds_fn):
        """add_case_rule accepts timeframe (days) with expire_after_resolved flag."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_case = Case({"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "normal"})
        mock_ds.case.get.return_value = mock_case

        user = MagicMock()
        user.uname = "analyst1"

        result = case_service.add_case_rule(
            "case-001",
            {"query": "*:*", "destination": "alerts/all", "timeframe": 14, "expire_after_resolved": True},
            user,
        )

        assert result.rules[0].timeframe == 14
        assert result.rules[0].expire_after_resolved is True

    @patch("howler.services.case_service.datastore")
    def test_add_rule_with_timeframe_only(self, mock_ds_fn):
        """add_case_rule with timeframe defaults expire_after_resolved to False."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_case = Case({"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "normal"})
        mock_ds.case.get.return_value = mock_case

        user = MagicMock()
        user.uname = "analyst1"

        result = case_service.add_case_rule(
            "case-001",
            {"query": "*:*", "destination": "alerts/all", "timeframe": 7},
            user,
        )

        assert result.rules[0].timeframe == 7
        assert result.rules[0].expire_after_resolved is False

    @patch("howler.services.case_service.datastore")
    def test_add_rule_no_timeframe(self, mock_ds_fn):
        """add_case_rule without timeframe means no expiry."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_case = Case({"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "normal"})
        mock_ds.case.get.return_value = mock_case

        user = MagicMock()
        user.uname = "analyst1"

        result = case_service.add_case_rule(
            "case-001",
            {"query": "*:*", "destination": "alerts/all"},
            user,
        )

        assert result.rules[0].timeframe is None
        assert result.rules[0].expire_after_resolved is False

    @patch("howler.services.case_service.datastore")
    def test_add_rule_rejects_expire_after_resolved_without_timeframe(self, mock_ds_fn):
        """add_case_rule rejects expire_after_resolved when timeframe is not set."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_case = Case({"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "normal"})
        mock_ds.case.get.return_value = mock_case

        user = MagicMock()
        user.uname = "analyst1"

        with pytest.raises(InvalidDataException, match="expire after resolved"):
            case_service.add_case_rule(
                "case-001",
                {"query": "*:*", "destination": "alerts/all", "expire_after_resolved": True},
                user,
            )

    @patch("howler.services.case_service.datastore")
    def test_add_rule_strips_created_at(self, mock_ds_fn):
        """add_case_rule ignores client-supplied created_at."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_case = Case({"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "normal"})
        mock_ds.case.get.return_value = mock_case

        user = MagicMock()
        user.uname = "analyst1"

        result = case_service.add_case_rule(
            "case-001",
            {"query": "*:*", "destination": "alerts/all", "created_at": "1999-01-01T00:00:00Z"},
            user,
        )

        # created_at should be auto-generated ("NOW"), not the client value
        assert result.rules[0].created_at is not None

    @patch("howler.services.case_service.datastore")
    def test_update_rule_sets_expire_after_resolved(self, mock_ds_fn):
        """update_case_rule can toggle expire_after_resolved."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        rule = CaseRule({"query": "*:*", "destination": "alerts/all", "author": "admin", "timeframe": 14})
        mock_case = Case({"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "normal"})
        mock_case.rules.append(rule)
        mock_ds.case.get.return_value = mock_case

        user = MagicMock()
        user.uname = "analyst1"

        result = case_service.update_case_rule("case-001", rule.rule_id, {"expire_after_resolved": True}, user)

        assert result.rules[0].expire_after_resolved is True

    @patch("howler.services.case_service.datastore")
    def test_update_rule_sets_timeframe(self, mock_ds_fn):
        """update_case_rule can update timeframe days."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        rule = CaseRule({"query": "*:*", "destination": "alerts/all", "author": "admin", "timeframe": 14})
        mock_case = Case({"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "normal"})
        mock_case.rules.append(rule)
        mock_ds.case.get.return_value = mock_case

        user = MagicMock()
        user.uname = "analyst1"

        result = case_service.update_case_rule("case-001", rule.rule_id, {"timeframe": 30}, user)

        assert result.rules[0].timeframe == 30

    @patch("howler.services.case_service.datastore")
    def test_update_rule_rejects_expire_after_resolved_without_timeframe(self, mock_ds_fn):
        """update_case_rule rejects enabling expire_after_resolved when timeframe is None."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        rule = CaseRule({"query": "*:*", "destination": "alerts/all", "author": "admin", "timeframe": None})
        mock_case = Case({"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "normal"})
        mock_case.rules.append(rule)
        mock_ds.case.get.return_value = mock_case

        user = MagicMock()
        user.uname = "analyst1"

        with pytest.raises(InvalidDataException, match="expire after resolved"):
            case_service.update_case_rule("case-001", rule.rule_id, {"expire_after_resolved": True}, user)


# ---------------------------------------------------------------------------
# Helpers for log-related tests
# ---------------------------------------------------------------------------


from howler.odm.models.case import CaseLog


def _make_log(explanation: str, timestamp: str = "2026-01-01T00:00:00.000000Z") -> CaseLog:
    return CaseLog({"timestamp": timestamp, "explanation": explanation, "user": "system"})


def _make_log_change(key: str, prev: str, new: str, timestamp: str) -> CaseLog:
    return CaseLog(
        {
            "timestamp": timestamp,
            "key": key,
            "previous_value": prev,
            "new_value": new,
            "user": "system",
            "explanation": f"Updated {key} from '{prev}' to '{new}'",
        }
    )


# ---------------------------------------------------------------------------
# CaseItem.classification — propagation from hit / event
# ---------------------------------------------------------------------------


class TestCaseItemClassificationPropagation:
    """Tests that append_hit / append_event copy the record's classification onto the item."""

    @patch("howler.services.case_service.recompute_case_metadata")
    @patch("howler.services.case_service.add_backreference")
    @patch("howler.services.case_service.datastore")
    def test_append_hit_copies_classification(self, mock_ds_fn, _mock_backref, _mock_sync):
        """append_hit sets item.classification from the fetched hit."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_case = MagicMock()
        mock_case.case_id = "case-001"
        mock_case.items = []
        mock_ds.case.get.return_value = mock_case
        mock_ds.case.save.return_value = True

        mock_hit = MagicMock()
        mock_hit.classification = "RESTRICTED"
        mock_ds.hit.get.return_value = mock_hit

        item = CaseItem({"type": "hit", "value": "hit-001", "name": "hit-001"})
        case_service.append_hit(mock_case, item)

        assert item.classification.value == CLASSIFICATION.normalize_classification("RESTRICTED")

    @patch("howler.services.case_service.recompute_case_metadata")
    @patch("howler.services.case_service.add_backreference")
    @patch("howler.services.case_service.datastore")
    def test_append_hit_overwrites_any_existing_classification(self, mock_ds_fn, _mock_backref, _mock_sync):
        """append_hit overwrites any classification already set on the item with the hit's value."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_case = MagicMock()
        mock_case.case_id = "case-001"
        mock_case.items = []
        mock_ds.case.get.return_value = mock_case
        mock_ds.case.save.return_value = True

        mock_hit = MagicMock()
        mock_hit.classification = "UNRESTRICTED"
        mock_ds.hit.get.return_value = mock_hit

        item = CaseItem({"type": "hit", "value": "hit-001", "name": "hit-001"})
        case_service.append_hit(mock_case, item)

        assert item.classification.value == CLASSIFICATION.normalize_classification("UNRESTRICTED")

    @patch("howler.services.case_service.recompute_case_metadata")
    @patch("howler.services.case_service.add_backreference")
    @patch("howler.services.case_service.datastore")
    def test_append_event_copies_classification(self, mock_ds_fn, _mock_backref, _mock_sync):
        """append_event sets item.classification from the fetched event."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_case = MagicMock()
        mock_case.case_id = "case-001"
        mock_case.items = []
        mock_ds.case.get.return_value = mock_case
        mock_case.save.return_value = True

        mock_event = MagicMock()
        mock_event.classification = "RESTRICTED"
        mock_event.howler.id = "event-001"
        mock_ds.event.get.return_value = mock_event

        item = CaseItem({"type": "event", "value": "event-001", "name": "event-001"})
        case_service.append_event(mock_case, item)

        assert item.classification.value == CLASSIFICATION.normalize_classification("RESTRICTED")

    @patch("howler.services.case_service.recompute_case_metadata")
    @patch("howler.services.case_service.add_backreference")
    @patch("howler.services.case_service.datastore")
    def test_append_event_copies_unrestricted_classification(self, mock_ds_fn, _mock_backref, _mock_sync):
        """append_event sets item.classification even when the event is UNRESTRICTED."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_case = MagicMock()
        mock_case.case_id = "case-001"
        mock_case.items = []
        mock_ds.case.get.return_value = mock_case
        mock_case.save.return_value = True

        mock_event = MagicMock()
        mock_event.classification = "UNRESTRICTED"
        mock_event.howler.id = "event-001"
        mock_ds.event.get.return_value = mock_event

        item = CaseItem({"type": "event", "value": "event-001", "name": "event-001"})
        case_service.append_event(mock_case, item)

        assert item.classification.value == CLASSIFICATION.normalize_classification("UNRESTRICTED")


# ---------------------------------------------------------------------------
# filter_case_items_by_classification()
# ---------------------------------------------------------------------------


class TestFilterCaseItemsByClassification:
    """Tests for case_service.filter_case_items_by_classification."""

    @patch("howler.services.case_service.CLASSIFICATION")
    def test_items_without_classification_always_included(self, mock_cl):
        """Items with no classification field are always visible regardless of user level."""
        mock_cl.is_accessible.return_value = False  # would block if called

        case = {
            "case_id": "case-001",
            "items": [
                {"type": "reference", "value": "http://example.com", "classification": None, "name": "link"},
                {"type": "case", "value": "child-id", "classification": None, "name": "child"},
            ],
        }

        case_service.filter_case_items_by_classification(case, "UNRESTRICTED")

        assert len(case["items"]) == 2
        mock_cl.is_accessible.assert_not_called()

    @patch("howler.services.case_service.CLASSIFICATION")
    def test_accessible_classified_items_included(self, mock_cl):
        """Items whose classification is accessible to the user are kept."""
        mock_cl.is_accessible.return_value = True

        case = {
            "case_id": "case-001",
            "items": [
                {"type": "hit", "value": "hit-001", "classification": "RESTRICTED", "name": "hit-001"},
            ],
        }

        case_service.filter_case_items_by_classification(case, "RESTRICTED")

        assert len(case["items"]) == 1
        mock_cl.is_accessible.assert_called_once_with("RESTRICTED", "RESTRICTED")

    @patch("howler.services.case_service.CLASSIFICATION")
    def test_inaccessible_classified_items_removed(self, mock_cl):
        """Items whose classification exceeds the user's level are filtered out."""
        mock_cl.is_accessible.return_value = False

        case = {
            "case_id": "case-001",
            "items": [
                {"type": "hit", "value": "hit-001", "classification": "RESTRICTED", "name": "hit-001"},
            ],
        }

        case_service.filter_case_items_by_classification(case, "UNRESTRICTED")

        assert len(case["items"]) == 0
        mock_cl.is_accessible.assert_called_once_with("UNRESTRICTED", "RESTRICTED")

    @patch("howler.services.case_service.CLASSIFICATION")
    def test_mixed_items_partial_filter(self, mock_cl):
        """Only inaccessible items are removed; accessible and unclassified items remain."""
        mock_cl.is_accessible.side_effect = lambda user_c12n, item_c12n: item_c12n == "UNRESTRICTED"

        case = {
            "case_id": "case-001",
            "items": [
                {"type": "hit", "value": "hit-u", "classification": "UNRESTRICTED", "name": "hit-u"},
                {"type": "hit", "value": "hit-r", "classification": "RESTRICTED", "name": "hit-r"},
                {"type": "reference", "value": "http://example.com", "classification": None, "name": "link"},
            ],
        }

        case_service.filter_case_items_by_classification(case, "UNRESTRICTED")

        values = [item["value"] for item in case["items"]]
        assert "hit-u" in values
        assert "http://example.com" in values
        assert "hit-r" not in values

    @patch("howler.services.case_service.CLASSIFICATION")
    def test_empty_items_list(self, mock_cl):
        """An empty items list stays empty after filtering."""
        case = {"case_id": "case-001", "items": []}

        case_service.filter_case_items_by_classification(case, "UNRESTRICTED")

        assert case["items"] == []
        mock_cl.is_accessible.assert_not_called()

    @patch("howler.services.case_service.CLASSIFICATION")
    def test_missing_items_key_treated_as_empty(self, mock_cl):
        """A case dict with no 'items' key is handled gracefully."""
        case = {"case_id": "case-001"}

        case_service.filter_case_items_by_classification(case, "UNRESTRICTED")

        assert case.get("items", None) is None

    @patch("howler.services.case_service.CLASSIFICATION")
    def test_returns_same_dict_object(self, mock_cl):
        """filter_case_items_by_classification mutates and returns the same dict."""
        mock_cl.is_accessible.return_value = True

        case = {
            "case_id": "case-001",
            "items": [{"type": "hit", "value": "hit-001", "classification": "UNRESTRICTED", "name": "p"}],
        }
        original_id = id(case)

        case_service.filter_case_items_by_classification(case, "UNRESTRICTED")

        assert id(case) == original_id


# ---------------------------------------------------------------------------
# append_folder()
# ---------------------------------------------------------------------------


class TestAppendFolder:
    """Tests for case_service.append_case_item with folder items."""

    @patch("howler.services.case_service.datastore")
    def test_append_folder_adds_item(self, mock_ds_fn):
        """append_case_item appends a folder item and saves the case."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_case = MagicMock()
        mock_case.case_id = "case-001"
        mock_case.items = []
        mock_ds.case.get.return_value = mock_case
        mock_case.save.return_value = True

        item = CaseItem({"type": "folder", "name": "My Folder"})
        case_service.append_case_item("case-001", item=item)

        assert len(mock_case.items) == 1
        mock_case.save.assert_called_once()

    @patch("howler.services.case_service.datastore")
    def test_append_folder_missing_case_raises(self, mock_ds_fn):
        """append_case_item raises NotFoundException when case does not exist."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.get.return_value = None

        item = CaseItem({"type": "folder", "name": "Folder"})
        with pytest.raises(NotFoundException):
            case_service.append_case_item("nonexistent", item=item)

    @patch("howler.services.case_service.datastore")
    def test_append_folder_duplicate_same_parent_raises(self, mock_ds_fn):
        """append_case_item raises InvalidDataException for duplicate folder name under same parent."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        existing = CaseItem({"type": "folder", "name": "My Folder"})
        mock_case = MagicMock()
        mock_case.case_id = "case-001"
        mock_case.items = [existing]
        mock_ds.case.get.return_value = mock_case

        item = CaseItem({"type": "folder", "name": "My Folder"})
        with pytest.raises(InvalidDataException, match="already exists"):
            case_service.append_case_item("case-001", item=item)


# ---------------------------------------------------------------------------
# append_markdown()
# ---------------------------------------------------------------------------


class TestAppendMarkdown:
    """Tests for case_service.append_case_item with markdown items."""

    @patch("howler.services.case_service.datastore")
    def test_append_markdown_adds_item(self, mock_ds_fn):
        """append_case_item appends a markdown item and saves the case."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_case = MagicMock()
        mock_case.case_id = "case-001"
        mock_case.items = []
        mock_ds.case.get.return_value = mock_case
        mock_case.save.return_value = True

        item = CaseItem({"type": "markdown", "value": "# Hello\n\nWorld"})
        case_service.append_case_item("case-001", item=item)

        assert len(mock_case.items) == 1
        mock_case.save.assert_called_once()

    @patch("howler.services.case_service.datastore")
    def test_append_markdown_missing_case_raises(self, mock_ds_fn):
        """append_case_item raises NotFoundException when case does not exist."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.get.return_value = None

        item = CaseItem({"type": "markdown", "value": "content"})
        with pytest.raises(NotFoundException):
            case_service.append_case_item("nonexistent", item=item)


# ---------------------------------------------------------------------------
# move_case_item()
# ---------------------------------------------------------------------------


class TestMoveCaseItem:
    """Tests for case_service.move_case_item."""

    @patch("howler.services.case_service.datastore")
    def test_move_item_to_folder(self, mock_ds_fn):
        """move_case_item updates the parent and saves."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        folder = CaseItem({"type": "folder", "name": "Folder"})
        item = CaseItem({"type": "hit", "value": "hit-001"})

        mock_case = MagicMock()
        mock_case.case_id = "case-001"
        mock_case.items = [folder, item]
        mock_ds.case.get.return_value = mock_case
        mock_ds.case.save.return_value = True

        case_service.move_case_item("case-001", item.id, folder.id)

        assert item.parent == folder.id
        mock_case.save.assert_called_once_with(refresh=None)

    @patch("howler.services.case_service.datastore")
    def test_move_item_to_root(self, mock_ds_fn):
        """move_case_item moves item to root when new_parent is None."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        folder = CaseItem({"type": "folder", "name": "Folder"})
        item = CaseItem({"type": "hit", "value": "hit-001", "parent": folder.id})

        mock_case = MagicMock()
        mock_case.case_id = "case-001"
        mock_case.items = [folder, item]
        mock_ds.case.get.return_value = mock_case
        mock_ds.case.save.return_value = True

        case_service.move_case_item("case-001", item.id, None)

        assert item.parent is None
        mock_case.save.assert_called_once_with(refresh=None)

    @patch("howler.services.case_service.datastore")
    def test_move_case_item_type_to_subfolder_raises(self, mock_ds_fn):
        """move_case_item raises InvalidDataException when moving a case item to a folder."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        folder = CaseItem({"type": "folder", "name": "Folder"})
        case_item = CaseItem({"type": "case", "value": "child-001"})

        mock_case = MagicMock()
        mock_case.case_id = "parent-001"
        mock_case.items = [folder, case_item]
        mock_ds.case.get.return_value = mock_case

        with pytest.raises(InvalidDataException, match="root-level"):
            case_service.move_case_item("parent-001", case_item.id, folder.id)

    @patch("howler.services.case_service.datastore")
    def test_move_missing_case_raises(self, mock_ds_fn):
        """move_case_item raises NotFoundException when case does not exist."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.get.return_value = None

        with pytest.raises(NotFoundException):
            case_service.move_case_item("nonexistent", "item-id", None)

    @patch("howler.services.case_service.datastore")
    def test_move_missing_item_raises(self, mock_ds_fn):
        """move_case_item raises NotFoundException when item does not exist."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_case = MagicMock()
        mock_case.case_id = "case-001"
        mock_case.items = []
        mock_ds.case.get.return_value = mock_case

        with pytest.raises(NotFoundException):
            case_service.move_case_item("case-001", "nonexistent-item", None)

    @patch("howler.services.case_service.datastore")
    def test_move_folder_into_own_child_raises(self, mock_ds_fn):
        """move_case_item prevents cycle by rejecting move of a folder under its descendant."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        parent_folder = CaseItem({"type": "folder", "name": "Parent"})
        child_folder = CaseItem({"type": "folder", "name": "Child", "parent": parent_folder.id})

        mock_case = MagicMock()
        mock_case.case_id = "case-001"
        mock_case.items = [parent_folder, child_folder]
        mock_ds.case.get.return_value = mock_case

        with pytest.raises(InvalidDataException, match="descendant"):
            case_service.move_case_item("case-001", parent_folder.id, child_folder.id)


# ---------------------------------------------------------------------------
# remove_case_items()
# ---------------------------------------------------------------------------


class TestRemoveCaseItemsByIds:
    """Tests for case_service.remove_case_items."""

    @patch("howler.services.case_service.recompute_case_metadata")
    @patch("howler.services.case_service.datastore")
    def test_remove_item_by_id(self, mock_ds_fn, mock_sync):
        """remove_case_items removes a single item by its UUID."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        item = CaseItem({"type": "reference", "value": "https://example.com"})

        mock_case = MagicMock()
        mock_case.case_id = "case-001"
        mock_case.items = [item]
        mock_ds.case.get.return_value = mock_case
        mock_ds.case.save.return_value = True

        case_service.remove_case_items("case-001", [item.id])

        assert item not in mock_case.items
        mock_case.save.assert_called_once_with(refresh=None)

    @patch("howler.services.case_service.datastore")
    def test_remove_missing_case_raises(self, mock_ds_fn):
        """Raises NotFoundException when case does not exist."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.get.return_value = None

        with pytest.raises(NotFoundException):
            case_service.remove_case_items("nonexistent", ["some-id"])

    @patch("howler.services.case_service.datastore")
    def test_remove_missing_item_raises(self, mock_ds_fn):
        """Raises NotFoundException when item id is not in the case."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_case = MagicMock()
        mock_case.case_id = "case-001"
        mock_case.items = []
        mock_ds.case.get.return_value = mock_case

        with pytest.raises(NotFoundException):
            case_service.remove_case_items("case-001", ["nonexistent-id"])

    @patch("howler.services.case_service.datastore")
    def test_remove_non_empty_folder_without_force_raises(self, mock_ds_fn):
        """Raises InvalidDataException when removing a non-empty folder without force."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        folder = CaseItem({"type": "folder", "name": "Folder"})
        child = CaseItem({"type": "hit", "value": "hit-001", "parent": folder.id})

        mock_case = MagicMock()
        mock_case.case_id = "case-001"
        mock_case.items = [folder, child]
        mock_ds.case.get.return_value = mock_case

        with pytest.raises(InvalidDataException, match="not empty"):
            case_service.remove_case_items("case-001", [folder.id], force=False)

    @patch("howler.services.case_service.recompute_case_metadata")
    @patch("howler.services.case_service.datastore")
    def test_remove_non_empty_folder_with_force(self, mock_ds_fn, mock_sync):
        """remove_case_items with force=True removes a folder and its children."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        folder = CaseItem({"type": "folder", "name": "Folder"})
        child = CaseItem({"type": "reference", "value": "https://test.com", "parent": folder.id})

        mock_case = MagicMock()
        mock_case.case_id = "case-001"
        mock_case.items = [folder, child]
        mock_ds.case.get.return_value = mock_case
        mock_ds.case.save.return_value = True

        case_service.remove_case_items("case-001", [folder.id], force=True)

        assert len(mock_case.items) == 0
        mock_case.save.assert_called_once_with(refresh=None)


# ---------------------------------------------------------------------------
# _is_descendant()
# ---------------------------------------------------------------------------


class TestIsDescendant:
    """Tests for case_service._is_descendant cycle detection."""

    def test_direct_descendant(self):
        """Child is a direct descendant of parent."""
        parent = CaseItem({"type": "folder", "name": "P"})
        child = CaseItem({"type": "folder", "name": "C", "parent": parent.id})

        assert case_service._is_descendant([parent, child], child.id, parent.id) is True

    def test_not_descendant(self):
        """Unrelated items are not descendants."""
        a = CaseItem({"type": "folder", "name": "A"})
        b = CaseItem({"type": "folder", "name": "B"})

        assert case_service._is_descendant([a, b], b.id, a.id) is False

    def test_deep_descendant(self):
        """Grandchild is a descendant of grandparent."""
        gp = CaseItem({"type": "folder", "name": "GP"})
        p = CaseItem({"type": "folder", "name": "P", "parent": gp.id})
        c = CaseItem({"type": "folder", "name": "C", "parent": p.id})

        assert case_service._is_descendant([gp, p, c], c.id, gp.id) is True

    def test_cycle_terminates_without_match(self):
        """_is_descendant breaks out of cycles in the item tree without looping forever."""
        a = CaseItem({"type": "folder", "name": "A"})
        b = CaseItem({"type": "folder", "name": "B", "parent": a.id})
        # Introduce a cycle: a.parent → b (normally impossible in a valid tree)
        a.parent = b.id

        # Neither a nor b is a descendant of "unrelated-id" — should return False
        result = case_service._is_descendant([a, b], a.id, "unrelated-id")
        assert result is False


# ---------------------------------------------------------------------------
# create_case() — with items
# ---------------------------------------------------------------------------


class TestCreateCaseWithItems:
    """Tests for create_case when the items list is non-empty."""

    @patch("howler.services.case_service.append_case_item")
    @patch("howler.services.case_service.datastore")
    def test_create_case_with_items_appends_and_fetches_updated(self, mock_ds_fn, mock_append_item):
        """create_case calls append_case_item for each item and re-fetches the updated case."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        updated_case = Case({"case_id": "case-001", "title": "T", "summary": "S"})
        mock_ds.case.get.return_value = updated_case

        result = case_service.create_case(
            {"title": "T", "summary": "S", "items": [{"type": "reference", "value": "https://x.com", "name": "ref"}]},
            user=_make_user(),
        )

        mock_append_item.assert_called_once()
        mock_ds.case.get.assert_called_once()
        assert result is updated_case

    @patch("howler.services.case_service.append_case_item")
    @patch("howler.services.case_service.datastore")
    def test_create_case_with_items_raises_when_updated_case_missing(self, mock_ds_fn, mock_append_item):
        """create_case raises HowlerValueError when the updated case cannot be re-fetched."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_ds.case.get.return_value = None

        with pytest.raises(HowlerValueError, match="Error occurred when creating case"):
            case_service.create_case(
                {
                    "title": "T",
                    "summary": "S",
                    "items": [{"type": "reference", "value": "https://x.com", "name": "ref"}],
                },
                user=_make_user(),
            )

    @patch("howler.services.case_service.append_case_item")
    @patch("howler.services.case_service.datastore")
    def test_create_case_with_items_filters_returned_case(self, mock_ds_fn, mock_append_item):
        """create_case removes inaccessible items from the fetched case before returning it."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        updated_case = Case(
            {
                "case_id": "case-001",
                "title": "T",
                "summary": "S",
                "items": [
                    {"type": "reference", "value": "https://visible.example", "name": "visible"},
                    {
                        "type": "reference",
                        "value": "https://hidden.example",
                        "name": "hidden",
                        "classification": CLASSIFICATION.RESTRICTED,
                    },
                ],
            }
        )
        mock_ds.case.get.return_value = updated_case

        result = case_service.create_case(
            {
                "title": "T",
                "summary": "S",
                "items": [{"type": "reference", "value": "https://x.com", "name": "ref"}],
            },
            user=_make_user(classification=CLASSIFICATION.UNRESTRICTED),
        )

        assert [item.value for item in result.items] == ["https://visible.example"]


# ---------------------------------------------------------------------------
# get_last_resolved_time() — datetime edge cases
# ---------------------------------------------------------------------------


class TestGetLastResolvedTimeDatetimeEdgeCases:
    """Tests for get_last_resolved_time covering datetime timezone branches."""

    def test_naive_datetime_gets_utc_added(self):
        """get_last_resolved_time attaches UTC tzinfo to a naive datetime timestamp."""
        naive_ts = datetime(2026, 3, 10, 12, 0, 0)  # no tzinfo
        assert naive_ts.tzinfo is None

        mock_entry = MagicMock()
        mock_entry.key = "status"
        mock_entry.new_value = "resolved"
        mock_entry.timestamp = naive_ts

        mock_case = MagicMock()
        mock_case.log = [mock_entry]

        result = case_service.get_last_resolved_time(mock_case)

        assert result is not None
        assert result.tzinfo is not None
        assert result.year == 2026
        assert result.month == 3

    def test_unparseable_timestamp_is_skipped(self):
        """get_last_resolved_time skips log entries with unparseable timestamps."""
        bad_entry = MagicMock()
        bad_entry.key = "status"
        bad_entry.new_value = "resolved"
        bad_entry.timestamp = "not-a-date-at-all"

        mock_case = MagicMock()
        mock_case.log = [bad_entry]

        # No valid resolved timestamp → should return None
        result = case_service.get_last_resolved_time(mock_case)
        assert result is None


# ---------------------------------------------------------------------------
# get_parent_from_path()
# ---------------------------------------------------------------------------


class TestGetParentFromPath:
    """Tests for case_service.get_parent_from_path."""

    @patch("howler.services.case_service.datastore")
    def test_string_case_id_is_fetched_from_datastore(self, mock_ds_fn):
        """get_parent_from_path fetches the case by string ID before processing the path."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        case = Case({"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "normal"})
        mock_ds.case.get.return_value = case

        result = case_service.get_parent_from_path("case-001", "/")

        mock_ds.case.get.assert_called_once_with("case-001")
        assert result is None  # "/" returns None (root path)

    def test_slash_only_path_returns_none(self):
        """get_parent_from_path returns None for a path consisting entirely of slashes."""
        case = Case({"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "normal"})
        case.items = []

        result = case_service.get_parent_from_path(case, "///")

        assert result is None

    def test_missing_folder_without_create_returns_none(self):
        """get_parent_from_path returns None when a path segment is missing and create_if_missing=False."""
        case = Case({"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "normal"})
        case.items = []  # no folders

        result = case_service.get_parent_from_path(case, "nonexistent/subfolder", create_if_missing=False)

        assert result is None

    def test_none_case_raises_not_found(self):
        """get_parent_from_path raises NotFoundException when the case resolves to None."""
        with pytest.raises(NotFoundException):
            case_service.get_parent_from_path(None, "some/path")

    @patch("howler.odm.models.case.Case.save")
    def test_deeply_nested_path_creates_all_folders_without_persisting(self, mock_save):
        """With persist=False, every folder in a deep path is created in memory without saving."""
        case = Case({"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "normal"})
        case.items = []

        parts = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"]
        result = case_service.get_parent_from_path(case, "/".join(parts), create_if_missing=True, persist=False)

        mock_save.assert_not_called()

        folders = [item for item in case.items if item.type == "folder"]
        assert len(folders) == len(parts)

        # Walk the returned leaf folder back up to the root via parent pointers.
        names_leaf_to_root = []
        current = result
        while current is not None:
            names_leaf_to_root.append(current.name)
            current = next((item for item in case.items if item.id == current.parent), None)

        assert names_leaf_to_root == list(reversed(parts))


# ---------------------------------------------------------------------------
# check_conflicts()
# ---------------------------------------------------------------------------


class TestCheckConflicts:
    """Tests for case_service.check_conflicts."""

    def test_item_with_none_name_skips_conflict_check(self):
        """check_conflicts returns immediately without checking when item.name is None."""
        existing = CaseItem({"type": "hit", "value": "existing", "name": "taken"})
        mock_case = MagicMock()
        mock_case.items = [existing]

        item = MagicMock()
        item.name = None

        # Should not raise even though there is an item named "taken" in the case
        case_service.check_conflicts(mock_case, item)


# ---------------------------------------------------------------------------
# _ensure_parent_exists()
# ---------------------------------------------------------------------------


class TestEnsureParentExists:
    """Tests for case_service._ensure_parent_exists."""

    def test_raises_when_parent_not_found(self):
        """_ensure_parent_exists raises InvalidDataException when the parent ID does not exist."""
        mock_case = MagicMock()
        mock_case.items = []

        with pytest.raises(InvalidDataException, match="does not exist"):
            case_service._ensure_parent_exists(mock_case, "nonexistent-parent-id")

    def test_raises_when_parent_is_not_folder(self):
        """_ensure_parent_exists raises InvalidDataException when the parent item is not a folder."""
        hit_item = CaseItem({"type": "hit", "value": "hit-001", "name": "hit"})
        mock_case = MagicMock()
        mock_case.items = [hit_item]

        with pytest.raises(InvalidDataException, match="is not a folder"):
            case_service._ensure_parent_exists(mock_case, hit_item.id)


# ---------------------------------------------------------------------------
# move_case_item() — name conflict in destination
# ---------------------------------------------------------------------------


class TestMoveCaseItemNameConflict:
    """Tests for move_case_item name-conflict detection at the destination."""

    @patch("howler.services.case_service.datastore")
    def test_move_raises_when_name_already_exists_in_destination(self, mock_ds_fn):
        """move_case_item raises InvalidDataException when the destination already has an item with the same name."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        folder_a = CaseItem({"type": "folder", "name": "FolderA"})
        folder_b = CaseItem({"type": "folder", "name": "FolderB"})
        item_to_move = CaseItem({"type": "hit", "value": "hit-001", "name": "Report", "parent": folder_a.id})
        sibling_in_b = CaseItem({"type": "hit", "value": "hit-002", "name": "Report", "parent": folder_b.id})

        mock_case = MagicMock()
        mock_case.case_id = "case-001"
        mock_case.items = [folder_a, folder_b, item_to_move, sibling_in_b]
        mock_ds.case.get.return_value = mock_case

        with pytest.raises(InvalidDataException, match="already exists"):
            case_service.move_case_item("case-001", item_to_move.id, folder_b.id)


# ---------------------------------------------------------------------------
# recompute_case_metadata() — missing hit
# ---------------------------------------------------------------------------


class TestSyncCaseMetadataMissingHit:
    """Test recompute_case_metadata skips a hit item when the backing hit is not found."""

    @patch("howler.services.case_service.datastore")
    def test_sync_skips_hit_not_in_datastore(self, mock_ds_fn):
        """recompute_case_metadata continues gracefully when ds.hit.get returns None."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        hit_item = CaseItem({"type": "hit", "value": "hit-missing", "name": "hit-missing"})

        mock_case = MagicMock()
        mock_case.items = [hit_item]

        mock_ds.hit.get.return_value = None

        case_service.recompute_case_metadata(mock_case)

        mock_case.save.assert_not_called()
        assert mock_case.targets == []
        assert mock_case.threats == []
        assert mock_case.indicators == []


# ---------------------------------------------------------------------------
# rename_case_item() — folder item updates .value
# ---------------------------------------------------------------------------


class TestRenameCaseItemFolder:
    """Tests that rename_case_item also updates item.value for folder items."""

    @patch("howler.services.case_service.datastore")
    def test_rename_folder_updates_value(self, mock_ds_fn):
        """rename_case_item sets item.value = new name when the item is a folder."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        folder = CaseItem({"type": "folder", "name": "Old Folder"})
        mock_case = MagicMock()
        mock_case.case_id = "case-001"
        mock_case.items = [folder]
        mock_case.save.return_value = True
        mock_ds.case.get.return_value = mock_case

        case_service.rename_case_item("case-001", folder.id, "New Folder")

        assert folder.name == "New Folder"
        assert folder.value == "New Folder"
        mock_case.save.assert_called_once_with(refresh=None)


# ---------------------------------------------------------------------------
# update_case_rule() — invalid timeframe value
# ---------------------------------------------------------------------------


class TestUpdateCaseRuleInvalidTimeframe:
    """Tests for update_case_rule timeframe validation."""

    @patch("howler.services.case_service.datastore")
    def test_update_rule_zero_timeframe_raises(self, mock_ds_fn):
        """update_case_rule raises HowlerValueError when timeframe is set to 0."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        rule = CaseRule({"query": "*:*", "destination": "alerts/all", "author": "admin", "timeframe": 14})
        mock_case = Case({"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "normal"})
        mock_case.rules.append(rule)
        mock_ds.case.get.return_value = mock_case

        user = MagicMock()
        user.uname = "analyst1"

        with pytest.raises(HowlerValueError, match="positive integer"):
            case_service.update_case_rule("case-001", rule.rule_id, {"timeframe": 0}, user)

    @patch("howler.services.case_service.datastore")
    def test_update_rule_negative_timeframe_raises(self, mock_ds_fn):
        """update_case_rule raises HowlerValueError when timeframe is negative."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        rule = CaseRule({"query": "*:*", "destination": "alerts/all", "author": "admin", "timeframe": 7})
        mock_case = Case({"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "normal"})
        mock_case.rules.append(rule)
        mock_ds.case.get.return_value = mock_case

        user = MagicMock()
        user.uname = "analyst1"

        with pytest.raises(HowlerValueError, match="positive integer"):
            case_service.update_case_rule("case-001", rule.rule_id, {"timeframe": -5}, user)
