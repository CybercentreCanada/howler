import json
import math
from unittest.mock import MagicMock, patch

import pytest

from howler.datastore.bulk import ElasticBulkPlan
from howler.datastore.collection import ESCollection
from howler.odm.models.case import Case, CaseItem


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


def test_collection_bulk_returns_item_failures_and_logs_them():
    operations = MagicMock()
    operations.get_plan_batches.return_value = ["bulk-operation"]
    collection = MagicMock()
    collection.with_retries.return_value = {
        "errors": True,
        "items": [
            {
                "update": {
                    "_index": "howler_case_hot",
                    "_id": "case-123",
                    "status": 409,
                    "error": {"type": "version_conflict_engine_exception", "reason": "document changed"},
                }
            }
        ],
    }

    with patch("howler.datastore.collection.logger") as mock_logger:
        result = ESCollection.bulk(collection, operations)

    assert not result
    assert result.failures == [
        {
            "operation": "update",
            "index": "howler_case_hot",
            "id": "case-123",
            "status": 409,
            "error": {"type": "version_conflict_engine_exception", "reason": "document changed"},
        }
    ]
    collection.with_retries.assert_called_once_with(
        collection.datastore.client.bulk,
        operations="bulk-operation",
        refresh=None,
    )
    mock_logger.error.assert_called_once_with(
        "Bulk plan failures: %s",
        [
            {
                "operation": "update",
                "index": "howler_case_hot",
                "id": "case-123",
                "status": 409,
                "error": {"type": "version_conflict_engine_exception", "reason": "document changed"},
            }
        ],
    )


def test_collection_bulk_preserves_failures_across_batches():
    operations = MagicMock()
    operations.get_plan_batches.return_value = ["successful-bulk", "failed-bulk"]
    collection = MagicMock()
    collection.with_retries.side_effect = [
        {"errors": False, "items": [{"update": {"status": 200}}]},
        {
            "errors": True,
            "items": [
                {"update": {"_id": "hit-1", "status": 409, "error": {"type": "conflict"}}},
                {"update": {"_id": "hit-2", "status": 500, "error": {"type": "failure"}}},
            ],
        },
    ]

    result = ESCollection.bulk(collection, operations)

    assert not result
    assert [failure["id"] for failure in result.failures] == ["hit-1", "hit-2"]
    assert len(result.responses) == 2


def test_update_by_query_translates_wait_for_refresh_to_true():
    collection = MagicMock()
    collection.create_scripts_from_operations.return_value = {"source": "ctx._source.field = params.value"}
    collection._update_async.return_value = {"updated": 1}

    result = ESCollection.update_by_query(
        collection,
        "howler.id:hit-123",
        [("SET", "howler.outline.summary", "Updated summary")],
        refresh="wait_for",
    )

    assert result == 1
    assert collection._update_async.call_args.kwargs["refresh"] == "true"


# ---------------------------------------------------------------------------
# add_update_operation() field scoping
# ---------------------------------------------------------------------------


def _make_case() -> Case:
    return Case(
        {
            "case_id": "case-001",
            "title": "Original Title",
            "summary": "Original Summary",
            "overview": "O",
            "escalation": "normal",
            "items": [CaseItem({"type": "hit", "value": "hit-1", "name": "hit-1"})],
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
