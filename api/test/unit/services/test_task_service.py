"""Unit tests for searching case tasks."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from howler.common.exceptions import ForbiddenException
from howler.config import CLASSIFICATION
from howler.services import task_service


def _task(
    task_id: str,
    *,
    assignment: str | None = "alice",
    complete: bool = False,
    summary: str | None = None,
) -> dict:
    return {
        "id": task_id,
        "assignment": assignment,
        "complete": complete,
        "summary": summary or task_id,
        "item": None,
    }


def _user(uname: str = "alice"):
    return SimpleNamespace(
        uname=uname,
        access_control="classification:UNRESTRICTED",
        classification=CLASSIFICATION.UNRESTRICTED,
    )


def _case(case_id: str, tasks: list[dict], **overrides) -> dict:
    case_data = {
        "case_id": case_id,
        "title": f"Case {case_id}",
        "status": "open",
        "tasks": tasks,
        "items": [
            {"id": "visible-item", "name": "Visible item", "classification": CLASSIFICATION.UNRESTRICTED},
            {"id": "restricted-item", "name": "Restricted item", "classification": "RESTRICTED"},
        ],
    }
    case_data.update(overrides)
    return case_data


class TestSearchTasks:
    """Tests for the task-level filtering and pagination service."""

    @patch("howler.services.task_service.datastore")
    def test_paginates_within_a_single_case_and_returns_minimal_context(self, mock_datastore):
        user = _user()
        case = _case("case-1", [_task("d"), _task("b"), _task("a"), _task("c")])
        stream = MagicMock()
        stream.__iter__.return_value = iter([case])
        mock_datastore.return_value.case.stream_search.return_value = stream

        result = task_service.search_tasks(user, offset=1, rows=2, task_filter="all")

        assert [entry["task"]["id"] for entry in result["items"]] == ["b", "c"]
        assert result["has_more"] is True
        assert result["offset"] == 1
        assert result["rows"] == 2
        assert result["items"][0]["case"] == {
            "__index": "case",
            "case_id": "case-1",
            "title": "Case case-1",
            "status": "open",
            "items": [
                {
                    "id": "visible-item",
                    "name": "Visible item",
                    "classification": CLASSIFICATION.UNRESTRICTED,
                }
            ],
        }
        assert "tasks" not in result["items"][0]["case"]
        stream.close.assert_called_once_with()

    @patch("howler.services.task_service.datastore")
    def test_filters_tasks_by_authenticated_assignee_and_completion_state(self, mock_datastore):
        user = _user()
        case = _case(
            "case-1",
            [
                _task("alice-incomplete"),
                _task("alice-complete", complete=True),
                _task("bob-incomplete", assignment="bob"),
                _task("unassigned", assignment=None),
            ],
        )
        mock_datastore.return_value.case.stream_search.side_effect = lambda *args, **kwargs: iter([case])

        all_tasks = task_service.search_tasks(user, rows=10, task_filter="all")
        complete_tasks = task_service.search_tasks(user, rows=10, task_filter="complete")
        incomplete_tasks = task_service.search_tasks(user, rows=10, task_filter="incomplete")

        assert [entry["task"]["id"] for entry in all_tasks["items"]] == ["alice-complete", "alice-incomplete"]
        assert [entry["task"]["id"] for entry in complete_tasks["items"]] == ["alice-complete"]
        assert [entry["task"]["id"] for entry in incomplete_tasks["items"]] == ["alice-incomplete"]

    @patch("howler.services.task_service.datastore")
    def test_uses_sanitized_authenticated_username_and_case_access_control(self, mock_datastore):
        user = _user('alice+"analyst')
        mock_datastore.return_value.case.stream_search.return_value = iter([])

        task_service.search_tasks(user)

        mock_datastore.return_value.case.stream_search.assert_called_once_with(
            'tasks.assignment:"alice\\+\\"analyst"',
            fl=task_service._CASE_SEARCH_FIELDS,
            access_control=user.access_control,
            as_obj=False,
        )

    @patch("howler.services.task_service.datastore")
    def test_has_more_is_false_beyond_the_end(self, mock_datastore):
        user = _user()
        case = _case("case-1", [_task("a"), _task("b")])
        mock_datastore.return_value.case.stream_search.return_value = iter([case])

        result = task_service.search_tasks(user, offset=5, rows=2, task_filter="all")

        assert result["items"] == []
        assert result["has_more"] is False

    @patch("howler.services.task_service.datastore")
    def test_stops_and_closes_case_stream_after_finding_one_more_task(self, mock_datastore):
        user = _user()
        case = _case("case-1", [_task("a"), _task("b"), _task("c")])
        stream = MagicMock()
        stream.__iter__.return_value = iter([case])
        mock_datastore.return_value.case.stream_search.return_value = stream

        result = task_service.search_tasks(user, rows=2, task_filter="all")

        assert len(result["items"]) == 2
        assert result["has_more"] is True
        stream.close.assert_called_once_with()

    @patch("howler.services.task_service.datastore")
    def test_paginates_across_case_task_arrays_and_detects_more_across_case_boundary(self, mock_datastore):
        user = _user()
        cases = [
            _case("case-1", [_task("b"), _task("a")]),
            _case("case-2", [_task("d"), _task("c")]),
        ]
        mock_datastore.return_value.case.stream_search.return_value = iter(cases)

        result = task_service.search_tasks(user, offset=2, rows=1, task_filter="all")

        assert [entry["task"]["id"] for entry in result["items"]] == ["c"]
        assert result["has_more"] is True

    @patch("howler.services.task_service.datastore")
    def test_exact_end_page_has_no_more_results(self, mock_datastore):
        user = _user()
        case = _case("case-1", [_task("b"), _task("a")])
        mock_datastore.return_value.case.stream_search.return_value = iter([case])

        result = task_service.search_tasks(user, rows=2, task_filter="all")

        assert [entry["task"]["id"] for entry in result["items"]] == ["a", "b"]
        assert result["has_more"] is False

    @patch("howler.services.task_service.datastore")
    def test_missing_access_control_fails_closed(self, mock_datastore):
        user = _user()
        user.access_control = None

        with pytest.raises(ForbiddenException, match="without case access controls"):
            task_service.search_tasks(user)

        mock_datastore.return_value.case.stream_search.assert_not_called()
