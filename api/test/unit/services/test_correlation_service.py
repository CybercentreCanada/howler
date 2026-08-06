"""Unit tests for the correlation service."""

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from howler.common.exceptions import HowlerRuntimeError
from howler.config import CLASSIFICATION
from howler.odm.models.case import CaseItem, CaseRule
from howler.services import correlation_service

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_rule(
    enabled: bool = True,
    timeframe: int | None = None,
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
        """Rules whose created_at + timeframe is in the past are excluded."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        rule = _make_rule(timeframe=1)
        rule.created_at = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()

        case = _make_case_obj("case-1", [rule])
        mock_ds.case.stream_search.return_value = iter([case])

        result = correlation_service.get_active_rules()

        assert len(result) == 0

    @patch("howler.services.correlation_service.datastore")
    def test_includes_valid_rules(self, mock_ds_fn):
        """Enabled rules with an unexpired (or no) timeframe are returned."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        rules = [
            _make_rule(timeframe=30, query="event.kind:alert"),
            _make_rule(timeframe=None, query="*:*"),
        ]
        rules[0].created_at = datetime.now(timezone.utc).isoformat()

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
        """Rules with unparseable timeframe are skipped and do not crash."""
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

    @patch("howler.services.correlation_service.datastore")
    def test_excludes_rules_with_non_positive_timeframe(self, mock_ds_fn):
        """Rules with timeframe <= 0 are treated as invalid and skipped."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        rule_zero = MagicMock()
        rule_zero.enabled = True
        rule_zero.timeframe = 0
        rule_zero.rule_id = "rule-zero"
        rule_zero.expire_after_resolved = False
        rule_zero.created_at = datetime.now(timezone.utc).isoformat()

        rule_negative = MagicMock()
        rule_negative.enabled = True
        rule_negative.timeframe = -5
        rule_negative.rule_id = "rule-negative"
        rule_negative.expire_after_resolved = False
        rule_negative.created_at = datetime.now(timezone.utc).isoformat()

        case = _make_case_obj("case-1", [rule_zero, rule_negative])
        mock_ds.case.stream_search.return_value = iter([case])

        result = correlation_service.get_active_rules()

        assert len(result) == 0

    @patch("howler.services.correlation_service.datastore")
    def test_handles_naive_created_at_as_utc(self, mock_ds_fn):
        """Naive created_at timestamps are normalized to UTC and processed."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        rule = _make_rule(timeframe=1)
        rule.created_at = (datetime.now() - timedelta(hours=1)).isoformat()

        case = _make_case_obj("case-1", [rule])
        mock_ds.case.stream_search.return_value = iter([case])

        result = correlation_service.get_active_rules()

        assert len(result) == 1
        assert result[0][0] == "case-1"


class TestCorrelationWorker:
    """Tests for correlation worker batching behavior."""

    @patch("howler.services.correlation_service.process_batch")
    @patch("howler.services.correlation_service._get_ingestion_queue")
    @patch.object(correlation_service, "BATCH_TIMEOUT", 1)
    @patch.object(correlation_service, "BATCH_SIZE", 3)
    def test_processes_full_batch(self, mock_get_queue, mock_process_batch):
        """A full queue batch is delivered to process_batch without waiting for a timeout."""
        queue = MagicMock()
        queue.pop.side_effect = ["hit-1", "hit-2", "hit-3", KeyboardInterrupt]
        mock_get_queue.return_value = queue

        with pytest.raises(KeyboardInterrupt):
            correlation_service.run_worker()

        mock_process_batch.assert_called_once_with(["hit-1", "hit-2", "hit-3"])

    @patch("howler.services.correlation_service.process_batch")
    @patch("howler.services.correlation_service._get_ingestion_queue")
    @patch.object(correlation_service, "BATCH_TIMEOUT", 1)
    @patch.object(correlation_service, "BATCH_SIZE", 3)
    def test_flushes_partial_batch_after_timeout(self, mock_get_queue, mock_process_batch):
        """A timeout flushes queued records when the batch is not yet full."""
        queue = MagicMock()
        queue.pop.side_effect = ["hit-1", None, KeyboardInterrupt]
        mock_get_queue.return_value = queue

        with pytest.raises(KeyboardInterrupt):
            correlation_service.run_worker()

        mock_process_batch.assert_called_once_with(["hit-1"])


class TestEnqueueForCorrelation:
    """Tests for enqueue_for_correlation queue producer behavior."""

    @patch("howler.services.correlation_service._get_ingestion_queue")
    def test_enqueues_all_ids(self, mock_get_queue):
        """All provided IDs are pushed to the shared ingestion queue."""
        queue = MagicMock()
        mock_get_queue.return_value = queue

        correlation_service.enqueue_for_correlation(["hit-1", "hit-2"])

        queue.push.assert_called_once_with("hit-1", "hit-2")

    @patch("howler.services.correlation_service.case_service")
    @patch("howler.services.correlation_service.datastore")
    def test_handles_naive_last_resolved_as_utc(self, mock_ds_fn, mock_case_service):
        """Naive resolution timestamps are normalized to UTC and processed."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        rule = _make_rule(timeframe=1)
        rule.expire_after_resolved = True

        case = _make_case_obj("case-1", [rule])
        mock_ds.case.stream_search.return_value = iter([case])
        mock_case_service.get_last_resolved_time.return_value = datetime.now() - timedelta(hours=1)

        result = correlation_service.get_active_rules()

        assert len(result) == 1
        assert result[0][0] == "case-1"


# ---------------------------------------------------------------------------
# process_batch
# ---------------------------------------------------------------------------


def _make_case(case_id: str, items: list | None = None) -> MagicMock:
    case = MagicMock()
    case.case_id = case_id
    case.items = items if items is not None else []
    return case


def _make_backing_obj(classification: str = CLASSIFICATION.UNRESTRICTED) -> MagicMock:
    """A stand-in for a Hit/Event with just enough shape for backreference/metadata sync."""
    obj = MagicMock()
    obj.classification = classification
    obj.related = None
    obj.howler.related = []
    obj.howler.outline = None
    return obj


def _setup_ds(
    mock_ds_fn: MagicMock,
    cases: dict[str, MagicMock],
    hits: dict[str, MagicMock] | None = None,
    events: dict[str, MagicMock] | None = None,
) -> MagicMock:
    """Wire up a mocked datastore whose case/hit/event `.get()` calls resolve from dicts."""
    mock_ds = MagicMock()
    mock_ds_fn.return_value = mock_ds

    def event_get(*args, **kwargs):
        key = args[0] if args else kwargs.get("key")
        return (events or {}).get(key)

    mock_ds.case.get.side_effect = lambda cid: cases.get(cid)
    mock_ds.hit.get.side_effect = lambda hid: (hits or {}).get(hid)
    mock_ds.event.get.side_effect = event_get
    mock_ds.__getitem__.side_effect = lambda item_type: getattr(mock_ds, item_type)

    # Mirror ElasticBulkPlan.empty: starts empty, flips once an operation is queued.
    bulk_plan = mock_ds.case.get_bulk_plan.return_value
    bulk_plan.empty = True

    def _mark_not_empty(*args, **kwargs):
        bulk_plan.empty = False

    bulk_plan.add_update_operation.side_effect = _mark_not_empty
    bulk_plan.add_index_operation.side_effect = _mark_not_empty

    return mock_ds


class TestProcessBatch:
    """Tests for correlation_service.process_batch."""

    @patch("howler.services.correlation_service.comms_service")
    @patch("howler.services.correlation_service.search_service")
    @patch("howler.services.correlation_service.get_active_rules")
    @patch("howler.services.correlation_service.datastore")
    def test_adds_matching_hits(self, mock_ds_fn, mock_get_rules, mock_search_svc, mock_comms):
        """Matching hits are accumulated onto the case and flushed in a single bulk call."""
        case = _make_case("case-1")
        hit = _make_backing_obj()
        mock_ds = _setup_ds(mock_ds_fn, {"case-1": case}, hits={"hit-1": hit})

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
        assert len(case.items) == 1
        assert case.items[0].type == "hit"
        assert case.items[0].value == "hit-1"
        assert case.items[0].name == "alerts"

        assert "case-1" in hit.howler.related
        mock_ds.hit.get_bulk_plan.return_value.add_update_operation.assert_called_once_with(
            "hit-1", hit, fields=["howler.related"]
        )
        mock_ds.hit.bulk.assert_called_once_with(mock_ds.hit.get_bulk_plan.return_value)

        mock_ds.case.get_bulk_plan.return_value.add_update_operation.assert_called_once_with(
            "case-1", case, fields=["items", "targets", "threats", "indicators"]
        )
        mock_ds.case.bulk.assert_called_once()
        mock_comms.emit.assert_called_once_with("cases", {"case": case.as_primitives()})

    @patch("howler.services.correlation_service.comms_service")
    @patch("howler.services.correlation_service.search_service")
    @patch("howler.services.correlation_service.get_active_rules")
    @patch("howler.services.correlation_service.datastore")
    def test_skips_duplicates(self, mock_ds_fn, mock_get_rules, mock_search_svc, mock_comms):
        """Records that would conflict with an existing item are silently skipped."""
        existing = CaseItem({"type": "hit", "value": "hit-0", "name": "related"})
        case = _make_case("case-1", items=[existing])
        mock_ds = _setup_ds(mock_ds_fn, {"case-1": case})

        rule = _make_rule(query="*:*", destination="related")
        mock_get_rules.return_value = [("case-1", rule)]

        mock_search_svc.search.return_value = {
            "items": [{"howler": {"id": "hit-1"}, "__index": "hit"}],
            "total": 1,
            "offset": 0,
            "rows": 1,
        }

        added = correlation_service.process_batch(["hit-1"])

        assert added == 0
        assert case.items == [existing]
        mock_ds.case.bulk.assert_not_called()

    @patch("howler.services.correlation_service.comms_service")
    @patch("howler.services.correlation_service.search_service")
    @patch("howler.services.correlation_service.get_active_rules")
    @patch("howler.services.correlation_service.datastore")
    def test_renders_destination_template(self, mock_ds_fn, mock_get_rules, mock_search_svc, mock_comms):
        """Mustache templates in destination are rendered with record data."""
        case = _make_case("case-1")
        hit = _make_backing_obj()
        _setup_ds(mock_ds_fn, {"case-1": case}, hits={"hit-1": hit})

        rule = _make_rule(query="*:*", destination="alerts/{{howler.analytic}}")
        mock_get_rules.return_value = [("case-1", rule)]

        mock_search_svc.search.return_value = {
            "items": [{"howler": {"id": "hit-1", "analytic": "My Detection"}, "__index": "hit"}],
            "total": 1,
            "offset": 0,
            "rows": 1,
        }

        correlation_service.process_batch(["hit-1"])

        hit_items = [i for i in case.items if i.type == "hit"]
        assert len(hit_items) == 1
        assert hit_items[0].name == "My Detection"

        folder_items = [i for i in case.items if i.type == "folder"]
        assert len(folder_items) == 1
        assert folder_items[0].name == "alerts"

    @patch("howler.services.correlation_service.comms_service")
    @patch("howler.services.correlation_service.search_service")
    @patch("howler.services.correlation_service.get_active_rules")
    @patch("howler.services.correlation_service.datastore")
    def test_deeply_nested_destination_persists_all_new_folders(
        self, mock_ds_fn, mock_get_rules, mock_search_svc, mock_comms
    ):
        """Every folder created along a deep destination path is included in the bulk-persisted case."""
        case = _make_case("case-1")
        hit = _make_backing_obj()
        mock_ds = _setup_ds(mock_ds_fn, {"case-1": case}, hits={"hit-1": hit})

        parts = ["a", "b", "c", "d", "e", "f", "g", "h"]
        rule = _make_rule(query="*:*", destination="/".join(parts) + "/{{howler.id}}")
        mock_get_rules.return_value = [("case-1", rule)]

        mock_search_svc.search.return_value = {
            "items": [{"howler": {"id": "hit-1"}, "__index": "hit"}],
            "total": 1,
            "offset": 0,
            "rows": 1,
        }

        added = correlation_service.process_batch(["hit-1"])

        assert added == 1

        # The exact case object mutated in memory is what gets handed to the bulk plan, so its
        # folders are part of the single persisted document rather than requiring separate saves.
        mock_ds.case.get_bulk_plan.return_value.add_update_operation.assert_called_once_with(
            "case-1", case, fields=["items", "targets", "threats", "indicators"]
        )
        mock_ds.case.bulk.assert_called_once()

        folders = [i for i in case.items if i.type == "folder"]
        assert len(folders) == len(parts)

        names_leaf_to_root = []
        current = next(i for i in case.items if i.type == "hit")
        while current is not None:
            names_leaf_to_root.append(current.name)
            current = next((i for i in case.items if i.id == current.parent), None)

        assert names_leaf_to_root[1:] == list(reversed(parts))

    def test_returns_zero_when_no_records(self):
        """An empty record_ids list returns 0 without querying."""
        added = correlation_service.process_batch([])
        assert added == 0

    @patch("howler.services.correlation_service.get_active_rules")
    @patch("howler.services.correlation_service.datastore")
    def test_returns_zero_when_no_rules(self, mock_ds_fn, mock_get_rules):
        """Returns 0 when there are no active rules."""
        mock_ds_fn.return_value = MagicMock()
        mock_get_rules.return_value = []

        added = correlation_service.process_batch(["hit-1"])

        assert added == 0

    @patch("howler.services.correlation_service.comms_service")
    @patch("howler.services.correlation_service.search_service")
    @patch("howler.services.correlation_service.get_active_rules")
    @patch("howler.services.correlation_service.datastore")
    def test_handles_not_found_gracefully(self, mock_ds_fn, mock_get_rules, mock_search_svc, mock_comms):
        """A missing backing hit/event is logged and does not raise, nor does it flush a bulk update."""
        case = _make_case("case-1")
        mock_ds = _setup_ds(mock_ds_fn, {"case-1": case})

        rule = _make_rule(query="*:*", destination="related")
        mock_get_rules.return_value = [("case-1", rule)]

        mock_search_svc.search.return_value = {
            "items": [{"howler": {"id": "hit-1"}, "__index": "hit"}],
            "total": 1,
            "offset": 0,
            "rows": 1,
        }

        added = correlation_service.process_batch(["hit-1"])

        assert added == 0
        assert case.items == []
        mock_ds.case.bulk.assert_not_called()

    @patch("howler.services.correlation_service.comms_service")
    @patch("howler.services.correlation_service.search_service")
    @patch("howler.services.correlation_service.get_active_rules")
    @patch("howler.services.correlation_service.datastore")
    def test_continues_after_es_query_failure(self, mock_ds_fn, mock_get_rules, mock_search_svc, mock_comms):
        """An ES query failure for one rule doesn't block subsequent rules."""
        case1 = _make_case("case-1")
        case2 = _make_case("case-2")
        hit = _make_backing_obj()
        _setup_ds(mock_ds_fn, {"case-1": case1, "case-2": case2}, hits={"hit-1": hit})

        rule_bad = _make_rule(query="invalid(", destination="a")
        rule_good = _make_rule(query="*:*", destination="b")
        mock_get_rules.return_value = [("case-1", rule_bad), ("case-2", rule_good)]

        mock_search_svc.search.side_effect = [
            Exception("parse error"),
            {"items": [{"howler": {"id": "hit-1"}, "__index": "hit"}], "total": 1, "offset": 0, "rows": 1},
        ]

        added = correlation_service.process_batch(["hit-1"])

        assert added == 1
        assert case1.items == []
        assert len(case2.items) == 1
        assert case2.items[0].value == "hit-1"

    @patch("howler.services.correlation_service.comms_service")
    @patch("howler.services.correlation_service.search_service")
    @patch("howler.services.correlation_service.get_active_rules")
    @patch("howler.services.correlation_service.datastore")
    def test_multiple_records_multiple_rules(self, mock_ds_fn, mock_get_rules, mock_search_svc, mock_comms):
        """Multiple records can match across multiple rules and cases in a single bulk flush."""
        case1 = _make_case("case-1")
        case2 = _make_case("case-2")
        hits = {"hit-1": _make_backing_obj(), "hit-2": _make_backing_obj(), "hit-3": _make_backing_obj()}
        mock_ds = _setup_ds(mock_ds_fn, {"case-1": case1, "case-2": case2}, hits=hits)

        rule_a = _make_rule(query="event.kind:alert", destination="alerts/{{howler.id}}")
        rule_b = _make_rule(query="event.kind:event", destination="events/{{howler.id}}")
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
        assert len([i for i in case1.items if i.type == "hit"]) == 2
        assert len([i for i in case2.items if i.type == "hit"]) == 1
        assert mock_ds.case.get_bulk_plan.return_value.add_update_operation.call_count == 2
        mock_ds.case.bulk.assert_called_once()

    @patch("howler.services.correlation_service.comms_service")
    @patch("howler.services.correlation_service.search_service")
    @patch("howler.services.correlation_service.get_active_rules")
    @patch("howler.services.correlation_service.datastore")
    def test_adds_matching_events(self, mock_ds_fn, mock_get_rules, mock_search_svc, mock_comms):
        """Matching events are added to the case with item type 'event'."""
        case = _make_case("case-1")
        event = _make_backing_obj()
        _setup_ds(mock_ds_fn, {"case-1": case}, events={"obs-1": event})

        rule = _make_rule(query="event.kind:enrichment", destination="events", indexes=["event"])
        mock_get_rules.return_value = [("case-1", rule)]

        mock_search_svc.search.return_value = {
            "items": [{"howler": {"id": "obs-1"}, "__index": "event"}],
            "total": 1,
            "offset": 0,
            "rows": 1,
        }

        added = correlation_service.process_batch(["obs-1"])

        assert added == 1
        event_items = [i for i in case.items if i.type == "event"]
        assert len(event_items) == 1
        assert event_items[0].value == "obs-1"
        assert "case-1" in event.howler.related
        mock_ds = mock_ds_fn.return_value
        mock_ds.event.get_bulk_plan.return_value.add_update_operation.assert_called_once_with(
            "obs-1", event, fields=["howler.related"]
        )
        mock_ds.event.bulk.assert_called_once_with(mock_ds.event.get_bulk_plan.return_value)

    @patch("howler.services.correlation_service.comms_service")
    @patch("howler.services.correlation_service.search_service")
    @patch("howler.services.correlation_service.get_active_rules")
    @patch("howler.services.correlation_service.datastore")
    def test_searches_both_indexes(self, mock_ds_fn, mock_get_rules, mock_search_svc, mock_comms):
        """A rule targeting both hit and event indexes searches across both."""
        case = _make_case("case-1")
        _setup_ds(
            mock_ds_fn,
            {"case-1": case},
            hits={"hit-1": _make_backing_obj()},
            events={"obs-1": _make_backing_obj()},
        )

        rule = _make_rule(query="*:*", destination="related/{{howler.id}}", indexes=["hit", "event"])
        mock_get_rules.return_value = [("case-1", rule)]

        mock_search_svc.search.return_value = {
            "items": [
                {"howler": {"id": "hit-1"}, "__index": "hit"},
                {"howler": {"id": "obs-1"}, "__index": "event"},
            ],
            "total": 2,
            "offset": 0,
            "rows": 2,
        }

        added = correlation_service.process_batch(["hit-1", "obs-1"])

        assert added == 2
        mock_search_svc.search.assert_called_once()
        call_kwargs = mock_search_svc.search.call_args
        assert set(call_kwargs.kwargs["indexes"]) == {"hit", "event"}

        types = {i.type for i in case.items if i.type != "folder"}
        assert types == {"hit", "event"}

    @patch("howler.services.correlation_service.comms_service")
    @patch("howler.services.correlation_service.search_service")
    @patch("howler.services.correlation_service.get_active_rules")
    @patch("howler.services.correlation_service.datastore")
    def test_defaults_to_hit_index_when_indexes_empty(self, mock_ds_fn, mock_get_rules, mock_search_svc, mock_comms):
        """When indexes is empty, the rule defaults to searching the hit index."""
        case = _make_case("case-1")
        _setup_ds(mock_ds_fn, {"case-1": case}, hits={"hit-1": _make_backing_obj()})

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

    @patch("howler.services.correlation_service.comms_service")
    @patch("howler.services.correlation_service.search_service")
    @patch("howler.services.correlation_service.get_active_rules")
    @patch("howler.services.correlation_service.datastore")
    def test_item_type_derived_from_index(self, mock_ds_fn, mock_get_rules, mock_search_svc, mock_comms):
        """The item type added to the case matches the __index of the record."""
        case = _make_case("case-1")
        _setup_ds(
            mock_ds_fn,
            {"case-1": case},
            hits={"hit-1": _make_backing_obj()},
            events={"obs-1": _make_backing_obj()},
        )

        rule = _make_rule(query="*:*", destination="items/{{howler.id}}", indexes=["hit", "event"])
        mock_get_rules.return_value = [("case-1", rule)]

        mock_search_svc.search.return_value = {
            "items": [
                {"howler": {"id": "hit-1"}, "__index": "hit"},
                {"howler": {"id": "obs-1"}, "__index": "event"},
            ],
            "total": 2,
            "offset": 0,
            "rows": 2,
        }

        correlation_service.process_batch(["hit-1", "obs-1"])

        hit_item = next(i for i in case.items if i.value == "hit-1")
        obs_item = next(i for i in case.items if i.value == "obs-1")
        assert hit_item.type == "hit"
        assert obs_item.type == "event"

    @patch("howler.services.correlation_service.get_active_rules")
    @patch("howler.services.correlation_service.datastore")
    def test_skips_rule_when_case_not_found(self, mock_ds_fn, mock_get_rules):
        """When ds.case.get returns None for a case, the rule is skipped and no items are added."""
        mock_ds = _setup_ds(mock_ds_fn, {})

        rule = _make_rule(query="*:*", destination="related")
        mock_get_rules.return_value = [("case-missing", rule)]

        added = correlation_service.process_batch(["hit-1"])

        assert added == 0
        mock_ds.case.bulk.assert_not_called()


class TestCorrelationUnreachableBranches:
    """Cover correlation states that require controlled fault injection."""

    def test_missing_item_name_falls_back_to_record_id(self):
        """An item with no rendered name uses its record ID."""
        case = MagicMock(items=[])
        backing_obj = _make_backing_obj()
        item = MagicMock(type="hit", value="hit-1")
        item.name = None
        rule = _make_rule(destination="related")

        with (
            patch.object(correlation_service, "CaseItem", return_value=item),
            patch.object(correlation_service, "_resolve_backing_object", return_value=backing_obj),
            patch.object(correlation_service.case_service, "get_parent_from_path", return_value=None),
            patch.object(correlation_service.case_service, "check_conflicts", return_value=False),
            patch.object(correlation_service.case_service, "add_backreference", return_value=True),
        ):
            added = correlation_service._add_record_to_case(case, "case-1", {"howler": {"id": "hit-1"}}, rule, {})

        assert added is not None
        assert added[0] == "hit"
        assert added[1] == "hit-1"
        assert item.name == "hit-1"
        assert case.items == [item]

    @patch("howler.services.correlation_service.search_service")
    @patch("howler.services.correlation_service.get_active_rules")
    @patch("howler.services.correlation_service.datastore")
    def test_bulk_failure_raises_runtime_error(self, mock_ds_fn, mock_get_rules, mock_search_svc):
        """A failed bulk case update is surfaced to the caller."""
        case = _make_case("case-1")
        datastore = _setup_ds(mock_ds_fn, {"case-1": case}, hits={"hit-1": _make_backing_obj()})
        datastore.case.bulk.return_value = False
        datastore.case.get_bulk_plan.return_value.empty = False
        datastore.case.get_bulk_plan.return_value.operations = ["update"]

        mock_get_rules.return_value = [("case-1", _make_rule(destination="related"))]
        mock_search_svc.search.return_value = {
            "items": [{"howler": {"id": "hit-1"}, "__index": "hit"}],
            "total": 1,
            "offset": 0,
            "rows": 1,
        }

        with pytest.raises(HowlerRuntimeError, match="Bulk case update reported errors"):
            correlation_service.process_batch(["hit-1"])

        datastore.case.bulk.assert_called_once()
