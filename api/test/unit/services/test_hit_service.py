from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest

from howler.common.exceptions import HowlerValueError, InvalidDataException
from howler.datastore.collection import ESCollection
from howler.datastore.operations import OdmUpdateOperation
from howler.helper import hit as hit_helper
from howler.models import construct_partial, validate_field_value
from howler.models.hit import Hit
from howler.models.howler_data import Comment
from howler.services import hit_service


@pytest.fixture()
def hit_datastore(monkeypatch):
    storage = MagicMock()
    storage.hit.model_class = Hit
    monkeypatch.setattr(hit_service, "datastore", lambda: storage)
    return storage


def test_update_hit_uses_collection_operations_and_returns_saved_version():
    hit = construct_partial(Hit, {"howler": {"labels": {"generic": []}}})
    storage = MagicMock()
    storage.hit.get.return_value = hit, "new-version"
    storage.hit.get_if_exists.return_value = hit

    with patch.object(hit_service, "datastore", return_value=storage):
        updated, version = hit_service._update_hit(
            "hit-1",
            [
                OdmUpdateOperation(
                    ESCollection.UPDATE_SET,
                    "howler.labels.generic",
                    ["label"],
                    silent=True,
                )
            ],
            version="old-version",
        )

    assert updated is hit
    assert version == "new-version"
    storage.hit.update.assert_called_once()


def test_comment_update_values_are_converted_to_primitive_fields():
    comment = Comment.model_validate({"user": "user-1", "value": "Comment"})

    value = validate_field_value(Hit, "howler.comment", comment, list_item=True)

    assert value["id"] == comment.id
    assert value["user"] == "user-1"
    assert value["value"] == "Comment"


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


def test_convert_hit_reports_ignored_unknown_fields(hit_datastore):
    hit, warnings = hit_service.convert_hit(
        {"howler": {"analytic": "Example", "hash": "ab" * 32}, "unused": "value"},
        unique=False,
        ignore_extra_values=True,
    )

    assert isinstance(hit, Hit)
    assert warnings == ["unused is not currently used by howler."]
    assert "unused" not in cast(Any, hit).as_primitives()


def test_convert_hit_rejects_unknown_fields_by_default(hit_datastore):
    with pytest.raises(HowlerValueError, match="invalid parameters: unused"):
        hit_service.convert_hit({"howler": {"analytic": "Example", "hash": "ab" * 32}, "unused": "value"}, unique=False)
