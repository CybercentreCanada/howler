"""Hit ingestion uses the registered Pydantic document and preserves warnings."""

from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest

from howler.common.exceptions import HowlerValueError
from howler.models.hit import Hit
from howler.services import hit_service


@pytest.fixture
def hit_datastore():
    storage = MagicMock()
    storage.hit.model_class = Hit
    with patch.object(hit_service, "datastore", return_value=storage):
        yield storage


def test_convert_hit_builds_pydantic_hit_with_workflow_defaults(hit_datastore):
    hit, warnings = hit_service.convert_hit(
        {"howler": {"analytic": "Example", "assessment": "ambiguous", "hash": "ab" * 32}}, unique=False
    )

    assert isinstance(hit, Hit)
    assert cast(Any, hit).event.id == cast(Any, hit).howler.id
    assert cast(Any, hit).howler.escalation == "miss"
    assert cast(Any, hit).howler.status == "resolved"
    assert any("assessment ambiguous" in warning for warning in warnings)


def test_convert_hit_reports_ignored_unknown_fields(hit_datastore):
    hit, warnings = hit_service.convert_hit(
        {"howler": {"analytic": "Example", "hash": "ab" * 32}, "unused": "value"},
        unique=False,
        ignore_extra_values=True,
    )

    assert isinstance(hit, Hit)
    assert warnings == ["unused is not currently used by howler."]
    assert "unused" not in cast(Any, hit).as_primitives()


def test_convert_hit_rejects_unknown_fields_when_not_ignored(hit_datastore):
    with pytest.raises(HowlerValueError, match="invalid parameters: unused"):
        hit_service.convert_hit({"howler": {"analytic": "Example", "hash": "ab" * 32}, "unused": "value"}, unique=False)
