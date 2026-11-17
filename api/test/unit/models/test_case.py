"""Validation and serialization behavior for Case documents and embedded case models."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from howler.models.case import Case, CaseEnrichment, CaseItem, CaseItemTypes, CaseLog, CaseRule, CaseTask
from howler.models.registry import model_registry
from howler.sample_data.randomizer import random_model_obj

CASE_DATA = {"case_id": "case-001", "title": "Incident", "summary": "Summary"}


class TestCaseLog:
    """Tests for the change-log model."""

    def test_log_with_explanation_allows_omitted_change_details(self) -> None:
        log = CaseLog.model_validate({"timestamp": "NOW", "explanation": "Case created", "user": "admin"})

        assert log.user == "admin"
        assert log.explanation == "Case created"
        assert log.key is None
        assert log.previous_value is None
        assert log.new_value is None

    def test_log_without_explanation_requires_complete_change_details(self) -> None:
        log = CaseLog.model_validate(
            {
                "timestamp": "NOW",
                "key": "escalation",
                "previous_value": "low",
                "new_value": "crisis",
                "user": "bob",
            }
        )
        assert log.new_value == "crisis"
        assert log.previous_value == "low"
        assert log.key == "escalation"
        primitives = log.as_primitives()
        assert primitives["user"] == "bob"
        assert primitives["new_value"] == "crisis"
        assert primitives["previous_value"] == "low"
        assert primitives["key"] == "escalation"

        for incomplete in ({"timestamp": "NOW", "user": "analyst"}, {"timestamp": "NOW", "new_value": "crisis"}):
            with pytest.raises(ValidationError):
                CaseLog.model_validate(incomplete)


class TestCaseItem:
    """Tests for case items, including path and visibility constraints."""

    def test_item_defaults_and_primitives(self) -> None:
        item = CaseItem.model_validate({"type": "hit", "value": "abc123"})

        assert item.type == "hit"
        assert item.value == "abc123"
        assert item.id
        assert item.parent is None
        assert item.visible is True
        primitives = item.as_primitives()
        assert primitives["id"] == item.id
        assert primitives["visible"] is True
        assert "parent" not in primitives

    def test_item_accepts_supported_types_and_rejects_unknown_types(self) -> None:
        for item_type in tuple(CaseItemTypes):
            data = (
                {"type": item_type.value, "name": "Folder"}
                if item_type is CaseItemTypes.FOLDER
                else {
                    "type": item_type.value,
                    "value": "item-value",
                }
            )
            assert CaseItem.model_validate(data).type == item_type.value

        with pytest.raises(ValidationError):
            CaseItem.model_validate({"type": "unknown", "value": "value"})

    def test_folder_value_uses_its_name_and_can_have_a_parent(self) -> None:
        item = CaseItem.model_validate({"type": "folder", "name": "Nested Folder", "parent": "parent-id"})
        assert item.value == "Nested Folder"
        assert item.parent == "parent-id"

    def test_case_item_must_be_root_level(self) -> None:
        with pytest.raises(ValidationError, match="root-level"):
            CaseItem.model_validate({"type": "case", "parent": "folder-id", "value": "case-1"})

        item = CaseItem.model_validate({"type": "case", "value": "case-1"})
        assert item.parent is None

    def test_item_requires_type_and_value(self) -> None:
        for data in ({"type": "hit"}, {"value": "hit-1"}):
            with pytest.raises(ValidationError):
                CaseItem.model_validate(data)

    def test_visibility_can_be_disabled(self) -> None:
        item = CaseItem.model_validate({"type": "hit", "value": "abc123", "visible": False})
        assert item.visible is False
        assert item.as_primitives()["visible"] is False


class TestCaseRule:
    """Tests for rule defaults and expiry validation."""

    BASE_RULE = {"destination": "/dest", "query": "*:*", "author": "analyst"}

    def test_rule_defaults_and_valid_timeframe(self) -> None:
        rule = CaseRule.model_validate(self.BASE_RULE)

        assert rule.destination == "/dest"
        assert rule.query == "*:*"
        assert rule.author == "analyst"
        assert rule.enabled is True
        assert rule.timeframe is None
        assert rule.rule_id
        assert rule.indexes == ["hit"]
        assert rule.as_primitives()["enabled"] is True
        assert rule.as_primitives()["indexes"] == ["hit"]

        configured = CaseRule.model_validate({**self.BASE_RULE, "enabled": False, "timeframe": 14})
        assert configured.enabled is False
        assert configured.timeframe == 14

    @pytest.mark.parametrize("timeframe", [0, -1, "7", 1.5, True, False])
    def test_timeframe_must_be_a_positive_integer(self, timeframe: object) -> None:
        with pytest.raises(ValidationError):
            CaseRule.model_validate({**self.BASE_RULE, "timeframe": timeframe})

    def test_expiry_after_resolution_requires_a_timeframe(self) -> None:
        with pytest.raises(ValidationError, match="expire after resolved"):
            CaseRule.model_validate({**self.BASE_RULE, "timeframe": None, "expire_after_resolved": True})

        rule = CaseRule.model_validate({**self.BASE_RULE, "timeframe": 30, "expire_after_resolved": True})
        assert rule.timeframe == 30
        assert rule.expire_after_resolved is True

    def test_rule_requires_destination_query_and_author(self) -> None:
        for data in ({"destination": "/dest"}, {"query": "*:*"}, {"destination": "/dest", "query": "*:*"}):
            with pytest.raises(ValidationError):
                CaseRule.model_validate(data)

    def test_random_rule_model_has_required_fields(self) -> None:
        for _ in range(10):
            try:
                rule = random_model_obj(CaseRule)
            except ValidationError:
                continue
            assert rule.destination
            assert rule.query
            assert rule.author
            assert rule.rule_id
            return
        pytest.fail("Could not generate a valid CaseRule in ten attempts")


class TestCaseTask:
    """Tests for tasks attached to case items."""

    def test_task_defaults_and_completion(self) -> None:
        task = CaseTask.model_validate(
            {"assignment": "analyst-team", "summary": "Review indicators", "item": "item-001"}
        )
        assert task.assignment == "analyst-team"
        assert task.summary == "Review indicators"
        assert task.item == "item-001"
        assert task.complete is False

        complete = CaseTask.model_validate(
            {"complete": True, "assignment": "soc", "summary": "Done", "item": "item-002"}
        )
        assert complete.complete is True

    def test_task_requires_summary(self) -> None:
        with pytest.raises(ValidationError):
            CaseTask.model_validate({"assignment": "soc"})


class TestCaseEnrichment:
    """Tests for enrichment annotations associated with a case item."""

    def test_enrichment_defaults_to_no_annotations(self) -> None:
        enrichment = CaseEnrichment.model_validate({"item": "item-001"})
        assert enrichment.item == "item-001"
        assert enrichment.annotations == []

    def test_enrichment_accepts_annotation_ids(self) -> None:
        enrichment = CaseEnrichment.model_validate({"item": "item-002", "annotations": ["ann-1", "ann-2"]})
        assert enrichment.annotations == ["ann-1", "ann-2"]


class TestCase:
    """Tests for Case document defaults, nested content, and round trips."""

    def test_case_defaults_and_required_fields(self) -> None:
        case = Case.model_validate(CASE_DATA)
        assert case.escalation == "normal"
        assert case.as_primitives()["escalation"] == "normal"
        assert isinstance(case.created, datetime)
        assert abs((case.created - datetime.now(timezone.utc)).total_seconds()) < 60
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

        for missing in ({"summary": "Summary"}, {"title": "Incident"}):
            with pytest.raises(ValidationError):
                Case.model_validate(missing)

    @pytest.mark.parametrize("escalation", ["normal", "focus", "crisis"])
    def test_valid_escalation_values(self, escalation: str) -> None:
        case = Case.model_validate({**CASE_DATA, "escalation": escalation})
        assert case.escalation == escalation
        assert case.as_primitives()["escalation"] == escalation

    def test_invalid_escalation_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="escalation"):
            Case.model_validate({**CASE_DATA, "escalation": "urgent"})

    def test_case_accepts_lists_and_nested_models(self) -> None:
        case = Case.model_validate(
            {
                **CASE_DATA,
                "targets": ["server-1", "server-2"],
                "threats": ["apt-29"],
                "indicators": ["ioc-hash"],
                "participants": ["analyst-1", "analyst-2"],
                "items": [
                    {"type": "event", "value": "event-1"},
                    {"type": "hit", "value": "hit-1"},
                ],
                "rules": [{"destination": "/critical", "query": "howler.score:>90", "author": "analyst"}],
                "tasks": [{"assignment": "soc", "summary": "Investigate", "item": "item-1"}],
                "enrichments": [{"item": "item-1", "annotations": ["ann-1"]}],
            }
        )

        assert case.targets == ["server-1", "server-2"]
        assert case.threats == ["apt-29"]
        assert [item.type for item in case.items] == ["event", "hit"]
        assert case.rules[0].query == "howler.score:>90"
        assert case.tasks[0].complete is False
        assert case.enrichments[0].annotations == ["ann-1"]

    def test_case_primitives_round_trip(self) -> None:
        case = Case.model_validate(
            {
                **CASE_DATA,
                "escalation": "focus",
                "targets": ["server-1"],
                "items": [{"type": "hit", "value": "hit-1"}],
                "rules": [{"destination": "/alerts", "query": "q", "author": "analyst"}],
                "enrichments": [{"item": "item-1", "annotations": ["ann-1"]}],
                "tasks": [{"assignment": "analyst", "summary": "Review", "item": "item-1"}],
            }
        )

        primitives = case.as_primitives()
        assert primitives["__index"] == "case"
        primitives.pop("__index")
        rebuilt = Case.model_validate(primitives)

        assert rebuilt.case_id == case.case_id
        assert rebuilt.title == case.title
        assert rebuilt.escalation == case.escalation
        assert rebuilt.targets == case.targets
        assert rebuilt.items[0].value == case.items[0].value
        assert rebuilt.items[0].id == case.items[0].id
        assert rebuilt.rules[0].query == case.rules[0].query
        assert rebuilt.enrichments[0].annotations == case.enrichments[0].annotations
        assert rebuilt.tasks[0].summary == case.tasks[0].summary

    def test_case_visibility_and_optional_dates(self) -> None:
        case = Case.model_validate(
            {
                **CASE_DATA,
                "visible": False,
                "start": "2025-01-01T00:00:00Z",
                "end": "2025-12-31T23:59:59Z",
            }
        )
        assert case.visible is False
        assert case.as_primitives()["visible"] is False
        assert case.start is not None and (case.start.year, case.start.month, case.start.day) == (2025, 1, 1)
        assert case.end is not None and (case.end.year, case.end.month, case.end.day) == (2025, 12, 31)

        with pytest.raises(ValidationError):
            Case.model_validate({**CASE_DATA, "start": "not-a-date"})

    def test_case_can_contain_log_entries(self) -> None:
        case = Case.model_validate(
            {**CASE_DATA, "log": [{"timestamp": "NOW", "explanation": "Case created", "user": "admin"}]}
        )
        assert len(case.log) == 1
        assert case.log[0].user == "admin"
        assert case.log[0].explanation == "Case created"
        assert case.as_primitives()["log"][0]["user"] == "admin"

    def test_random_case_model_has_required_content(self) -> None:
        for _ in range(10):
            try:
                case = random_model_obj(Case)
            except ValidationError:
                continue
            assert case.case_id
            assert case.title
            return
        pytest.fail("Could not generate a valid Case in ten attempts")


def test_case_compound_lists_map_as_objects() -> None:
    """Case's item-like arrays map to object properties rather than nested documents."""
    properties = model_registry.mapping(Case)["properties"]
    for field in ("items", "rules", "tasks", "enrichments", "log"):
        assert properties[field]["type"] == "object"
