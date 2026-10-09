"""Tests for shared safe scroll search projection helpers."""

from types import SimpleNamespace

from howler.api.search_utils import prune_scroll_items, select_safe_scroll_fields


def _search_collection(*stored_fields: str):
    return SimpleNamespace(
        model_class=None,
        stored_fields={field: SimpleNamespace(store=True) for field in stored_fields},
    )


def test_scroll_projection_keeps_requested_fields_inside_compound_lists():
    collection = _search_collection("name", "action.operations.operation_id")
    collection.stored_fields["not_stored"] = SimpleNamespace(store=False)
    collections = {
        "hit": collection,
    }
    source_fields, allowed_fields, include_id = select_safe_scroll_fields(
        collections, ["name", "action.operations.operation_id", "not_stored"]
    )

    assert source_fields == ["name", "action.operations.operation_id"]
    assert allowed_fields == {"hit": ["name", "action.operations.operation_id"]}
    assert include_id is False

    items = [
        {
            "id": "hit-id",
            "__index": "hit",
            "name": "allowed",
            "not_stored": "filtered",
            "action": {
                "operations": [
                    {"operation_id": "add_label", "data_json": "filtered"},
                    {"operation_id": "promote", "data_json": "filtered"},
                ]
            },
        }
    ]

    assert prune_scroll_items(items, allowed_fields, include_id) == [
        {
            "name": "allowed",
            "action": {"operations": [{"operation_id": "add_label"}, {"operation_id": "promote"}]},
            "__index": "hit",
        }
    ]


def test_scroll_projection_uses_the_matching_index_allowlist():
    collections = {
        "hit": _search_collection("shared", "hit_only"),
        "user": _search_collection("shared", "user_only"),
    }
    source_fields, allowed_fields, include_id = select_safe_scroll_fields(
        collections, ["shared", "hit_only", "user_only"]
    )

    assert source_fields == ["shared", "hit_only", "user_only"]
    assert allowed_fields == {"hit": ["shared", "hit_only"], "user": ["shared", "user_only"]}
    assert include_id is False

    items = [
        {"__index": "hit", "shared": "hit-shared", "hit_only": "allowed", "user_only": "filtered"},
        {"__index": "user", "shared": "user-shared", "hit_only": "filtered", "user_only": "allowed"},
    ]

    assert prune_scroll_items(items, allowed_fields, include_id) == [
        {"shared": "hit-shared", "hit_only": "allowed", "__index": "hit"},
        {"shared": "user-shared", "user_only": "allowed", "__index": "user"},
    ]


def test_scroll_projection_drops_items_with_an_unmapped_index():
    """An item must not inherit another index's allowlist when its index is unknown."""
    items = [{"__index": "hit", "user_only": "must not leak"}]

    assert prune_scroll_items(items, {"user": ["user_only"]}, include_id=False) == [{"__index": "hit"}]


def test_scroll_projection_includes_document_ids_by_default():
    source_fields, allowed_fields, include_id = select_safe_scroll_fields({"hit": _search_collection("name")}, None)

    assert source_fields == ["name", "id"]
    assert allowed_fields == {"hit": ["name"]}
    assert include_id is True
