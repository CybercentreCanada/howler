from datetime import datetime, timezone

import pytest

from howler.common.exceptions import HowlerValueError
from howler.odm.models.case import CASE_ITEM_TYPES, Case, CaseEnrichment, CaseItem, CaseLog, CaseRule, CaseTask
from howler.odm.randomizer import random_model_obj


class TestCaseLog:
    """Tests for the CaseLog ODM model."""

    def test_create_case_log_with_explanation(self):
        """CaseLog is valid when explanation is provided alongside user."""
        log = CaseLog({"timestamp": "NOW", "explanation": "Case created", "user": "admin"})

        assert log.user == "admin"
        assert log.explanation == "Case created"
        assert log.key is None
        assert log.previous_value is None
        assert log.new_value is None

    def test_create_case_log_without_explanation_requires_timestamp_new_value_user(self):
        """CaseLog without explanation requires timestamp, new_value, and user."""
        log = CaseLog(
            {"timestamp": "NOW", "key": "escalation", "previous_value": "low", "new_value": "high", "user": "bob"}
        )

        assert log.user == "bob"
        assert log.new_value == "high"
        assert log.previous_value == "low"
        assert log.key == "escalation"

    def test_create_case_log_missing_new_value_without_explanation_raises(self):
        """CaseLog raises HowlerValueError when explanation is absent and new_value is missing."""
        with pytest.raises(HowlerValueError):
            CaseLog({"timestamp": "NOW", "user": "analyst"})  # no explanation and no new_value

    def test_create_case_log_missing_user_without_explanation_raises(self):
        """CaseLog raises HowlerValueError when explanation is absent and user is missing."""
        with pytest.raises(HowlerValueError):
            CaseLog({"timestamp": "NOW", "new_value": "high"})  # no explanation and no user

    def test_case_log_as_primitives(self):
        """as_primitives returns a plain dict containing all stored fields."""
        log = CaseLog(
            {
                "timestamp": "NOW",
                "key": "escalation",
                "previous_value": "low",
                "new_value": "high",
                "user": "alice",
            }
        )
        primitives = log.as_primitives()

        assert isinstance(primitives, dict)
        assert primitives["user"] == "alice"
        assert primitives["new_value"] == "high"
        assert primitives["previous_value"] == "low"
        assert primitives["key"] == "escalation"


class TestCaseItem:
    """Tests for the CaseItem ODM model."""

    def test_create_case_item_minimal(self):
        """CaseItem can be created with required fields only."""
        item = CaseItem({"path": "/alerts", "type": "hit", "value": "abc123"})

        assert item.path == "/alerts"
        assert item.type == "hit"
        assert item.value == "abc123"

    def test_create_case_item_with_id(self):
        """CaseItem can be created with an optional id."""
        item = CaseItem({"path": "/obs", "type": "observable", "value": "obs-001"})

        assert item.value == "obs-001"

    @pytest.mark.parametrize("item_type", sorted(CASE_ITEM_TYPES))
    def test_valid_item_types(self, item_type):
        """All declared CASE_ITEM_TYPES are accepted by the enum field."""
        item = CaseItem({"path": "/test", "type": item_type, "value": "val"})
        assert item.type == item_type

    def test_invalid_item_type_raises(self):
        """An invalid type value raises an error."""
        with pytest.raises(HowlerValueError):
            CaseItem({"path": "/test", "type": "invalid_type", "value": "val"})

    def test_case_item_missing_required_field(self):
        """CaseItem raises HowlerValueError when a required field is missing."""
        with pytest.raises(HowlerValueError):
            CaseItem({"path": "/test", "type": "hit"})  # missing 'value'

        with pytest.raises(HowlerValueError):
            CaseItem({"path": "/test", "value": "v"})  # missing 'type'

    def test_case_item_as_primitives(self):
        """as_primitives returns a plain dict representation."""
        item = CaseItem({"path": "/alerts", "type": "hit", "value": "abc123"})
        primitives = item.as_primitives()

        assert isinstance(primitives, dict)
        assert primitives["path"] == "/alerts"
        assert primitives["type"] == "hit"
        assert primitives["value"] == "abc123"

    def test_case_item_visible_defaults_to_true(self):
        """CaseItem.visible is True by default."""
        item = CaseItem({"path": "/alerts", "type": "hit", "value": "abc123"})

        assert item.visible is True

    def test_case_item_visible_can_be_set_to_false(self):
        """CaseItem.visible can be explicitly set to False."""
        item = CaseItem({"path": "/alerts", "type": "hit", "value": "abc123", "visible": False})

        assert item.visible is False

    def test_case_item_visible_included_in_primitives(self):
        """visible field is present in as_primitives output."""
        item_true = CaseItem({"path": "/x", "type": "hit", "value": "v"})
        item_false = CaseItem({"path": "/x", "type": "hit", "value": "v", "visible": False})

        assert item_true.as_primitives()["visible"] is True
        assert item_false.as_primitives()["visible"] is False


class TestCaseRule:
    """Tests for the CaseRule ODM model."""

    def test_create_case_rule(self):
        """CaseRule can be created with all required fields."""
        rule = CaseRule(
            {
                "destination": "/alerts/critical",
                "query": "howler.score:>80",
                "author": "analyst1",
            }
        )

        assert rule.destination == "/alerts/critical"
        assert rule.query == "howler.score:>80"
        assert rule.author == "analyst1"
        assert rule.enabled is True
        assert rule.timeframe is None
        assert rule.rule_id is not None

    def test_case_rule_uuid_auto_generated(self):
        """CaseRule.id is a valid UUID auto-generated when not provided."""
        rule = CaseRule(
            {
                "destination": "/dest",
                "query": "*:*",
                "author": "user1",
            }
        )

        assert rule.rule_id is not None
        assert len(str(rule.id)) == 36  # UUID format

    def test_case_rule_enabled_defaults_to_true(self):
        """CaseRule.enabled defaults to True."""
        rule = CaseRule(
            {
                "destination": "/dest",
                "query": "*:*",
                "author": "user1",
            }
        )

        assert rule.enabled is True

    def test_case_rule_enabled_can_be_false(self):
        """CaseRule.enabled can be set to False."""
        rule = CaseRule(
            {
                "destination": "/dest",
                "query": "*:*",
                "author": "user1",
                "enabled": False,
            }
        )

        assert rule.enabled is False

    def test_case_rule_timeframe_is_optional(self):
        """CaseRule.timeframe defaults to None (no expiry)."""
        rule = CaseRule(
            {
                "destination": "/dest",
                "query": "*:*",
                "author": "user1",
            }
        )

        assert rule.timeframe is None

    def test_case_rule_timeframe_accepts_iso_date(self):
        """CaseRule.timeframe can be set to a valid ISO date string."""
        rule = CaseRule(
            {
                "destination": "/dest",
                "query": "*:*",
                "author": "user1",
                "timeframe": "2026-05-06T00:00:00Z",
            }
        )

        assert rule.timeframe is not None
        assert rule.timeframe.year == 2026
        assert rule.timeframe.month == 5

    def test_case_rule_as_primitives(self):
        """as_primitives returns expected dict with all fields."""
        rule = CaseRule(
            {
                "destination": "/dest",
                "query": "*:*",
                "author": "admin",
                "enabled": False,
                "timeframe": "2026-06-01T12:00:00Z",
            }
        )
        primitives = rule.as_primitives()

        assert primitives["destination"] == "/dest"
        assert primitives["query"] == "*:*"
        assert primitives["author"] == "admin"
        assert primitives["enabled"] is False
        assert "timeframe" in primitives
        assert primitives["rule_id"] is not None

    def test_case_rule_missing_required_field(self):
        """CaseRule raises HowlerValueError when a required field is missing."""
        with pytest.raises(HowlerValueError):
            CaseRule({"destination": "/dest"})  # missing 'query' and 'author'

        with pytest.raises(HowlerValueError):
            CaseRule({"query": "*:*"})  # missing 'destination' and 'author'

        with pytest.raises(HowlerValueError):
            CaseRule({"destination": "/dest", "query": "*:*"})  # missing 'author'

    def test_random_case_rule_model(self):
        """random_model_obj can generate a valid CaseRule."""
        rule = random_model_obj(CaseRule)
        assert rule.destination is not None
        assert rule.query is not None
        assert rule.author is not None
        assert rule.rule_id is not None


class TestCaseTask:
    """Tests for the CaseTask ODM model."""

    def test_create_case_task(self):
        """CaseTask can be created with required fields."""
        task = CaseTask(
            {
                "id": "00000000-0000-0000-0000-000000000001",
                "assignment": "analyst-team",
                "summary": "Review indicators",
                "path": "/alerts/critical",
            }
        )

        assert task.assignment == "analyst-team"
        assert task.summary == "Review indicators"
        assert task.path == "/alerts/critical"
        assert task.complete is False  # default

    def test_case_task_complete_flag(self):
        """CaseTask complete flag can be set to True."""
        task = CaseTask(
            {
                "id": "00000000-0000-0000-0000-000000000002",
                "complete": True,
                "assignment": "soc",
                "summary": "Done",
                "path": "/",
            }
        )

        assert task.complete is True

    def test_case_task_missing_required_field(self):
        """CaseTask raises HowlerValueError when a required field is missing."""
        with pytest.raises(HowlerValueError):
            CaseTask(
                {
                    "id": "00000000-0000-0000-0000-000000000003",
                    "assignment": "soc",
                    # missing 'summary' and 'path'
                }
            )

    def test_case_task_as_primitives(self):
        """as_primitives returns a dict with all expected CaseTask fields."""
        task = CaseTask(
            {
                "id": "00000000-0000-0000-0000-000000000005",
                "assignment": "soc",
                "summary": "Analyse logs",
                "path": "/alerts/critical",
                "complete": True,
            }
        )
        primitives = task.as_primitives()

        assert isinstance(primitives, dict)
        assert primitives["assignment"] == "soc"
        assert primitives["summary"] == "Analyse logs"
        assert primitives["path"] == "/alerts/critical"
        assert primitives["complete"] is True


class TestCaseEnrichment:
    """Tests for the CaseEnrichment ODM model."""

    def test_create_enrichment_empty_annotations(self):
        """CaseEnrichment defaults to empty annotations list."""
        enrichment = CaseEnrichment({"path": "/alerts"})

        assert enrichment.path == "/alerts"
        assert enrichment.annotations == []

    def test_create_enrichment_with_annotations(self):
        """CaseEnrichment can store annotation IDs."""
        enrichment = CaseEnrichment(
            {
                "path": "/alerts/phishing",
                "annotations": ["ann-1", "ann-2", "ann-3"],
            }
        )

        assert len(enrichment.annotations) == 3
        assert "ann-2" in enrichment.annotations


class TestCase:
    """Tests for the Case ODM model."""

    def test_case_missing_required_field(self):
        """Case raises HowlerValueError when a required field is missing."""
        with pytest.raises(HowlerValueError):
            Case(
                {
                    # missing 'title'
                    "summary": "S",
                    "overview": "O",
                    "escalation": "high",
                }
            )

        with pytest.raises(HowlerValueError):
            Case(
                {
                    "title": "T",
                    # missing 'summary'
                    "overview": "O",
                    "escalation": "high",
                }
            )

    def test_create_case_minimal(self):
        """Case can be created with only required fields."""
        case = Case(
            {
                "case_id": "case-001",
                "title": "Incident Alpha",
                "summary": "Summary text",
                "overview": "## Overview markdown",
                "escalation": "high",
            }
        )

        assert case.case_id == "case-001"
        assert case.title == "Incident Alpha"
        assert case.summary == "Summary text"
        assert case.overview == "## Overview markdown"
        assert case.escalation == "high"
        assert isinstance(case.created, datetime)  # default NOW produces a real datetime
        assert (
            abs((case.created - datetime.now(timezone.utc)).total_seconds()) < 60
        )  # created is recent (within 1 minute)
        assert case.updated is None
        assert case.start is None
        assert case.end is None
        assert case.targets == []
        assert case.threats == []
        assert case.indicators == []
        assert case.participants == []
        assert case.items == []
        assert case.enrichments == []
        assert case.rules == []
        assert case.tasks == []

    def test_create_case_with_lists(self):
        """Case list fields accept data correctly."""
        case = Case(
            {
                "case_id": "case-002",
                "title": "Incident Beta",
                "summary": "Summary",
                "overview": "Overview",
                "escalation": "low",
                "targets": ["server-1", "server-2"],
                "threats": ["apt-29"],
                "indicators": ["ioc-hash-abc"],
                "participants": ["analyst-1", "analyst-2"],
            }
        )

        assert len(case.targets) == 2
        assert "server-1" in case.targets
        assert case.threats == ["apt-29"]
        assert case.indicators == ["ioc-hash-abc"]
        assert len(case.participants) == 2

    def test_create_case_with_items(self):
        """Case can contain nested CaseItem objects."""
        case = Case(
            {
                "case_id": "case-003",
                "title": "With Items",
                "summary": "S",
                "overview": "O",
                "escalation": "medium",
                "items": [
                    {"path": "/obs", "type": "observable", "value": "1.2.3.4", "id": "obs-1"},
                    {"path": "/hits", "type": "hit", "value": "hit-abc"},
                ],
            }
        )

        assert len(case.items) == 2
        assert case.items[0].type == "observable"
        assert case.items[1].value == "hit-abc"

    def test_create_case_with_rules(self):
        """Case can contain nested CaseRule objects."""
        case = Case(
            {
                "case_id": "case-004",
                "title": "With Rules",
                "summary": "S",
                "overview": "O",
                "escalation": "high",
                "rules": [
                    {"destination": "/critical", "query": "howler.score:>90", "author": "analyst"},
                ],
            }
        )

        assert len(case.rules) == 1
        assert case.rules[0].query == "howler.score:>90"
        assert case.rules[0].author == "analyst"

    def test_create_case_with_tasks(self):
        """Case can contain nested CaseTask objects."""
        case = Case(
            {
                "case_id": "case-005",
                "title": "With Tasks",
                "summary": "S",
                "overview": "O",
                "escalation": "low",
                "tasks": [
                    {
                        "id": "00000000-0000-0000-0000-000000000010",
                        "assignment": "soc",
                        "summary": "Investigate",
                        "path": "/alerts",
                        "complete": False,
                    },
                ],
            }
        )

        assert len(case.tasks) == 1
        assert case.tasks[0].complete is False
        assert case.tasks[0].assignment == "soc"

    def test_create_case_with_enrichments(self):
        """Case can contain nested CaseEnrichment objects."""
        case = Case(
            {
                "case_id": "case-006",
                "title": "With Enrichments",
                "summary": "S",
                "overview": "O",
                "escalation": "high",
                "enrichments": [
                    {"path": "/obs/ip", "annotations": ["ann-1"]},
                ],
            }
        )

        assert len(case.enrichments) == 1
        assert case.enrichments[0].annotations == ["ann-1"]

    def test_case_as_primitives_roundtrip(self):
        """as_primitives produces a dict that can recreate the Case."""
        original = Case(
            {
                "case_id": "case-rt",
                "title": "Roundtrip",
                "summary": "Summary",
                "overview": "Overview",
                "escalation": "medium",
                "targets": ["t1"],
                "items": [{"path": "/a", "type": "hit", "value": "v1"}],
                "rules": [{"destination": "/b", "query": "q", "author": "admin"}],
                "enrichments": [{"path": "/c", "annotations": ["x"]}],
                "tasks": [
                    {
                        "id": "00000000-0000-0000-0000-000000000099",
                        "assignment": "a",
                        "summary": "s",
                        "path": "/d",
                    }
                ],
            }
        )

        primitives = original.as_primitives()
        rebuilt = Case(primitives)

        assert rebuilt.case_id == original.case_id
        assert rebuilt.title == original.title
        assert rebuilt.escalation == original.escalation
        assert rebuilt.summary == original.summary
        assert rebuilt.overview == original.overview
        assert rebuilt.targets == original.targets
        assert len(rebuilt.items) == len(original.items)
        assert rebuilt.items[0].path == original.items[0].path
        assert rebuilt.items[0].type == original.items[0].type
        assert rebuilt.items[0].value == original.items[0].value
        assert len(rebuilt.rules) == len(original.rules)
        assert rebuilt.rules[0].destination == original.rules[0].destination
        assert rebuilt.rules[0].query == original.rules[0].query
        assert rebuilt.rules[0].author == original.rules[0].author
        assert len(rebuilt.enrichments) == len(original.enrichments)
        assert rebuilt.enrichments[0].path == original.enrichments[0].path
        assert rebuilt.enrichments[0].annotations == original.enrichments[0].annotations
        assert len(rebuilt.tasks) == len(original.tasks)
        assert rebuilt.tasks[0].assignment == original.tasks[0].assignment
        assert rebuilt.tasks[0].summary == original.tasks[0].summary

    def test_random_case_model(self):
        """random_model_obj can generate a valid Case."""
        case = random_model_obj(Case)
        assert case.case_id is not None
        assert case.title is not None

    def test_case_visible_defaults_to_true(self):
        """Case.visible is True by default."""
        case = Case(
            {
                "case_id": "case-vis",
                "title": "Visibility Default",
                "summary": "S",
                "overview": "O",
                "escalation": "low",
            }
        )

        assert case.visible is True

    def test_case_visible_can_be_set_to_false(self):
        """Case.visible can be explicitly set to False."""
        case = Case(
            {
                "case_id": "case-hidden",
                "title": "Hidden Case",
                "summary": "S",
                "overview": "O",
                "escalation": "high",
                "visible": False,
            }
        )

        assert case.visible is False

    def test_case_visible_included_in_primitives(self):
        """visible field is present in as_primitives output for Case."""
        case = Case(
            {
                "case_id": "case-prim",
                "title": "T",
                "summary": "S",
                "overview": "O",
                "escalation": "medium",
            }
        )

        primitives = case.as_primitives()
        assert "visible" in primitives
        assert primitives["visible"] is True

    def test_case_date_fields(self):
        """Optional date fields can be set and parsed correctly."""
        case = Case(
            {
                "case_id": "case-dates",
                "title": "Dates",
                "summary": "S",
                "overview": "O",
                "escalation": "low",
                "start": "2025-01-01T00:00:00Z",
                "end": "2025-12-31T23:59:59Z",
            }
        )

        assert case.start is not None
        assert case.start.year == 2025
        assert case.start.month == 1
        assert case.start.day == 1
        assert case.end is not None
        assert case.end.year == 2025
        assert case.end.month == 12
        assert case.end.day == 31

    def test_case_invalid_date_raises(self):
        """Invalid date format raises HowlerValueError."""
        with pytest.raises(HowlerValueError):
            Case(
                {
                    "case_id": "case-bad-date",
                    "title": "T",
                    "summary": "S",
                    "overview": "O",
                    "escalation": "low",
                    "start": "not-a-date",
                }
            )

    def test_case_with_log_entries(self):
        """Case stores CaseLog entries and includes them in as_primitives."""
        case = Case(
            {
                "case_id": "case-log",
                "title": "T",
                "summary": "S",
                "overview": "O",
                "escalation": "low",
                "log": [
                    {"timestamp": "NOW", "explanation": "Case created", "user": "admin"},
                ],
            }
        )

        assert len(case.log) == 1
        assert case.log[0].user == "admin"
        assert case.log[0].explanation == "Case created"

        primitives = case.as_primitives()
        assert "log" in primitives
        assert len(primitives["log"]) == 1
        assert primitives["log"][0]["user"] == "admin"
