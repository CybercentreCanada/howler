from datetime import datetime, timezone

import pytest

from howler.common.exceptions import HowlerValueError
from howler.odm.models.case import CASE_ITEM_TYPES, Case, CaseEnrichment, CaseItem, CaseRule, CaseTask
from howler.odm.randomizer import random_model_obj


class TestCaseItem:
    """Tests for the CaseItem ODM model."""

    def test_create_case_item_minimal(self):
        """CaseItem can be created with required fields only."""
        item = CaseItem({"path": "/alerts", "type": "hit", "value": "abc123"})

        assert item.path == "/alerts"
        assert item.type == "hit"
        assert item.value == "abc123"
        assert item.id is None

    def test_create_case_item_with_id(self):
        """CaseItem can be created with an optional id."""
        item = CaseItem({"path": "/obs", "type": "observable", "value": "1.2.3.4", "id": "obs-001"})

        assert item.id == "obs-001"

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
            CaseItem({"type": "hit", "value": "v"})  # missing 'path'

        with pytest.raises(HowlerValueError):
            CaseItem({"path": "/test", "value": "v"})  # missing 'type'

    def test_case_item_as_primitives(self):
        """as_primitives returns a plain dict representation."""
        item = CaseItem({"path": "/alerts", "type": "hit", "value": "abc123", "id": "x"})
        primitives = item.as_primitives()

        assert isinstance(primitives, dict)
        assert primitives["path"] == "/alerts"
        assert primitives["type"] == "hit"
        assert primitives["value"] == "abc123"
        assert primitives["id"] == "x"


class TestCaseRule:
    """Tests for the CaseRule ODM model."""

    def test_create_case_rule(self):
        """CaseRule can be created with destination and query."""
        rule = CaseRule({"destination": "/alerts/critical", "query": "howler.score:>80"})

        assert rule.destination == "/alerts/critical"
        assert rule.query == "howler.score:>80"

    def test_case_rule_as_primitives(self):
        """as_primitives returns expected dict."""
        rule = CaseRule({"destination": "/dest", "query": "*:*"})
        primitives = rule.as_primitives()

        assert primitives["destination"] == "/dest"
        assert primitives["query"] == "*:*"

    def test_case_rule_missing_required_field(self):
        """CaseRule raises HowlerValueError when a required field is missing."""
        with pytest.raises(HowlerValueError):
            CaseRule({"destination": "/dest"})  # missing 'query'

        with pytest.raises(HowlerValueError):
            CaseRule({"query": "*:*"})  # missing 'destination'


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
                    # missing 'case_id'
                    "title": "T",
                    "summary": "S",
                    "overview": "O",
                    "escalation": "high",
                }
            )

        with pytest.raises(HowlerValueError):
            Case(
                {
                    "case_id": "case-x",
                    # missing 'title'
                    "summary": "S",
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
                    {"destination": "/critical", "query": "howler.score:>90"},
                ],
            }
        )

        assert len(case.rules) == 1
        assert case.rules[0].query == "howler.score:>90"

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
                "rules": [{"destination": "/b", "query": "q"}],
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
