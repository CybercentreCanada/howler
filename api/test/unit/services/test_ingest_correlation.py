"""Unit tests verifying that records ingested via the ingest endpoint are
picked up by the correlation service.

These tests mock the services and queue to verify the contract between
ingest.py (producer) and correlation_service.process_batch (consumer).
"""

from typing import Any
from unittest.mock import MagicMock, patch

from howler.config import CLASSIFICATION
from howler.odm.models.case import CaseItem, CaseRule
from howler.services import correlation_service

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_rule(
    enabled: bool = True,
    query: str = "*:*",
    destination: str = "related",
    indexes: list[str] | None = None,
) -> CaseRule:
    data: dict[str, Any] = {
        "query": query,
        "destination": destination,
        "author": "test_user",
        "enabled": enabled,
    }

    if indexes is not None:
        data["indexes"] = indexes

    return CaseRule(data)


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

    # Mirror ElasticBulkPlan.empty: starts empty, flips once an operation is queued.
    bulk_plan = mock_ds.case.get_bulk_plan.return_value
    bulk_plan.empty = True

    def _mark_not_empty(*args, **kwargs):
        bulk_plan.empty = False

    bulk_plan.add_update_operation.side_effect = _mark_not_empty
    bulk_plan.add_index_operation.side_effect = _mark_not_empty

    return mock_ds


# ---------------------------------------------------------------------------
# Ingested alerts are correlated
# ---------------------------------------------------------------------------


class TestIngestedAlertsCorrelation:
    """Verify that alerts (hits) ingested via the API reach the correlation service."""

    @patch("howler.services.correlation_service.comms_service")
    @patch("howler.services.correlation_service.search_service")
    @patch("howler.services.correlation_service.get_active_rules")
    @patch("howler.services.correlation_service.datastore")
    def test_single_alert_matches_rule(self, mock_ds_fn, mock_get_rules, mock_search_svc, mock_comms):
        """A single ingested alert ID that matches a rule is appended to the case."""
        case = _make_case("case-1")
        _setup_ds(mock_ds_fn, {"case-1": case}, hits={"ingested-hit-1": _make_backing_obj()})

        rule = _make_rule(query="event.kind:alert", destination="alerts/incoming")
        mock_get_rules.return_value = [("case-1", rule)]

        mock_search_svc.search.return_value = {
            "items": [{"howler": {"id": "ingested-hit-1"}, "__index": "hit"}],
            "total": 1,
            "offset": 0,
            "rows": 1,
        }

        added = correlation_service.process_batch(["ingested-hit-1"])

        assert added == 1
        hit_item = next(i for i in case.items if i.type == "hit")
        assert hit_item.value == "ingested-hit-1"
        assert hit_item.name == "incoming"

    @patch("howler.services.correlation_service.comms_service")
    @patch("howler.services.correlation_service.search_service")
    @patch("howler.services.correlation_service.get_active_rules")
    @patch("howler.services.correlation_service.datastore")
    def test_batch_of_alerts_all_matched(self, mock_ds_fn, mock_get_rules, mock_search_svc, mock_comms):
        """Multiple alerts in a batch all matching the same rule are each added."""
        case = _make_case("case-1")
        hits = {"hit-a": _make_backing_obj(), "hit-b": _make_backing_obj(), "hit-c": _make_backing_obj()}
        _setup_ds(mock_ds_fn, {"case-1": case}, hits=hits)

        rule = _make_rule(query="event.kind:alert", destination="alerts/{{howler.id}}")
        mock_get_rules.return_value = [("case-1", rule)]

        mock_search_svc.search.return_value = {
            "items": [
                {"howler": {"id": "hit-a"}, "__index": "hit"},
                {"howler": {"id": "hit-b"}, "__index": "hit"},
                {"howler": {"id": "hit-c"}, "__index": "hit"},
            ],
            "total": 3,
            "offset": 0,
            "rows": 3,
        }

        added = correlation_service.process_batch(["hit-a", "hit-b", "hit-c"])

        assert added == 3
        assert len([i for i in case.items if i.type == "hit"]) == 3

    @patch("howler.services.correlation_service.search_service")
    @patch("howler.services.correlation_service.get_active_rules")
    @patch("howler.services.correlation_service.datastore")
    def test_alert_not_matching_rule_not_added(self, mock_ds_fn, mock_get_rules, mock_search_svc):
        """An alert that does not match the rule query is not added to any case."""
        case = _make_case("case-1")
        _setup_ds(mock_ds_fn, {"case-1": case})

        rule = _make_rule(query="event.kind:signal", destination="signals")
        mock_get_rules.return_value = [("case-1", rule)]

        # ES returns no results for this batch
        mock_search_svc.search.return_value = {
            "items": [],
            "total": 0,
            "offset": 0,
            "rows": 0,
        }

        added = correlation_service.process_batch(["hit-no-match"])

        assert added == 0
        assert case.items == []

    @patch("howler.services.correlation_service.comms_service")
    @patch("howler.services.correlation_service.search_service")
    @patch("howler.services.correlation_service.get_active_rules")
    @patch("howler.services.correlation_service.datastore")
    def test_alert_matched_by_multiple_rules(self, mock_ds_fn, mock_get_rules, mock_search_svc, mock_comms):
        """A single alert matching rules from two different cases is added to both."""
        case_a = _make_case("case-a")
        case_b = _make_case("case-b")
        _setup_ds(mock_ds_fn, {"case-a": case_a, "case-b": case_b}, hits={"hit-1": _make_backing_obj()})

        rule_a = _make_rule(query="event.kind:alert", destination="case-a-alerts")
        rule_b = _make_rule(query="*:*", destination="case-b-all")
        mock_get_rules.return_value = [("case-a", rule_a), ("case-b", rule_b)]

        search_result = {
            "items": [{"howler": {"id": "hit-1"}, "__index": "hit"}],
            "total": 1,
            "offset": 0,
            "rows": 1,
        }
        mock_search_svc.search.return_value = search_result

        added = correlation_service.process_batch(["hit-1"])

        assert added == 2
        assert len([i for i in case_a.items if i.type == "hit"]) == 1
        assert len([i for i in case_b.items if i.type == "hit"]) == 1

    @patch("howler.services.correlation_service.comms_service")
    @patch("howler.services.correlation_service.search_service")
    @patch("howler.services.correlation_service.get_active_rules")
    @patch("howler.services.correlation_service.datastore")
    def test_duplicate_alert_skipped(self, mock_ds_fn, mock_get_rules, mock_search_svc, mock_comms):
        """An alert already present in the case is skipped."""
        existing = CaseItem({"type": "hit", "value": "hit-dup", "name": "related"})
        case = _make_case("case-1", items=[existing])
        _setup_ds(mock_ds_fn, {"case-1": case}, hits={"hit-dup": _make_backing_obj()})

        rule = _make_rule(query="*:*", destination="related")
        mock_get_rules.return_value = [("case-1", rule)]

        mock_search_svc.search.return_value = {
            "items": [{"howler": {"id": "hit-dup"}, "__index": "hit"}],
            "total": 1,
            "offset": 0,
            "rows": 1,
        }

        added = correlation_service.process_batch(["hit-dup"])

        assert added == 0
        assert case.items == [existing]

    @patch("howler.services.correlation_service.comms_service")
    @patch("howler.services.correlation_service.search_service")
    @patch("howler.services.correlation_service.get_active_rules")
    @patch("howler.services.correlation_service.datastore")
    def test_alert_destination_rendered_with_hit_data(self, mock_ds_fn, mock_get_rules, mock_search_svc, mock_comms):
        """The destination path is rendered as a Mustache template with hit fields."""
        case = _make_case("case-1")
        _setup_ds(mock_ds_fn, {"case-1": case}, hits={"hit-tpl": _make_backing_obj()})

        rule = _make_rule(
            query="event.kind:alert",
            destination="alerts/{{howler.analytic}}/{{event.kind}}",
        )
        mock_get_rules.return_value = [("case-1", rule)]

        mock_search_svc.search.return_value = {
            "items": [
                {
                    "howler": {"id": "hit-tpl", "analytic": "Phishing Detector"},
                    "event": {"kind": "alert"},
                    "__index": "hit",
                }
            ],
            "total": 1,
            "offset": 0,
            "rows": 1,
        }

        correlation_service.process_batch(["hit-tpl"])

        hit_item = next(i for i in case.items if i.type == "hit")
        assert hit_item.value == "hit-tpl"
        assert hit_item.name == "alert"


# ---------------------------------------------------------------------------
# Ingested events are correlated
# ---------------------------------------------------------------------------


class TestIngestedEventsCorrelation:
    """Verify that events ingested via the API reach the correlation service."""

    @patch("howler.services.correlation_service.comms_service")
    @patch("howler.services.correlation_service.search_service")
    @patch("howler.services.correlation_service.get_active_rules")
    @patch("howler.services.correlation_service.datastore")
    def test_event_matches_rule_with_event_index(self, mock_ds_fn, mock_get_rules, mock_search_svc, mock_comms):
        """An event matching a rule targeting the event index is added."""
        case = _make_case("case-1")
        _setup_ds(mock_ds_fn, {"case-1": case}, events={"obs-1": _make_backing_obj()})

        rule = _make_rule(
            query="event.kind:enrichment",
            destination="events",
            indexes=["event"],
        )
        mock_get_rules.return_value = [("case-1", rule)]

        mock_search_svc.search.return_value = {
            "items": [{"howler": {"id": "obs-1"}, "__index": "event"}],
            "total": 1,
            "offset": 0,
            "rows": 1,
        }

        added = correlation_service.process_batch(["obs-1"])

        assert added == 1
        event_item = next(i for i in case.items if i.type == "event")
        assert event_item.value == "obs-1"

    @patch("howler.services.correlation_service.search_service")
    @patch("howler.services.correlation_service.get_active_rules")
    @patch("howler.services.correlation_service.datastore")
    def test_event_not_matched_by_hit_only_rule(self, mock_ds_fn, mock_get_rules, mock_search_svc):
        """A rule targeting only the hit index does not match events."""
        case = _make_case("case-1")
        _setup_ds(mock_ds_fn, {"case-1": case})

        rule = _make_rule(query="*:*", destination="hits", indexes=["hit"])
        mock_get_rules.return_value = [("case-1", rule)]

        # Search only hits — no events returned
        mock_search_svc.search.return_value = {
            "items": [],
            "total": 0,
            "offset": 0,
            "rows": 0,
        }

        added = correlation_service.process_batch(["obs-1"])

        assert added == 0

    @patch("howler.services.correlation_service.comms_service")
    @patch("howler.services.correlation_service.search_service")
    @patch("howler.services.correlation_service.get_active_rules")
    @patch("howler.services.correlation_service.datastore")
    def test_mixed_batch_alerts_and_events(self, mock_ds_fn, mock_get_rules, mock_search_svc, mock_comms):
        """A batch with both hit and event IDs can match a rule searching both indexes."""
        case = _make_case("case-1")
        _setup_ds(
            mock_ds_fn,
            {"case-1": case},
            hits={"hit-1": _make_backing_obj()},
            events={"obs-1": _make_backing_obj()},
        )

        rule = _make_rule(query="*:*", destination="all/{{howler.id}}", indexes=["hit", "event"])
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

        types = {i.type for i in case.items if i.type != "folder"}
        values = {i.value for i in case.items if i.type != "folder"}
        assert types == {"hit", "event"}
        assert values == {"hit-1", "obs-1"}

    @patch("howler.services.correlation_service.comms_service")
    @patch("howler.services.correlation_service.search_service")
    @patch("howler.services.correlation_service.get_active_rules")
    @patch("howler.services.correlation_service.datastore")
    def test_event_batch_multiple_rules(self, mock_ds_fn, mock_get_rules, mock_search_svc, mock_comms):
        """Multiple events matched by multiple rules across different cases."""
        case_a = _make_case("case-a")
        case_b = _make_case("case-b")
        events = {"obs-1": _make_backing_obj(), "obs-2": _make_backing_obj()}
        _setup_ds(mock_ds_fn, {"case-a": case_a, "case-b": case_b}, events=events)

        rule_a = _make_rule(query="*:*", destination="case-a-obs/{{howler.id}}", indexes=["event"])
        rule_b = _make_rule(query="*:*", destination="case-b-obs/{{howler.id}}", indexes=["event"])
        mock_get_rules.return_value = [("case-a", rule_a), ("case-b", rule_b)]

        search_result = {
            "items": [
                {"howler": {"id": "obs-1"}, "__index": "event"},
                {"howler": {"id": "obs-2"}, "__index": "event"},
            ],
            "total": 2,
            "offset": 0,
            "rows": 2,
        }
        mock_search_svc.search.return_value = search_result

        added = correlation_service.process_batch(["obs-1", "obs-2"])

        # 2 events × 2 rules = 4 appends
        assert added == 4
        assert len([i for i in case_a.items if i.type == "event"]) == 2
        assert len([i for i in case_b.items if i.type == "event"]) == 2


# ---------------------------------------------------------------------------
# Queue contract: IDs pushed by ingest are consumed by process_batch
# ---------------------------------------------------------------------------


class TestIngestToCorrelationContract:
    """Verify the queue contract between the ingest endpoint and the correlation worker."""

    @patch("howler.services.correlation_service.comms_service")
    @patch("howler.services.correlation_service.search_service")
    @patch("howler.services.correlation_service.get_active_rules")
    @patch("howler.services.correlation_service.datastore")
    def test_ids_format_matches_process_batch_expectation(
        self, mock_ds_fn, mock_get_rules, mock_search_svc, mock_comms
    ):
        """process_batch expects a list[str] of record IDs — the same format pushed by ingest."""
        case = _make_case("case-1")
        hits = {"abc123": _make_backing_obj(), "def456": _make_backing_obj()}
        _setup_ds(mock_ds_fn, {"case-1": case}, hits=hits)

        rule = _make_rule(query="*:*", destination="related/{{howler.id}}")
        mock_get_rules.return_value = [("case-1", rule)]

        ingested_ids = ["abc123", "def456"]

        mock_search_svc.search.return_value = {
            "items": [
                {"howler": {"id": "abc123"}, "__index": "hit"},
                {"howler": {"id": "def456"}, "__index": "hit"},
            ],
            "total": 2,
            "offset": 0,
            "rows": 2,
        }

        added = correlation_service.process_batch(ingested_ids)

        assert added == 2

        # Verify the ID filter sent to ES contains both IDs
        search_call = mock_search_svc.search.call_args
        filters = search_call.kwargs["filters"]
        assert any("abc123" in f and "def456" in f for f in filters)


# ---------------------------------------------------------------------------
# get_active_rules(): timeframe and expire_after_resolved
# ---------------------------------------------------------------------------


class TestGetActiveRulesExpiry:
    """Tests for correlation_service.get_active_rules with the new expiry model."""

    @patch("howler.services.correlation_service.case_service")
    @patch("howler.services.correlation_service.datastore")
    def test_no_timeframe_always_active(self, mock_ds_fn, mock_case_svc):
        """A rule with no timeframe is always active."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        rule = _make_rule(query="*:*")
        # Ensure timeframe is None (default from _make_rule)
        rule.timeframe = None
        rule.expire_after_resolved = False

        case = MagicMock()
        case.case_id = "case-1"
        case.rules = [rule]
        mock_ds.case.stream_search.return_value = [case]

        results = correlation_service.get_active_rules()
        assert len(results) == 1

    @patch("howler.services.correlation_service.case_service")
    @patch("howler.services.correlation_service.datastore")
    def test_timeframe_from_creation_active(self, mock_ds_fn, mock_case_svc):
        """Rule with timeframe from creation is active when within the window."""
        from datetime import datetime, timedelta, timezone

        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        rule = _make_rule(query="*:*")
        rule.timeframe = 14
        rule.expire_after_resolved = False
        # Created 5 days ago — still within 14-day window
        rule.created_at = datetime.now(timezone.utc) - timedelta(days=5)

        case = MagicMock()
        case.case_id = "case-1"
        case.rules = [rule]
        mock_ds.case.stream_search.return_value = [case]

        results = correlation_service.get_active_rules()
        assert len(results) == 1

    @patch("howler.services.correlation_service.case_service")
    @patch("howler.services.correlation_service.datastore")
    def test_timeframe_from_creation_expired(self, mock_ds_fn, mock_case_svc):
        """Rule with timeframe from creation is inactive after the window."""
        from datetime import datetime, timedelta, timezone

        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        rule = _make_rule(query="*:*")
        rule.timeframe = 7
        rule.expire_after_resolved = False
        # Created 10 days ago — past the 7-day window
        rule.created_at = datetime.now(timezone.utc) - timedelta(days=10)

        case = MagicMock()
        case.case_id = "case-1"
        case.rules = [rule]
        mock_ds.case.stream_search.return_value = [case]

        results = correlation_service.get_active_rules()
        assert len(results) == 0

    @patch("howler.services.correlation_service.case_service")
    @patch("howler.services.correlation_service.datastore")
    def test_expire_after_resolved_case_not_resolved(self, mock_ds_fn, mock_case_svc):
        """Rule with expire_after_resolved is active when case not yet resolved."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        rule = _make_rule(query="*:*")
        rule.timeframe = 7
        rule.expire_after_resolved = True

        case = MagicMock()
        case.case_id = "case-1"
        case.rules = [rule]
        mock_ds.case.stream_search.return_value = [case]

        # Case never resolved
        mock_case_svc.get_last_resolved_time.return_value = None

        results = correlation_service.get_active_rules()
        assert len(results) == 1

    @patch("howler.services.correlation_service.case_service")
    @patch("howler.services.correlation_service.datastore")
    def test_expire_after_resolved_within_window(self, mock_ds_fn, mock_case_svc):
        """Rule with expire_after_resolved is active within the window after resolution."""
        from datetime import datetime, timedelta, timezone

        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        rule = _make_rule(query="*:*")
        rule.timeframe = 14
        rule.expire_after_resolved = True

        case = MagicMock()
        case.case_id = "case-1"
        case.rules = [rule]
        mock_ds.case.stream_search.return_value = [case]

        # Resolved 5 days ago — still within 14-day window
        mock_case_svc.get_last_resolved_time.return_value = datetime.now(timezone.utc) - timedelta(days=5)

        results = correlation_service.get_active_rules()
        assert len(results) == 1

    @patch("howler.services.correlation_service.case_service")
    @patch("howler.services.correlation_service.datastore")
    def test_expire_after_resolved_past_window(self, mock_ds_fn, mock_case_svc):
        """Rule with expire_after_resolved is inactive after the window."""
        from datetime import datetime, timedelta, timezone

        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        rule = _make_rule(query="*:*")
        rule.timeframe = 7
        rule.expire_after_resolved = True

        case = MagicMock()
        case.case_id = "case-1"
        case.rules = [rule]
        mock_ds.case.stream_search.return_value = [case]

        # Resolved 10 days ago — past 7-day window
        mock_case_svc.get_last_resolved_time.return_value = datetime.now(timezone.utc) - timedelta(days=10)

        results = correlation_service.get_active_rules()
        assert len(results) == 0
