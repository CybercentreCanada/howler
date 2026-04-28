"""Unit tests for the correlation service."""

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock, patch

from howler.common.exceptions import InvalidDataException, NotFoundException
from howler.odm.models.case import CaseRule
from howler.services import correlation_service

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_rule(
    enabled: bool = True,
    timeframe: str | None = None,
    query: str = "*:*",
    destination: str = "related",
    indexes: list[str] | None = None,
) -> CaseRule:
    data: dict[str, Any] = {
        "query": query,
        "destination": destination,
        "author": "test_user",
        "enabled": enabled,
        "timeframe": timeframe,
    }

    if indexes is not None:
        data["indexes"] = indexes

    return CaseRule(data)


def _make_case_obj(case_id: str, rules: list[CaseRule]) -> MagicMock:
    case = MagicMock()
    case.case_id = case_id
    case.rules = rules
    return case


# ---------------------------------------------------------------------------
# get_active_rules
# ---------------------------------------------------------------------------


class TestGetActiveRules:
    """Tests for correlation_service.get_active_rules."""

    @patch("howler.services.correlation_service.datastore")
    def test_excludes_disabled_rules(self, mock_ds_fn):
        """Disabled rules are not returned."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        case = _make_case_obj("case-1", [_make_rule(enabled=False)])
        mock_ds.case.stream_search.return_value = iter([case])

        result = correlation_service.get_active_rules()

        assert len(result) == 0

    @patch("howler.services.correlation_service.datastore")
    def test_excludes_expired_rules(self, mock_ds_fn):
        """Rules with a timeframe in the past are excluded."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        case = _make_case_obj("case-1", [_make_rule(timeframe=past)])
        mock_ds.case.stream_search.return_value = iter([case])

        result = correlation_service.get_active_rules()

        assert len(result) == 0

    @patch("howler.services.correlation_service.datastore")
    def test_includes_valid_rules(self, mock_ds_fn):
        """Enabled rules with a future (or no) timeframe are returned."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        rules = [
            _make_rule(timeframe=future, query="event.kind:alert"),
            _make_rule(timeframe=None, query="*:*"),
        ]
        case = _make_case_obj("case-1", rules)
        mock_ds.case.stream_search.return_value = iter([case])

        result = correlation_service.get_active_rules()

        assert len(result) == 2
        assert all(cid == "case-1" for cid, _ in result)

    @patch("howler.services.correlation_service.datastore")
    def test_returns_rules_from_multiple_cases(self, mock_ds_fn):
        """Rules from different cases are all returned."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        case1 = _make_case_obj("case-1", [_make_rule(query="a:b")])
        case2 = _make_case_obj("case-2", [_make_rule(query="c:d")])
        mock_ds.case.stream_search.return_value = iter([case1, case2])

        result = correlation_service.get_active_rules()

        assert len(result) == 2
        case_ids = {cid for cid, _ in result}
        assert case_ids == {"case-1", "case-2"}

    @patch("howler.services.correlation_service.datastore")
    def test_excludes_rules_with_invalid_timeframe(self, mock_ds_fn):
        """Rules with an unparseable timeframe are skipped with a warning."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        # Use a MagicMock rule since CaseRule validates the timeframe at
        # construction and would reject an invalid string.
        bad_rule = MagicMock()
        bad_rule.enabled = True
        bad_rule.timeframe = "not-a-date"
        bad_rule.rule_id = "rule-bad"

        case = _make_case_obj("case-1", [bad_rule])
        mock_ds.case.stream_search.return_value = iter([case])

        result = correlation_service.get_active_rules()

        assert len(result) == 0


# ---------------------------------------------------------------------------
# process_batch
# ---------------------------------------------------------------------------


class TestProcessBatch:
    """Tests for correlation_service.process_batch."""

    @patch("howler.services.correlation_service.search_service")
    @patch("howler.services.correlation_service.case_service")
    @patch("howler.services.correlation_service.get_active_rules")
    @patch("howler.services.correlation_service.datastore")
    def test_adds_matching_hits(self, mock_ds_fn, mock_get_rules, mock_case_svc, mock_search_svc):
        """Matching hits are added to the case via append_case_item."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        rule = _make_rule(query="event.kind:alert", destination="alerts")
        mock_get_rules.return_value = [("case-1", rule)]

        mock_search_svc.search.return_value = {
            "items": [{"howler": {"id": "hit-1"}, "__index": "hit"}],
            "total": 1,
            "offset": 0,
            "rows": 1,
        }

        added = correlation_service.process_batch(["hit-1"])

        assert added == 1
        mock_case_svc.append_case_item.assert_called_once_with(
            "case-1",
            item_type="hit",
            item_value="hit-1",
            item_path="alerts",
        )

    @patch("howler.services.correlation_service.search_service")
    @patch("howler.services.correlation_service.case_service")
    @patch("howler.services.correlation_service.get_active_rules")
    @patch("howler.services.correlation_service.datastore")
    def test_skips_duplicates(self, mock_ds_fn, mock_get_rules, mock_case_svc, mock_search_svc):
        """Duplicate records (InvalidDataException) are silently skipped."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        rule = _make_rule(query="*:*", destination="related")
        mock_get_rules.return_value = [("case-1", rule)]

        mock_search_svc.search.return_value = {
            "items": [{"howler": {"id": "hit-1"}, "__index": "hit"}],
            "total": 1,
            "offset": 0,
            "rows": 1,
        }
        mock_case_svc.append_case_item.side_effect = InvalidDataException("already exists")

        added = correlation_service.process_batch(["hit-1"])

        assert added == 0

    @patch("howler.services.correlation_service.search_service")
    @patch("howler.services.correlation_service.case_service")
    @patch("howler.services.correlation_service.get_active_rules")
    @patch("howler.services.correlation_service.datastore")
    def test_renders_destination_template(self, mock_ds_fn, mock_get_rules, mock_case_svc, mock_search_svc):
        """Mustache templates in destination are rendered with record data."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        rule = _make_rule(query="*:*", destination="alerts/{{howler.analytic}}")
        mock_get_rules.return_value = [("case-1", rule)]

        mock_search_svc.search.return_value = {
            "items": [{"howler": {"id": "hit-1", "analytic": "My Detection"}, "__index": "hit"}],
            "total": 1,
            "offset": 0,
            "rows": 1,
        }

        correlation_service.process_batch(["hit-1"])

        mock_case_svc.append_case_item.assert_called_once_with(
            "case-1",
            item_type="hit",
            item_value="hit-1",
            item_path="alerts/My Detection",
        )

    @patch("howler.services.correlation_service.case_service")
    @patch("howler.services.correlation_service.get_active_rules")
    @patch("howler.services.correlation_service.datastore")
    def test_returns_zero_when_no_records(self, mock_ds_fn, mock_get_rules, mock_case_svc):
        """An empty record_ids list returns 0 without querying."""
        added = correlation_service.process_batch([])
        assert added == 0
        mock_case_svc.append_case_item.assert_not_called()

    @patch("howler.services.correlation_service.case_service")
    @patch("howler.services.correlation_service.get_active_rules")
    @patch("howler.services.correlation_service.datastore")
    def test_returns_zero_when_no_rules(self, mock_ds_fn, mock_get_rules, mock_case_svc):
        """Returns 0 when there are no active rules."""
        mock_get_rules.return_value = []

        added = correlation_service.process_batch(["hit-1"])

        assert added == 0
        mock_case_svc.append_case_item.assert_not_called()

    @patch("howler.services.correlation_service.search_service")
    @patch("howler.services.correlation_service.case_service")
    @patch("howler.services.correlation_service.get_active_rules")
    @patch("howler.services.correlation_service.datastore")
    def test_handles_not_found_gracefully(self, mock_ds_fn, mock_get_rules, mock_case_svc, mock_search_svc):
        """NotFoundException from append_case_item is logged, not raised."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        rule = _make_rule(query="*:*", destination="related")
        mock_get_rules.return_value = [("case-1", rule)]

        mock_search_svc.search.return_value = {
            "items": [{"howler": {"id": "hit-1"}, "__index": "hit"}],
            "total": 1,
            "offset": 0,
            "rows": 1,
        }
        mock_case_svc.append_case_item.side_effect = NotFoundException("gone")

        added = correlation_service.process_batch(["hit-1"])

        assert added == 0

    @patch("howler.services.correlation_service.search_service")
    @patch("howler.services.correlation_service.case_service")
    @patch("howler.services.correlation_service.get_active_rules")
    @patch("howler.services.correlation_service.datastore")
    def test_continues_after_es_query_failure(self, mock_ds_fn, mock_get_rules, mock_case_svc, mock_search_svc):
        """An ES query failure for one rule doesn't block subsequent rules."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        rule_bad = _make_rule(query="invalid(", destination="a")
        rule_good = _make_rule(query="*:*", destination="b")
        mock_get_rules.return_value = [("case-1", rule_bad), ("case-2", rule_good)]

        mock_search_svc.search.side_effect = [
            Exception("parse error"),
            {"items": [{"howler": {"id": "hit-1"}, "__index": "hit"}], "total": 1, "offset": 0, "rows": 1},
        ]

        added = correlation_service.process_batch(["hit-1"])

        assert added == 1
        mock_case_svc.append_case_item.assert_called_once_with(
            "case-2",
            item_type="hit",
            item_value="hit-1",
            item_path="b",
        )

    @patch("howler.services.correlation_service.search_service")
    @patch("howler.services.correlation_service.case_service")
    @patch("howler.services.correlation_service.get_active_rules")
    @patch("howler.services.correlation_service.datastore")
    def test_multiple_records_multiple_rules(self, mock_ds_fn, mock_get_rules, mock_case_svc, mock_search_svc):
        """Multiple records can match across multiple rules."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        rule_a = _make_rule(query="event.kind:alert", destination="alerts")
        rule_b = _make_rule(query="event.kind:event", destination="events")
        mock_get_rules.return_value = [("case-1", rule_a), ("case-2", rule_b)]

        mock_search_svc.search.side_effect = [
            {
                "items": [
                    {"howler": {"id": "hit-1"}, "__index": "hit"},
                    {"howler": {"id": "hit-2"}, "__index": "hit"},
                ],
                "total": 2,
                "offset": 0,
                "rows": 2,
            },
            {
                "items": [{"howler": {"id": "hit-3"}, "__index": "hit"}],
                "total": 1,
                "offset": 0,
                "rows": 1,
            },
        ]

        added = correlation_service.process_batch(["hit-1", "hit-2", "hit-3"])

        assert added == 3

    @patch("howler.services.correlation_service.search_service")
    @patch("howler.services.correlation_service.case_service")
    @patch("howler.services.correlation_service.get_active_rules")
    @patch("howler.services.correlation_service.datastore")
    def test_adds_matching_observables(self, mock_ds_fn, mock_get_rules, mock_case_svc, mock_search_svc):
        """Matching observables are added to the case with item_type='observable'."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        rule = _make_rule(
            query="event.kind:enrichment",
            destination="observables",
            indexes=["observable"],
        )
        mock_get_rules.return_value = [("case-1", rule)]

        mock_search_svc.search.return_value = {
            "items": [{"howler": {"id": "obs-1"}, "__index": "observable"}],
            "total": 1,
            "offset": 0,
            "rows": 1,
        }

        added = correlation_service.process_batch(["obs-1"])

        assert added == 1
        mock_case_svc.append_case_item.assert_called_once_with(
            "case-1",
            item_type="observable",
            item_value="obs-1",
            item_path="observables",
        )

    @patch("howler.services.correlation_service.search_service")
    @patch("howler.services.correlation_service.case_service")
    @patch("howler.services.correlation_service.get_active_rules")
    @patch("howler.services.correlation_service.datastore")
    def test_searches_both_indexes(self, mock_ds_fn, mock_get_rules, mock_case_svc, mock_search_svc):
        """A rule targeting both hit and observable indexes searches across both."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        rule = _make_rule(
            query="*:*",
            destination="related",
            indexes=["hit", "observable"],
        )
        mock_get_rules.return_value = [("case-1", rule)]

        mock_search_svc.search.return_value = {
            "items": [
                {"howler": {"id": "hit-1"}, "__index": "hit"},
                {"howler": {"id": "obs-1"}, "__index": "observable"},
            ],
            "total": 2,
            "offset": 0,
            "rows": 2,
        }

        added = correlation_service.process_batch(["hit-1", "obs-1"])

        assert added == 2
        mock_search_svc.search.assert_called_once()
        call_kwargs = mock_search_svc.search.call_args
        assert set(call_kwargs.kwargs["indexes"]) == {"hit", "observable"}

        calls = mock_case_svc.append_case_item.call_args_list
        types = {c.kwargs["item_type"] for c in calls}
        assert types == {"hit", "observable"}

    @patch("howler.services.correlation_service.search_service")
    @patch("howler.services.correlation_service.case_service")
    @patch("howler.services.correlation_service.get_active_rules")
    @patch("howler.services.correlation_service.datastore")
    def test_defaults_to_hit_index_when_indexes_empty(self, mock_ds_fn, mock_get_rules, mock_case_svc, mock_search_svc):
        """When indexes is empty, the rule defaults to searching the hit index."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        rule = _make_rule(query="*:*", destination="related", indexes=[])
        mock_get_rules.return_value = [("case-1", rule)]

        mock_search_svc.search.return_value = {
            "items": [{"howler": {"id": "hit-1"}, "__index": "hit"}],
            "total": 1,
            "offset": 0,
            "rows": 1,
        }

        correlation_service.process_batch(["hit-1"])

        call_kwargs = mock_search_svc.search.call_args
        assert call_kwargs.kwargs["indexes"] == ["hit"]

    @patch("howler.services.correlation_service.search_service")
    @patch("howler.services.correlation_service.case_service")
    @patch("howler.services.correlation_service.get_active_rules")
    @patch("howler.services.correlation_service.datastore")
    def test_item_type_derived_from_index(self, mock_ds_fn, mock_get_rules, mock_case_svc, mock_search_svc):
        """The item_type passed to append_case_item matches the __index of the record."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        rule = _make_rule(query="*:*", destination="items", indexes=["hit", "observable"])
        mock_get_rules.return_value = [("case-1", rule)]

        mock_search_svc.search.return_value = {
            "items": [
                {"howler": {"id": "hit-1"}, "__index": "hit"},
                {"howler": {"id": "obs-1"}, "__index": "observable"},
            ],
            "total": 2,
            "offset": 0,
            "rows": 2,
        }

        correlation_service.process_batch(["hit-1", "obs-1"])

        calls = mock_case_svc.append_case_item.call_args_list
        assert len(calls) == 2

        hit_call = [c for c in calls if c.kwargs["item_value"] == "hit-1"][0]
        obs_call = [c for c in calls if c.kwargs["item_value"] == "obs-1"][0]
        assert hit_call.kwargs["item_type"] == "hit"
        assert obs_call.kwargs["item_type"] == "observable"
