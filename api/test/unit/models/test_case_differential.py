"""Differential tests for the Case model and its cross-field validators."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from howler.models import model_registry
from howler.models.case import Case as NewCase
from howler.models.case import CaseItem as NewCaseItem
from howler.models.case import CaseLog as NewCaseLog
from howler.models.case import CaseRule as NewCaseRule
from test.unit.models._goldens import primitive_golden

CASE_DATA = {"case_id": "c-1", "title": "Case Title", "summary": "A summary"}


def test_case_primitives_and_index_match_legacy() -> None:
    """A minimal case produces identical stored primitives (aside from "NOW" timestamps)."""
    new = NewCase.model_validate(CASE_DATA)

    new_primitives = new.as_primitives()
    new_primitives.pop("created", None)

    assert new_primitives == primitive_golden("case")
    assert new_primitives["__index"] == "case"


@pytest.mark.parametrize(
    "rule_data",
    [
        {"timeframe": None, "expire_after_resolved": True},
        {"timeframe": 0, "expire_after_resolved": False},
        {"timeframe": -1, "expire_after_resolved": False},
        {"timeframe": True, "expire_after_resolved": False},
    ],
)
def test_case_rule_rejects_invalid_timeframe_like_legacy(rule_data: dict) -> None:
    """``expire_after_resolved=True`` with no timeframe, and non-positive timeframes, are invalid."""
    base = {"rule_id": "r-1", "destination": "d", "query": "q", "author": "a", **rule_data}

    with pytest.raises(ValidationError):
        NewCaseRule.model_validate(base)


def test_case_rule_accepts_valid_timeframe_and_defaults_match_legacy() -> None:
    """A valid rule (or one omitting timeframe/expire_after_resolved) matches the legacy ODM."""
    base = {"rule_id": "r-2", "destination": "d", "query": "q", "author": "a"}
    new = NewCaseRule.model_validate(base)

    new_primitives = new.as_primitives()
    new_primitives.pop("created_at", None)
    assert new_primitives == primitive_golden("case_rule.defaults")

    valid_with_timeframe = {**base, "timeframe": 30, "expire_after_resolved": True}
    new2 = NewCaseRule.model_validate(valid_with_timeframe)
    assert new2.timeframe == 30


def test_case_item_folder_value_defaults_to_name_like_legacy() -> None:
    """Folder items copy ``name`` into ``value``, matching the legacy ``CaseItem.__init__``."""
    data = {"id": "i-1", "type": "folder", "name": "My Folder"}
    new = NewCaseItem.model_validate(data)

    assert new.value == "My Folder"
    assert new.as_primitives() == primitive_golden("case_item.folder")


def test_case_item_rejects_non_root_case_items_like_legacy() -> None:
    """A ``case``-type item with a non-null parent is rejected by both implementations."""
    data = {"id": "i-2", "type": "case", "parent": "some-parent", "value": "x"}

    with pytest.raises(ValidationError):
        NewCaseItem.model_validate(data)


def test_case_log_requires_explanation_or_full_details_like_legacy() -> None:
    """``CaseLog`` requires either ``explanation`` or the full set of change-tracking fields."""
    incomplete = {"user": "me"}
    with pytest.raises(ValidationError):
        NewCaseLog.model_validate(incomplete)

    complete = {"timestamp": "2024-01-01T00:00:00.000000Z", "new_value": "x", "user": "me"}
    new = NewCaseLog.model_validate(complete)
    assert new.as_primitives() == primitive_golden("case_log.complete")

    with_explanation = {"timestamp": "2024-01-01T00:00:00.000000Z", "user": "me", "explanation": "manual change"}
    new2 = NewCaseLog.model_validate(with_explanation)
    assert new2.as_primitives() == primitive_golden("case_log.explanation")


def test_case_mapping_list_of_compound_is_object() -> None:
    """List-of-compound case fields (items/rules/tasks) map to ``object``, not ``nested``."""
    mapping = model_registry.mapping(NewCase)
    for field in ("items", "rules", "tasks", "enrichments", "log"):
        assert mapping["properties"][field]["type"] == "object"
