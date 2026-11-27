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


def _bulk_item(action: str, doc_id: str, result: str = "created", error: dict | None = None) -> dict:
    item: dict = {"_index": "test_index", "_id": doc_id, "status": 400 if error else 201, "result": result}
    if error:
        item["error"] = error
        del item["result"]
    return {action: item}


def _collection_with_responses(*responses) -> ESCollection:
    """An ESCollection whose bulk requests return (or raise) ``responses`` in order."""
    collection = object.__new__(ESCollection)
    collection.max_attempts = 1
    collection.datastore = MagicMock()
    collection.datastore.client.bulk.side_effect = list(responses)
    return collection


def test_collection_bulk_records_written_ids_per_chunk():
    """Only records each chunk actually wrote are reported; failed and no-op items are not."""
    plan = ElasticBulkPlan(indexes=["test_index"], model=None)
    for doc_id in ("a", "b", "c", "d"):
        plan.add_index_operation(doc_id, {"name": doc_id})

    collection = _collection_with_responses(
        {"errors": True, "items": [_bulk_item("index", "a"), _bulk_item("index", "b", error={"type": "x"})]},
        {"errors": False, "items": [_bulk_item("update", "c", result="noop"), _bulk_item("index", "d", "updated")]},
    )

    with patch.object(plan, "get_plan_batches", return_value=iter(["chunk-1", "chunk-2"])):
        assert ESCollection.bulk(collection, plan) is False

    assert plan.written_ids == ["a", "d"]


def test_collection_bulk_keeps_written_ids_when_a_later_chunk_raises():
    """Records written by earlier chunks stay reported when a later request fails outright."""
    from howler.common.exceptions import HowlerRuntimeError

    plan = ElasticBulkPlan(indexes=["test_index"], model=None)
    collection = _collection_with_responses(
        {"errors": False, "items": [_bulk_item("index", "a"), _bulk_item("index", "b")]},
        HowlerRuntimeError("Maximum of 1 retries reached. Aborting ES connection"),
    )

    with patch.object(plan, "get_plan_batches", return_value=iter(["chunk-1", "chunk-2"])):
        with pytest.raises(HowlerRuntimeError):
            ESCollection.bulk(collection, plan)

    assert plan.written_ids == ["a", "b"]


def test_collection_bulk_resets_written_ids_and_reports_each_record_once():
    """Each run starts fresh, and a record written to several indexes is reported once."""
    plan = ElasticBulkPlan(indexes=["test_index"], model=None)
    plan.written_ids = ["stale"]
    collection = _collection_with_responses(
        {"errors": False, "items": [_bulk_item("update", "a", "updated"), _bulk_item("update", "a", "updated")]},
    )

    with patch.object(plan, "get_plan_batches", return_value=iter(["chunk-1"])):
        assert ESCollection.bulk(collection, plan) is True

    assert plan.written_ids == ["a"]


def test_new_bulk_plan_has_no_written_ids():
    assert ElasticBulkPlan(indexes=["test_index"], model=None).written_ids == []


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
