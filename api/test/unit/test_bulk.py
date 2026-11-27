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


def test_location_resolution_targets_newest_for_writes_and_every_index_for_deletes():
    requests = []

    def locate(ids):
        requests.append(list(ids))
        return {key: ["test-000002", "test-000001"] for key in ids if key != "new"}

    plan = ElasticBulkPlan(["test"], document_locations=locate)
    plan.add_update_operation("a", {"name": "updated"})
    plan.add_delete_operation("a")
    plan.add_index_operation("new", {"name": "new"})
    plan.add_delete_operation("b", index="test-000001")

    plan.get_plan_data()
    headers = [json.loads(op[0]) for op in plan.operations]
    assert requests == [["a", "new"]]
    assert headers == [
        {"update": {"_index": "test-000002", "_id": "a"}},
        {"delete": {"_index": "test-000002", "_id": "a"}},
        {"delete": {"_index": "test-000001", "_id": "a"}},
        {"index": {"_index": "test", "_id": "new"}},
        {"delete": {"_index": "test-000001", "_id": "b"}},
    ]


def test_collection_bulk_returns_false_and_logs_errors():
    operations = MagicMock()
    operations.get_plan_batches.return_value = ["bulk-operation"]
    collection = MagicMock()
    bulk_error = {"type": "document_missing_exception", "reason": "document not found"}
    collection.with_retries.return_value = {
        "errors": True,
        "items": [
            {
                "delete": {
                    "_index": "test_index",
                    "_id": "record-123",
                    "status": 404,
                    "error": bulk_error,
                }
            }
        ],
    }

    with patch("howler.datastore.collection.logger") as mock_logger:
        result = ESCollection.bulk(collection, operations)

    assert result is False
    collection.with_retries.assert_called_once_with(
        collection.datastore.client.bulk,
        operations="bulk-operation",
        refresh=None,
    )
    mock_logger.error.assert_called_once_with(
        "Bulk %s failed for index %s document %s (status %s): %s",
        "delete",
        "test_index",
        "record-123",
        404,
        bulk_error,
    )


# ---------------------------------------------------------------------------
# add_update_operation() field scoping
# ---------------------------------------------------------------------------


def _make_case() -> Case:
    return Case(
        case_id="case-001",
        title="Original Title",
        summary="Original Summary",
        overview="O",
        escalation="normal",
        items=[CaseItem(id="item-1", type="hit", value="hit-1", name="hit-1")],
    )


def _get_update_body(plan: ElasticBulkPlan) -> dict:
    """Extract the `doc` body of the single queued update operation."""
    op = plan.operations[0]
    assert len(op) == 2
    header, body = op
    assert json.loads(header) == {"update": {"_index": "case", "_id": "case-001"}}
    return json.loads(body)["doc"]


@pytest.mark.parametrize(
    ("fields", "expected"),
    [
        (None, {"title": "Original Title", "summary": "Original Summary", "items": [{"id": "item-1"}]}),
        (["items"], {"items": [{"id": "item-1", "value": "hit-1", "name": "hit-1"}]}),
        (["items.*"], {"items": [{"type": "hit", "value": "hit-1", "name": "hit-1"}]}),
        (["items.type"], {"items": [{"type": "hit"}]}),
    ],
)
def test_add_update_operation_field_selection(fields, expected):
    plan = ElasticBulkPlan(indexes=["case"], model=Case)
    plan.add_update_operation("case-001", _make_case(), fields=fields)

    doc = _get_update_body(plan)
    assert all(doc[key] == value for key, value in expected.items() if key != "items")
    assert len(doc["items"]) == 1
    assert expected["items"][0].items() <= doc["items"][0].items()
    if fields:
        assert set(doc) == {"items"}
    if fields == ["items.type"]:
        assert doc["items"] == expected["items"]


def test_add_update_operation_validates_partial_dict_without_full_required_fields():
    plan = ElasticBulkPlan(indexes=["case"], model=Case)
    plan.add_update_operation(
        "case-001", {"items": [{"type": "hit"}], "unselected_unknown": object()}, fields=["items.type"]
    )
    assert _get_update_body(plan) == {"items": [{"type": "hit"}]}


def test_add_update_operation_fully_validates_exact_compound_field():
    plan = ElasticBulkPlan(indexes=["case"], model=Case)
    rule = {"destination": "/alerts", "query": "event.kind:alert", "author": "analyst", "expire_after_resolved": True}
    with pytest.raises(Exception):
        plan.add_update_operation("case-001", {"rules": [rule]}, fields=["rules"])
    plan.add_update_operation("case-001", {"rules": [{"enabled": False}]}, fields=["rules.enabled"])
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


@pytest.mark.parametrize(
    ("operation", "action", "index"),
    [
        ("insert", "create", "case"),
        ("index", "index", "case-000001"),
        ("upsert", "update", "case"),
    ],
)
def test_full_operation_helpers_preserve_exact_ndjson_actions_and_stored_id(operation, action, index):
    case = _make_case()
    plan = ElasticBulkPlan(indexes=["case"], model=Case)
    getattr(plan, f"add_{operation}_operation")("case-001", case, index=index)
    header, body = map(json.loads, plan.operations[0])
    assert header == {action: {"_index": index, "_id": "case-001"}}
    expected = {**case.as_primitives(hidden_fields=True), "id": "case-001"}
    assert body == ({"doc": expected, "doc_as_upsert": True} if operation == "upsert" else expected)
    assert plan.get_plan_data().endswith("\n")
