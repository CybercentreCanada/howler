import json
import math
from unittest.mock import MagicMock, patch

import pytest

from howler.datastore.bulk import ElasticBulkPlan
from howler.datastore.collection import ESCollection
from howler.models import construct_partial
from howler.models.action import Action
from howler.models.case import Case, CaseItem


@pytest.fixture(scope="module")
def operations():
    return [
        ("DELETE", (1,)),
        ("INSERT", (2, {"name": "test"})),
        ("UPDATE", (3, {"name": "updated"})),
        ("DELETE", (4,)),
        ("INSERT", (5, {"name": "test"})),
        ("INSERT", (6, {"name": "test"})),
    ]


@pytest.fixture(scope="function")
def bulk_plan():
    return ElasticBulkPlan(indexes=["test_index"], model=None)


@pytest.mark.parametrize(
    "operation_length, batch_size",
    [(6, 2), (5, 2), (6, 10), (1, 1), (6, None)],
    ids=["divisible", "not_divisible", "larger_than_ops", "single_op", "no_batch_size"],
)
def test_get_plan_batches(bulk_plan, operations, operation_length, batch_size):
    for op, op_args in operations[:operation_length]:
        if op == "DELETE":
            bulk_plan.add_delete_operation(*op_args)
        elif op == "INSERT":
            bulk_plan.add_index_operation(*op_args)
        elif op == "UPDATE":
            bulk_plan.add_update_operation(*op_args)

    batches = list(bulk_plan.get_plan_batches(batch_size=batch_size))

    assert len(batches) == math.ceil(operation_length / (batch_size or operation_length))
    assert "".join(batches) == bulk_plan.get_plan_data()


def test_collection_bulk_returns_false_and_logs_errors():
    operations = MagicMock()
    operations.get_plan_batches.return_value = ["bulk-operation"]
    collection = MagicMock()
    collection.with_retries.return_value = {"errors": {"delete": "document not found"}}

    with patch("howler.datastore.collection.logger") as mock_logger:
        result = ESCollection.bulk(collection, operations)

    assert result is False
    collection.with_retries.assert_called_once_with(
        collection.datastore.client.bulk,
        operations="bulk-operation",
        refresh=None,
    )
    mock_logger.error.assert_called_once_with("Errors on bulk plan: %s", {"delete": "document not found"})


# ---------------------------------------------------------------------------
# add_update_operation() field scoping
# ---------------------------------------------------------------------------


def _make_case() -> Case:
    return Case.model_validate(
        {
            "case_id": "case-001",
            "title": "Original Title",
            "summary": "Original Summary",
            "overview": "O",
            "escalation": "normal",
            "items": [CaseItem.model_validate({"id": "item-1", "type": "hit", "value": "hit-1", "name": "hit-1"})],
        }
    )


def _get_update_body(plan: ElasticBulkPlan) -> dict:
    """Extract the `doc` body of the single queued update operation."""
    op = plan.operations[0]
    assert len(op) == 2
    header, body = op
    assert json.loads(header) == {"update": {"_index": "case", "_id": "case-001"}}
    return json.loads(body)["doc"]


def test_add_update_operation_without_fields_keeps_everything():
    """Without a `fields` filter, the full serialized document is sent."""
    plan = ElasticBulkPlan(indexes=["case"], model=Case)
    plan.add_update_operation("case-001", _make_case())

    doc = _get_update_body(plan)
    assert doc["title"] == "Original Title"
    assert doc["summary"] == "Original Summary"
    assert len(doc["items"]) == 1


def test_add_update_operation_exact_field_keeps_whole_subtree():
    """An exact field name (no wildcard) keeps that field's entire subtree."""
    plan = ElasticBulkPlan(indexes=["case"], model=Case)
    plan.add_update_operation("case-001", _make_case(), fields=["items"])

    doc = _get_update_body(plan)
    assert set(doc.keys()) == {"items"}
    assert doc["items"][0]["id"] == "item-1"
    assert doc["items"][0]["value"] == "hit-1"
    assert doc["items"][0]["name"] == "hit-1"


def test_add_update_operation_wildcard_field_expands_against_model():
    """A `*`-suffixed pattern expands to every subfield of that field via the model."""
    plan = ElasticBulkPlan(indexes=["case"], model=Case)
    plan.add_update_operation("case-001", _make_case(), fields=["items.*"])

    doc = _get_update_body(plan)
    assert set(doc.keys()) == {"items"}
    # Every subfield of the CaseItem is present, since "items.*" expands to all of them.
    assert doc["items"][0]["value"] == "hit-1"
    assert doc["items"][0]["type"] == "hit"
    assert doc["items"][0]["name"] == "hit-1"


def test_add_update_operation_specific_subfield_prunes_siblings():
    """A specific dotted subfield pattern keeps only that subfield in each list entry."""
    plan = ElasticBulkPlan(indexes=["case"], model=Case)
    plan.add_update_operation("case-001", _make_case(), fields=["items.type"])

    doc = _get_update_body(plan)
    assert set(doc.keys()) == {"items"}
    assert doc["items"][0] == {"type": "hit"}


def test_add_update_operation_drops_unselected_top_level_fields():
    """Fields not selected (e.g. title/summary) are absent from the update body entirely."""
    plan = ElasticBulkPlan(indexes=["case"], model=Case)
    plan.add_update_operation("case-001", _make_case(), fields=["items", "targets"])

    doc = _get_update_body(plan)
    assert "title" not in doc
    assert "summary" not in doc


def test_add_update_operation_validates_partial_dict_without_full_required_fields():
    """A partial merge validates selected registry fields without requiring a full Case."""
    plan = ElasticBulkPlan(indexes=["case"], model=Case)
    plan.add_update_operation(
        "case-001",
        {"items": [{"type": "hit"}], "unselected_unknown": object()},
        fields=["items.type"],
    )

    assert _get_update_body(plan) == {"items": [{"type": "hit"}]}


def test_add_update_operation_fully_validates_exact_compound_field():
    """Replacing a whole compound field runs nested model validators."""
    plan = ElasticBulkPlan(indexes=["case"], model=Case)

    with pytest.raises(Exception):
        plan.add_update_operation(
            "case-001",
            {
                "rules": [
                    {
                        "destination": "/alerts",
                        "query": "event.kind:alert",
                        "author": "analyst",
                        "expire_after_resolved": True,
                    }
                ]
            },
            fields=["rules"],
        )

    plan.add_update_operation(
        "case-001",
        {"rules": [{"enabled": False}]},
        fields=["rules.enabled"],
    )
    assert _get_update_body(plan) == {"rules": [{"enabled": False}]}


def test_add_index_operation_requires_a_complete_model():
    """Full index operations reject partial documents."""
    plan = ElasticBulkPlan(indexes=["case"], model=Case)

    with pytest.raises(Exception):
        plan.add_index_operation("case-001", {"title": "Incomplete"})


@pytest.mark.parametrize("operation", ["insert", "index", "upsert"])
def test_full_bulk_operations_reject_projected_model_instances(operation):
    """Projected models are valid only for partial updates, never full bulk writes."""
    projected = construct_partial(Action, {"name": "Projected"})
    plan = ElasticBulkPlan(indexes=["action"], model=Action)

    with pytest.raises(Exception):
        getattr(plan, f"add_{operation}_operation")("action-1", projected)

    assert plan.empty


def test_full_operation_helpers_preserve_exact_ndjson_actions_and_stored_id():
    """Create/index/upsert helpers retain their public bulk action and body shapes."""
    case = _make_case()
    plan = ElasticBulkPlan(indexes=["case"], model=Case)

    plan.add_insert_operation("case-001", case)
    plan.add_index_operation("case-001", case, index="case-000001")
    plan.add_upsert_operation("case-001", case)

    create_header, create_body = plan.operations[0]  # pyright: ignore[reportAssignmentType]
    index_header, index_body = plan.operations[1]  # pyright: ignore[reportAssignmentType]
    upsert_header, upsert_body = plan.operations[2]  # pyright: ignore[reportAssignmentType]
    assert json.loads(create_header) == {"create": {"_index": "case", "_id": "case-001"}}
    assert json.loads(index_header) == {"index": {"_index": "case-000001", "_id": "case-001"}}
    assert json.loads(upsert_header) == {"update": {"_index": "case", "_id": "case-001"}}
    assert json.loads(create_body)["id"] == "case-001"
    assert json.loads(index_body)["id"] == "case-001"
    assert json.loads(upsert_body) == {
        "doc": {**json.loads(create_body)},
        "doc_as_upsert": True,
    }
    assert plan.get_plan_data().endswith("\n")
