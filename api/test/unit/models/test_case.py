import pytest

from howler.models import HowlerModelValidationError, model_registry
from howler.models.case import Case, CaseEnrichment, CaseItem, CaseItemTypes, CaseLog, CaseRule, CaseTask
from howler.sample_data.randomizer import random_model_obj

CASE_DATA = {"case_id": "case-001", "title": "Incident", "summary": "Summary"}
RULE_DATA = {"destination": "/dest", "query": "*:*", "author": "analyst"}


def test_log_explanation_or_change_details():
    log = CaseLog.model_validate({"timestamp": "NOW", "explanation": "Created", "user": "admin"})
    assert log.key is None and log.previous_value is None and log.new_value is None
    log = CaseLog.model_validate({"timestamp": "NOW", "key": "status", "new_value": "open", "user": "admin"})
    assert log.as_primitives()["new_value"] == "open"
    for incomplete in ({"timestamp": "NOW", "user": "analyst"}, {"timestamp": "NOW", "new_value": "open"}):
        with pytest.raises(HowlerModelValidationError):
            CaseLog.model_validate(incomplete)


def test_item_types_defaults_and_folder_value():
    item = CaseItem.model_validate({"type": "hit", "value": "abc123", "visible": False})
    assert item.id and item.parent is None and item.as_primitives()["visible"] is False
    for item_type in CaseItemTypes:
        data = (
            {"type": item_type.value, "name": "Folder"}
            if item_type is CaseItemTypes.FOLDER
            else {"type": item_type.value, "value": "item-value"}
        )
        assert CaseItem.model_validate(data).type == item_type.value
    folder = CaseItem.model_validate({"type": "folder", "name": "Folder", "parent": "parent-id"})
    assert folder.value == "Folder" and folder.parent == "parent-id"
    for data in ({"type": "unknown", "value": "value"}, {"type": "hit"}, {"value": "hit-1"}):
        with pytest.raises(HowlerModelValidationError):
            CaseItem.model_validate(data)


@pytest.mark.parametrize("timeframe", [0, -1, "7", 1.5, True, False])
def test_rule_timeframe_must_be_a_positive_integer(timeframe):
    with pytest.raises(HowlerModelValidationError):
        CaseRule.model_validate({**RULE_DATA, "timeframe": timeframe})


def test_rule_defaults_and_expiry():
    rule = CaseRule.model_validate(RULE_DATA)
    assert rule.rule_id and rule.enabled and rule.timeframe is None and rule.indexes == ["hit"]
    assert CaseRule.model_validate({**RULE_DATA, "timeframe": 30, "expire_after_resolved": True}).expire_after_resolved


def test_case_nested_models_and_round_trip():
    case = Case.model_validate(
        {
            **CASE_DATA,
            "escalation": "focus",
            "targets": ["server-1"],
            "items": [{"type": "hit", "value": "hit-1"}],
            "rules": [RULE_DATA],
            "tasks": [{"summary": "Review", "item": "item-1"}],
            "enrichments": [{"item": "item-1", "annotations": ["ann-1"]}],
            "log": [{"timestamp": "NOW", "explanation": "Created", "user": "admin"}],
        }
    )
    primitives = case.as_primitives()
    assert primitives.pop("__index") == "case"
    assert Case.model_validate(primitives).as_primitives() == case.as_primitives()
    assert case.tasks[0].complete is False
    assert case.enrichments[0].annotations == ["ann-1"]
    assert case.log[0].user == "admin"


def test_case_defaults_and_validation():
    case = Case.model_validate(CASE_DATA)
    assert case.escalation == "normal" and case.created is not None
    assert case.updated is None and case.start is None and case.end is None
    for field in ("targets", "threats", "indicators", "participants", "items", "enrichments", "rules", "tasks"):
        assert getattr(case, field) == []
    for data in (
        {"summary": "Summary"},
        {"title": "Incident"},
        {**CASE_DATA, "escalation": "urgent"},
        {**CASE_DATA, "start": "not-a-date"},
    ):
        with pytest.raises(HowlerModelValidationError):
            Case.model_validate(data)
    assert CaseTask.model_validate({"summary": "Review"}).complete is False
    assert CaseEnrichment.model_validate({"item": "item-1"}).annotations == []


def test_random_case_rule_and_case_models():
    for model in (CaseRule, Case):
        for _ in range(10):
            try:
                instance = random_model_obj(model)
            except HowlerModelValidationError:
                continue
            required = ("rule_id", "destination", "query", "author") if model is CaseRule else ("case_id", "title")
            assert all(getattr(instance, name) for name in required)
            break
        else:
            pytest.fail(f"Could not generate {model.__name__} in ten attempts")


def test_case_compound_lists_map_as_objects():
    properties = model_registry.mapping(Case)["properties"]
    for field in ("items", "rules", "tasks", "enrichments", "log"):
        assert properties[field]["type"] == "object"
