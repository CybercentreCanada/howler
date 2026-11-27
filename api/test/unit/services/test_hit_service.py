from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from howler.common.exceptions import InvalidDataException
from howler.helper import hit as hit_helper
from howler.models.hit import Hit
from howler.services import hit_service


@pytest.fixture()
def hit_datastore(monkeypatch):
    storage = MagicMock()
    storage.hit.model_class = Hit
    monkeypatch.setattr(hit_service, "datastore", lambda: storage)
    return storage


def test_assess_hit_maps_the_requested_assessment_to_workflow_updates():
    updates = {operation.key: operation.value for operation in hit_helper.assess_hit("attempt")}

    assert updates["howler.assessment"] == "attempt"
    assert updates["howler.escalation"] == "evidence"
    assert updates["howler.status"] == "resolved"


def test_assess_hit_rejects_unknown_assessments():
    with pytest.raises(InvalidDataException, match="Must set assessment"):
        hit_helper.assess_hit("unknown")


def test_convert_hit_builds_a_hit_with_workflow_defaults(hit_datastore):
    hit, warnings = hit_service.convert_hit(
        {"howler": {"analytic": "Example", "assessment": "ambiguous", "hash": "ab" * 32}}, unique=False
    )

    assert isinstance(hit, Hit)
    assert cast(Any, hit).event.id == cast(Any, hit).howler.id
    assert cast(Any, hit).howler.escalation == "miss"
    assert cast(Any, hit).howler.status == "resolved"
    assert any("assessment ambiguous" in warning for warning in warnings)
