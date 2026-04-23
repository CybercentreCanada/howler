"""Unit tests for the correlation service."""

from datetime import datetime, timedelta, timezone
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
) -> CaseRule:
    return CaseRule(
        {
            "query": query,
            "destination": destination,
            "author": "test_user",
            "enabled": enabled,
            "timeframe": timeframe,
        }
    )


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

    @patch("howler.services.correlation_service.case_service")
    @patch("howler.services.correlation_service.get_active_rules")
    @patch("howler.services.correlation_service.datastore")
    def test_adds_matching_hits(self, mock_ds_fn, mock_get_rules, mock_case_svc):
        """Matching hits are added to the case via append_case_item."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        rule = _make_rule(query="event.kind:alert", destination="alerts")
        mock_get_rules.return_value = [("case-1", rule)]

        mock_ds.hit.search.return_value = {
            "items": [{"howler": {"id": "hit-1"}}],
        }

        added = correlation_service.process_batch(["hit-1"])

        assert added == 1
        mock_case_svc.append_case_item.assert_called_once_with(
            "case-1",
            item_type="hit",
            item_value="hit-1",
            item_path="alerts",
        )

    @patch("howler.services.correlation_service.case_service")
    @patch("howler.services.correlation_service.get_active_rules")
    @patch("howler.services.correlation_service.datastore")
    def test_skips_duplicates(self, mock_ds_fn, mock_get_rules, mock_case_svc):
        """Duplicate hits (InvalidDataException) are silently skipped."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        rule = _make_rule(query="*:*", destination="related")
        mock_get_rules.return_value = [("case-1", rule)]

        mock_ds.hit.search.return_value = {
            "items": [{"howler": {"id": "hit-1"}}],
        }
        mock_case_svc.append_case_item.side_effect = InvalidDataException("already exists")

        added = correlation_service.process_batch(["hit-1"])

        assert added == 0

    @patch("howler.services.correlation_service.case_service")
    @patch("howler.services.correlation_service.get_active_rules")
    @patch("howler.services.correlation_service.datastore")
    def test_renders_destination_template(self, mock_ds_fn, mock_get_rules, mock_case_svc):
        """Mustache templates in destination are rendered with hit data."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        rule = _make_rule(query="*:*", destination="alerts/{{howler.analytic}}")
        mock_get_rules.return_value = [("case-1", rule)]

        mock_ds.hit.search.return_value = {
            "items": [{"howler": {"id": "hit-1", "analytic": "My Detection"}}],
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
    def test_returns_zero_when_no_hits(self, mock_ds_fn, mock_get_rules, mock_case_svc):
        """An empty hit_ids list returns 0 without querying."""
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

    @patch("howler.services.correlation_service.case_service")
    @patch("howler.services.correlation_service.get_active_rules")
    @patch("howler.services.correlation_service.datastore")
    def test_handles_not_found_gracefully(self, mock_ds_fn, mock_get_rules, mock_case_svc):
        """NotFoundException from append_case_item is logged, not raised."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        rule = _make_rule(query="*:*", destination="related")
        mock_get_rules.return_value = [("case-1", rule)]

        mock_ds.hit.search.return_value = {
            "items": [{"howler": {"id": "hit-1"}}],
        }
        mock_case_svc.append_case_item.side_effect = NotFoundException("gone")

        added = correlation_service.process_batch(["hit-1"])

        assert added == 0

    @patch("howler.services.correlation_service.case_service")
    @patch("howler.services.correlation_service.get_active_rules")
    @patch("howler.services.correlation_service.datastore")
    def test_continues_after_es_query_failure(self, mock_ds_fn, mock_get_rules, mock_case_svc):
        """An ES query failure for one rule doesn't block subsequent rules."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        rule_bad = _make_rule(query="invalid(", destination="a")
        rule_good = _make_rule(query="*:*", destination="b")
        mock_get_rules.return_value = [("case-1", rule_bad), ("case-2", rule_good)]

        mock_ds.hit.search.side_effect = [
            Exception("parse error"),
            {"items": [{"howler": {"id": "hit-1"}}]},
        ]

        added = correlation_service.process_batch(["hit-1"])

        assert added == 1
        mock_case_svc.append_case_item.assert_called_once_with(
            "case-2",
            item_type="hit",
            item_value="hit-1",
            item_path="b",
        )

    @patch("howler.services.correlation_service.case_service")
    @patch("howler.services.correlation_service.get_active_rules")
    @patch("howler.services.correlation_service.datastore")
    def test_multiple_hits_multiple_rules(self, mock_ds_fn, mock_get_rules, mock_case_svc):
        """Multiple hits can match across multiple rules."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        rule_a = _make_rule(query="event.kind:alert", destination="alerts")
        rule_b = _make_rule(query="event.kind:event", destination="events")
        mock_get_rules.return_value = [("case-1", rule_a), ("case-2", rule_b)]

        mock_ds.hit.search.side_effect = [
            {"items": [{"howler": {"id": "hit-1"}}, {"howler": {"id": "hit-2"}}]},
            {"items": [{"howler": {"id": "hit-3"}}]},
        ]

        added = correlation_service.process_batch(["hit-1", "hit-2", "hit-3"])

        assert added == 3
