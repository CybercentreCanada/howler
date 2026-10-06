"""Unit tests for the correlation service."""

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, call, patch
from uuid import UUID

import pytest

from howler.common.exceptions import HowlerRuntimeError, InvalidDataException
from howler.config import CLASSIFICATION
from howler.datastore.bulk import ElasticBulkPlan
from howler.datastore.collection import ESCollection
from howler.odm.models.case import Case, CaseItem, CaseRule
from howler.odm.models.event import Event
from howler.odm.models.hit import Hit
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
        queue.pop.side_effect = [
            {"id": "hit-1", "rule_id": None},
            {"id": "hit-2", "rule_id": None},
            {"id": "hit-3", "rule_id": None},
            KeyboardInterrupt,
        ]
        mock_get_queue.return_value = queue

        with pytest.raises(KeyboardInterrupt):
            correlation_service.run_worker()

        mock_process_batch.assert_called_once_with(["hit-1", "hit-2", "hit-3"], rule_id=None)

    @patch("howler.services.correlation_service.process_batch")
    @patch("howler.services.correlation_service._get_ingestion_queue")
    @patch.object(correlation_service, "BATCH_TIMEOUT", 1)
    @patch.object(correlation_service, "BATCH_SIZE", 3)
    def test_flushes_partial_batch_after_timeout(self, mock_get_queue, mock_process_batch):
        """A timeout flushes queued records when the batch is not yet full."""
        queue = MagicMock()
        queue.pop.side_effect = [{"id": "hit-1", "rule_id": None}, None, KeyboardInterrupt]
        mock_get_queue.return_value = queue

        with pytest.raises(KeyboardInterrupt):
            correlation_service.run_worker()

        mock_process_batch.assert_called_once_with(["hit-1"], rule_id=None)

    @patch("howler.services.correlation_service.process_batch")
    @patch("howler.services.correlation_service._get_ingestion_queue")
    @patch.object(correlation_service, "BATCH_TIMEOUT", 1)
    @patch.object(correlation_service, "BATCH_SIZE", 1)
    def test_processes_rule_scoped_job(self, mock_get_queue, mock_process_batch):
        queue = MagicMock()
        queue.pop.side_effect = [{"id": "hit-1", "rule_id": "rule-1"}, KeyboardInterrupt]
        mock_get_queue.return_value = queue

        with pytest.raises(KeyboardInterrupt):
            correlation_service.run_worker()

        mock_process_batch.assert_called_once_with(["hit-1"], rule_id="rule-1")

    @patch("howler.services.correlation_service.process_batch")
    @patch("howler.services.correlation_service._get_ingestion_queue")
    @patch.object(correlation_service, "BATCH_TIMEOUT", 1)
    @patch.object(correlation_service, "BATCH_SIZE", 2)
    def test_continues_processing_groups_after_a_group_failure(self, mock_get_queue, mock_process_batch):
        queue = MagicMock()
        queue.pop.side_effect = [
            {"id": "hit-1", "rule_id": "failing-rule"},
            {"id": "hit-2", "rule_id": "healthy-rule"},
            KeyboardInterrupt,
        ]
        mock_get_queue.return_value = queue
        mock_process_batch.side_effect = [RuntimeError("datastore unavailable"), 1]

        with pytest.raises(KeyboardInterrupt):
            correlation_service.run_worker()

        assert mock_process_batch.call_args_list == [
            call(["hit-1"], rule_id="failing-rule"),
            call(["hit-2"], rule_id="healthy-rule"),
        ]

    @patch("howler.services.correlation_service.process_batch")
    @patch("howler.services.correlation_service._get_ingestion_queue")
    @patch.object(correlation_service, "BATCH_TIMEOUT", 1)
    @patch.object(correlation_service, "BATCH_SIZE", 1)
    def test_coerces_legacy_string_job(self, mock_get_queue, mock_process_batch):
        queue = MagicMock()
        queue.pop.side_effect = ["legacy-hit", KeyboardInterrupt]
        mock_get_queue.return_value = queue

        with pytest.raises(KeyboardInterrupt):
            correlation_service.run_worker()

        mock_process_batch.assert_called_once_with(["legacy-hit"], rule_id=None)

    def test_rejects_malformed_correlation_jobs(self):
        assert correlation_service._validate_correlation_job("legacy-hit") == {"id": "legacy-hit", "rule_id": None}
        assert correlation_service._validate_correlation_job({"id": "hit-1", "rule_id": "rule-1"}) == {
            "id": "hit-1",
            "rule_id": "rule-1",
        }
        assert correlation_service._validate_correlation_job({"id": "", "rule_id": None}) is None
        assert correlation_service._validate_correlation_job({"id": "hit-1", "rule_id": 3}) is None


class TestEnqueueForCorrelation:
    """Tests for enqueue_for_correlation queue producer behavior."""

    @patch("howler.services.correlation_service._get_ingestion_queue")
    def test_enqueues_all_ids(self, mock_get_queue):
        """All provided IDs are pushed to the shared ingestion queue."""
        queue = MagicMock()
        mock_get_queue.return_value = queue

        correlation_service.enqueue_for_correlation(["hit-1", "hit-2"])

        queue.push.assert_called_once_with(
            {"id": "hit-1", "rule_id": None},
            {"id": "hit-2", "rule_id": None},
        )

    @patch("howler.services.correlation_service._get_ingestion_queue")
    def test_enqueues_rule_scoped_messages(self, mock_get_queue):
        queue = MagicMock()
        mock_get_queue.return_value = queue

        correlation_service.enqueue_for_correlation(["hit-1", "hit-2"], rule_id="rule-1")

        queue.push.assert_called_once_with(
            {"id": "hit-1", "rule_id": "rule-1"},
            {"id": "hit-2", "rule_id": "rule-1"},
        )

    @patch("howler.services.correlation_service._get_ingestion_queue")
    def test_enqueue_failure_raises_howler_runtime_error(self, mock_get_queue):
        queue = MagicMock()
        queue.push.side_effect = RuntimeError("redis unavailable")
        mock_get_queue.return_value = queue

        with pytest.raises(HowlerRuntimeError, match="Failed to enqueue record IDs for correlation"):
            correlation_service.enqueue_for_correlation(["hit-1"])


class TestRuleScopedCorrelation:
    @patch("howler.services.correlation_service.case_service.get_case")
    def test_get_backfill_rule_validates_case_and_normalizes_timestamp(self, mock_get_case):
        rule = _make_rule()
        rule.rule_id = "rule-1"
        case = MagicMock()
        case.rules = [rule]
        mock_get_case.return_value = case
        user = MagicMock()

        found_rule, since = correlation_service.get_backfill_rule("case-1", "rule-1", user, "2026-01-01T00:00:00")

        assert found_rule is rule
        assert since == datetime(2026, 1, 1, tzinfo=timezone.utc)
        mock_get_case.assert_called_once_with("case-1", as_odm=True, version=False, user=user)

    @patch("howler.services.correlation_service.case_service.get_case")
    def test_get_backfill_rule_rejects_disabled_rule(self, mock_get_case):
        rule = _make_rule(enabled=False)
        rule.rule_id = "rule-1"
        case = MagicMock()
        case.rules = [rule]
        mock_get_case.return_value = case

        with pytest.raises(InvalidDataException, match="Only enabled rules can be backfilled"):
            correlation_service.get_backfill_rule("case-1", "rule-1", MagicMock(), "2026-01-01T00:00:00Z")

    @patch("howler.services.correlation_service.datastore")
    def test_get_active_rules_filters_by_rule_id(self, mock_ds_fn):
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        case = _make_case_obj("case-1", [_make_rule(query="a:b"), _make_rule(query="c:d")])
        case.rules[0].rule_id = "rule-1"
        case.rules[1].rule_id = "rule-2"
        mock_ds.case.stream_search.return_value = iter([case])

        result = correlation_service.get_active_rules("rule-2")

        assert len(result) == 1
        assert result[0][1].rule_id == "rule-2"

    @patch("howler.services.correlation_service.datastore")
    def test_rule_scoped_backfill_includes_expired_rule(self, mock_ds_fn):
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        expired_rule = _make_rule(timeframe=1)
        expired_rule.rule_id = "expired-rule"
        expired_rule.created_at = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
        case = _make_case_obj("case-1", [expired_rule])
        mock_ds.case.stream_search.return_value = iter([case])

        result = correlation_service.get_active_rules("expired-rule")

        assert len(result) == 1
        assert result[0][1].rule_id == "expired-rule"

    @patch("howler.services.correlation_service.search_service.search")
    @patch("howler.services.correlation_service.get_backfill_rule")
    def test_count_backfill_matches_passes_since_and_user(self, mock_get_rule, mock_search):
        user = MagicMock()
        rule = _make_rule(query="event.kind:alert", indexes=["hit"])
        since = "2026-01-01T00:00:00Z"
        normalized_since = datetime(2026, 1, 1, tzinfo=timezone.utc)
        mock_get_rule.return_value = (rule, normalized_since)
        mock_search.return_value = {"total": 17}

        count = correlation_service.count_backfill_matches("case-1", "rule-1", since, user)

        assert count == 17
        mock_get_rule.assert_called_once_with("case-1", "rule-1", user, since)
        mock_search.assert_called_once_with(
            indexes=["hit"],
            query="event.kind:alert",
            filters=[f'timestamp:["{normalized_since.isoformat()}" TO *]'],
            rows=0,
            track_total_hits=True,
            user=user,
        )

    @patch("howler.services.correlation_service.enqueue_for_correlation")
    @patch("howler.services.correlation_service.search_service.search")
    @patch("howler.services.correlation_service.get_backfill_rule")
    def test_enqueue_backfill_resolves_rule_and_streams_pages(self, mock_get_rule, mock_search, mock_enqueue):
        user = MagicMock()
        rule = _make_rule(query="event.kind:alert", indexes=["hit"])
        rule.rule_id = "rule-1"
        since_value = "2026-01-01T00:00:00Z"
        since = datetime(2026, 1, 1, tzinfo=timezone.utc)
        mock_get_rule.return_value = (rule, since)
        mock_search.side_effect = [
            {"items": [{"howler": {"id": "hit-1"}}], "next_deep_paging_id": "scroll-1"},
            {"items": [{"howler": {"id": "hit-2"}}]},
        ]

        count = correlation_service.enqueue_backfill("case-1", "rule-1", since_value, user)

        assert count == 2
        mock_get_rule.assert_called_once_with("case-1", "rule-1", user, since_value)
        assert mock_enqueue.call_args_list[0].args == (["hit-1"],)
        assert mock_enqueue.call_args_list[0].kwargs == {"rule_id": "rule-1"}
        assert mock_enqueue.call_args_list[1].args == (["hit-2"],)
        assert mock_enqueue.call_args_list[1].kwargs == {"rule_id": "rule-1"}

    @patch("howler.services.correlation_service.enqueue_for_correlation")
    @patch("howler.services.correlation_service.search_service.search")
    @patch("howler.services.correlation_service.get_backfill_rule")
    def test_enqueue_backfill_propagates_queue_failure(self, mock_get_rule, mock_search, mock_enqueue):
        user = MagicMock()
        rule = _make_rule(query="event.kind:alert", indexes=["hit"])
        rule.rule_id = "rule-1"
        since_value = "2026-01-01T00:00:00Z"
        since = datetime(2026, 1, 1, tzinfo=timezone.utc)
        mock_get_rule.return_value = (rule, since)
        mock_search.side_effect = [
            {"items": [{"howler": {"id": "hit-1"}}], "next_deep_paging_id": "scroll-1"},
            {"items": [{"howler": {"id": "hit-2"}}]},
        ]
        mock_enqueue.side_effect = [None, HowlerRuntimeError("queue unavailable")]

        with pytest.raises(HowlerRuntimeError, match="queue unavailable"):
            correlation_service.enqueue_backfill("case-1", "rule-1", since_value, user)

        assert [call.args[0] for call in mock_enqueue.call_args_list] == [["hit-1"], ["hit-2"]]

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


def _uuid(value: int) -> str:
    return str(UUID(int=value))


def _make_real_case(case_id: str) -> Case:
    return Case({"case_id": case_id, "title": f"case {case_id}", "summary": "keep this summary"})


def _make_real_hit(record_id: str) -> Hit:
    return Hit(
        {
            "howler": {"id": record_id, "analytic": "Correlation test", "hash": "0123456789abcdef"},
            "message": "keep this hit message",
        }
    )


def _make_real_event(record_id: str) -> Event:
    return Event({"howler": {"id": record_id, "hash": "abcdef0123456789"}, "message": "keep this event message"})


def _bulk_updates(plan: ElasticBulkPlan) -> list[tuple[str, str, dict[str, Any]]]:
    """Decode real bulk-plan NDJSON into (target index, document ID, partial body)."""
    lines = [json.loads(line) for line in plan.get_plan_data().splitlines()]
    return [
        (lines[offset]["update"]["_index"], lines[offset]["update"]["_id"], lines[offset + 1]["doc"])
        for offset in range(0, len(lines), 2)
    ]


def _setup_ds(
    mock_ds_fn: MagicMock,
    cases: dict[str, Any],
    hits: dict[str, Any] | None = None,
    events: dict[str, Any] | None = None,
    case_versions: dict[str, str] | None = None,
    hit_versions: dict[str, str] | None = None,
    event_versions: dict[str, str] | None = None,
) -> MagicMock:
    """Wire up a datastore mock with versioned reads and the real version resolver."""
    mock_ds = MagicMock()
    mock_ds_fn.return_value = mock_ds

    def versioned_get(records: dict[str, Any] | None, versions: dict[str, str] | None, *args, **kwargs):
        key = args[0] if args else kwargs.get("key")
        record = (records or {}).get(key)
        if kwargs.get("version"):
            # Legacy two-part version tokens resolve to each collection's alias;
            # individual tests can provide three-part ILM tokens for physical indexes.
            return record, (versions or {}).get(key, f"{key}-seq---{key}-term") if record else "create"
        return record

    mock_ds.case.get.side_effect = lambda cid, *args, **kwargs: versioned_get(
        cases, case_versions, cid, *args, **kwargs
    )
    mock_ds.hit.get.side_effect = lambda *args, **kwargs: versioned_get(hits, hit_versions, *args, **kwargs)
    mock_ds.event.get.side_effect = lambda *args, **kwargs: versioned_get(events, event_versions, *args, **kwargs)
    mock_ds.__getitem__.side_effect = lambda item_type: getattr(mock_ds, item_type)

    # Keep collection objects mocked, but delegate token parsing to the production
    # ESCollection resolver so these tests cover legacy aliases and ILM indexes.
    for item_type in ("case", "hit", "event"):
        collection = getattr(mock_ds, item_type)
        collection.name = f"howler-{item_type}"
        resolver_owner = SimpleNamespace(name=collection.name)
        collection.get_version_write_target.side_effect = lambda version, owner=resolver_owner: (
            ESCollection.get_version_write_target(owner, version)
        )

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
            "hit-1", hit, index="howler-hit", fields=["howler.related"]
        )
        mock_ds.hit.bulk.assert_called_once_with(mock_ds.hit.get_bulk_plan.return_value)

        mock_ds.case.get_bulk_plan.return_value.add_update_operation.assert_called_once_with(
            "case-1", case, index="howler-case", fields=["items", "targets", "threats", "indicators"]
        )
        mock_ds.case.bulk.assert_called_once_with(mock_ds.case.get_bulk_plan.return_value, refresh="wait_for")
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
            "case-1", case, index="howler-case", fields=["items", "targets", "threats", "indicators"]
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
            "obs-1", event, index="howler-event", fields=["howler.related"]
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


class TestCorrelationBulkRouting:
    """Regression coverage for routing correlation partial updates by read version."""

    @patch("howler.services.correlation_service.comms_service")
    @patch("howler.services.correlation_service.search_service")
    @patch("howler.services.correlation_service.get_active_rules")
    @patch("howler.services.correlation_service.datastore")
    def test_routes_real_bulk_updates_to_versioned_indexes_and_batches_cached_records(
        self, mock_ds_fn, mock_get_rules, mock_search_svc, mock_comms
    ):
        case_old_id, case_current_id = _uuid(101), _uuid(102)
        hit_old_id, hit_current_id = _uuid(201), _uuid(202)
        event_old_id, event_current_id = _uuid(301), _uuid(302)
        cases = {case_old_id: _make_real_case(case_old_id), case_current_id: _make_real_case(case_current_id)}
        hits = {hit_old_id: _make_real_hit(hit_old_id), hit_current_id: _make_real_hit(hit_current_id)}
        events = {event_old_id: _make_real_event(event_old_id), event_current_id: _make_real_event(event_current_id)}

        versions = {
            "case_versions": {
                case_old_id: "howler-case-000001---10---1",
                case_current_id: "howler-case-000002---20---1",
            },
            "hit_versions": {
                hit_old_id: "howler-hit-000001---11---1",
                hit_current_id: "howler-hit-000002---21---1",
            },
            "event_versions": {
                event_old_id: "howler-event-000001---12---1",
                event_current_id: "howler-event-000002---22---1",
            },
        }
        mock_ds = _setup_ds(mock_ds_fn, cases, hits, events, **versions)

        active_case_index = "howler-case-000002"
        active_hit_index = "howler-hit-000002"
        active_event_index = "howler-event-000002"
        case_plan = ElasticBulkPlan([active_case_index], Case)
        hit_plan = ElasticBulkPlan([active_hit_index], Hit)
        event_plan = ElasticBulkPlan([active_event_index], Event)
        mock_ds.case.get_bulk_plan.return_value = case_plan
        mock_ds.hit.get_bulk_plan.return_value = hit_plan
        mock_ds.event.get_bulk_plan.return_value = event_plan

        rule = _make_rule(destination="correlated/{{howler.id}}", indexes=["hit", "event"])
        mock_get_rules.return_value = [(case_old_id, rule), (case_current_id, rule)]
        results = [
            {"howler": {"id": hit_old_id}, "__index": "hit"},
            {"howler": {"id": hit_current_id}, "__index": "hit"},
            {"howler": {"id": event_old_id}, "__index": "event"},
            {"howler": {"id": event_current_id}, "__index": "event"},
        ]
        mock_search_svc.search.return_value = {"items": results}
        second_rule_for_old_case = _make_rule(destination="another-path/{{howler.id}}", indexes=["hit", "event"])
        mock_get_rules.return_value.append((case_old_id, second_rule_for_old_case))

        persisted: list[str] = []
        mock_ds.hit.bulk.side_effect = lambda _plan: (persisted.append("hit"), True)[1]
        mock_ds.event.bulk.side_effect = lambda _plan: (persisted.append("event"), True)[1]
        mock_ds.case.bulk.side_effect = lambda _plan, refresh=None: (persisted.append(f"case:{refresh}"), True)[1]
        mock_comms.emit.side_effect = lambda *_args, **_kwargs: persisted.append("notify")

        with patch.object(correlation_service.case_service, "datastore", return_value=mock_ds):
            added = correlation_service.process_batch([hit_old_id, hit_current_id, event_old_id, event_current_id])

        assert added == 8
        assert len(case_plan.operations) == 2
        assert len(hit_plan.operations) == 2
        assert len(event_plan.operations) == 2
        assert dict((doc_id, index) for index, doc_id, _ in _bulk_updates(case_plan)) == {
            case_old_id: "howler-case-000001",
            case_current_id: active_case_index,
        }
        assert dict((doc_id, index) for index, doc_id, _ in _bulk_updates(hit_plan)) == {
            hit_old_id: "howler-hit-000001",
            hit_current_id: active_hit_index,
        }
        assert dict((doc_id, index) for index, doc_id, _ in _bulk_updates(event_plan)) == {
            event_old_id: "howler-event-000001",
            event_current_id: active_event_index,
        }

        case_updates = _bulk_updates(case_plan)
        assert all(set(body) == {"items", "targets", "threats", "indicators"} for _, _, body in case_updates)
        backing_updates = _bulk_updates(hit_plan) + _bulk_updates(event_plan)
        assert all(set(body) == {"howler"} and set(body["howler"]) == {"related"} for _, _, body in backing_updates)
        assert all(
            json.loads(operation[0]).get("update")
            for plan in (case_plan, hit_plan, event_plan)
            for operation in plan.operations
        )

        assert mock_ds.case.get.call_count == 2
        assert all(call.kwargs == {"as_obj": True, "version": True} for call in mock_ds.case.get.call_args_list)
        versioned_hit_reads = [read for read in mock_ds.hit.get.call_args_list if read.kwargs.get("version")]
        versioned_event_reads = [read for read in mock_ds.event.get.call_args_list if read.kwargs.get("version")]
        assert len(versioned_hit_reads) == 2
        assert {read.args[0] for read in versioned_hit_reads} == {hit_old_id, hit_current_id}
        assert len(versioned_event_reads) == 2
        assert {read.kwargs["key"] for read in versioned_event_reads} == {event_old_id, event_current_id}
        mock_ds.hit.bulk.assert_called_once_with(hit_plan)
        mock_ds.event.bulk.assert_called_once_with(event_plan)
        mock_ds.case.bulk.assert_called_once_with(case_plan, refresh="wait_for")
        assert persisted.count("hit") == 1
        assert persisted.count("event") == 1
        assert persisted.count("case:wait_for") == 1
        assert persisted.index("case:wait_for") < persisted.index("notify")
        assert persisted.count("notify") == 2

    @patch("howler.services.correlation_service.comms_service")
    @patch("howler.services.correlation_service.search_service")
    @patch("howler.services.correlation_service.get_active_rules")
    @patch("howler.services.correlation_service.datastore")
    def test_legacy_non_ilm_versions_route_updates_to_collection_alias(
        self, mock_ds_fn, mock_get_rules, mock_search_svc, mock_comms
    ):
        case_id, hit_id = _uuid(401), _uuid(402)
        case = _make_real_case(case_id)
        hit = _make_real_hit(hit_id)
        mock_ds = _setup_ds(
            mock_ds_fn,
            {case_id: case},
            {hit_id: hit},
            case_versions={case_id: "7---2"},
            hit_versions={hit_id: "9---3"},
        )
        case_plan = ElasticBulkPlan(["howler-case_hot"], Case)
        hit_plan = ElasticBulkPlan(["howler-hit_hot"], Hit)
        mock_ds.case.get_bulk_plan.return_value = case_plan
        mock_ds.hit.get_bulk_plan.return_value = hit_plan
        mock_get_rules.return_value = [(case_id, _make_rule(destination="legacy"))]
        mock_search_svc.search.return_value = {"items": [{"howler": {"id": hit_id}, "__index": "hit"}]}

        with patch.object(correlation_service.case_service, "datastore", return_value=mock_ds):
            added = correlation_service.process_batch([hit_id])

        assert added == 1
        assert _bulk_updates(case_plan)[0][0] == "howler-case"
        assert _bulk_updates(hit_plan)[0][0] == "howler-hit"

    @patch("howler.services.correlation_service.comms_service")
    @patch("howler.services.correlation_service.search_service")
    @patch("howler.services.correlation_service.get_active_rules")
    @patch("howler.services.correlation_service.datastore")
    def test_real_bulk_error_from_backing_collection_prevents_case_success_notification(
        self, mock_ds_fn, mock_get_rules, mock_search_svc, mock_comms
    ):
        case_id, hit_id = _uuid(601), _uuid(602)
        case = _make_real_case(case_id)
        hit = _make_real_hit(hit_id)
        mock_ds = _setup_ds(
            mock_ds_fn,
            {case_id: case},
            {hit_id: hit},
            case_versions={case_id: "howler-case-000001---1---1"},
            hit_versions={hit_id: "howler-hit-000001---2---1"},
        )
        case_plan = ElasticBulkPlan(["howler-case-000002"], Case)
        hit_plan = ElasticBulkPlan(["howler-hit-000002"], Hit)
        mock_ds.case.get_bulk_plan.return_value = case_plan
        mock_ds.hit.get_bulk_plan.return_value = hit_plan
        mock_get_rules.return_value = [(case_id, _make_rule(destination="errors"))]
        mock_search_svc.search.return_value = {"items": [{"howler": {"id": hit_id}, "__index": "hit"}]}

        response = {
            "errors": True,
            "items": [
                {
                    "update": {
                        "_index": "howler-hit-000001",
                        "_id": hit_id,
                        "status": 404,
                        "error": {"type": "document_missing_exception", "reason": "missing from active index"},
                    }
                }
            ],
        }
        fake_collection = object.__new__(ESCollection)
        fake_collection.max_attempts = 1
        fake_collection.datastore = SimpleNamespace(client=SimpleNamespace(bulk=MagicMock(return_value=response)))
        mock_ds.hit.bulk.side_effect = fake_collection.bulk

        with patch.object(correlation_service.case_service, "datastore", return_value=mock_ds):
            with pytest.raises(HowlerRuntimeError, match="Bulk backing record update reported errors"):
                correlation_service.process_batch([hit_id])

        request = fake_collection.datastore.client.bulk.call_args.kwargs["operations"]
        assert json.loads(request.splitlines()[0]) == {"update": {"_index": "howler-hit-000001", "_id": hit_id}}
        mock_ds.case.bulk.assert_not_called()
        mock_comms.emit.assert_not_called()


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
            patch.object(
                correlation_service,
                "_resolve_backing_object",
                return_value=(backing_obj, "hit-version"),
            ),
            patch.object(correlation_service.case_service, "get_parent_from_path", return_value=None),
            patch.object(correlation_service.case_service, "check_conflicts", return_value=False),
            patch.object(correlation_service.case_service, "add_backreference", return_value=True),
        ):
            added = correlation_service._add_record_to_case(case, {"howler": {"id": "hit-1"}}, rule, {})

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
