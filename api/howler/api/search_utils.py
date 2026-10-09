"""Shared helpers for safely selecting and projecting scroll search results."""

from collections.abc import Mapping
from typing import Any, cast

from howler.datastore.utils import expand_field_patterns, prune_to_paths
from howler.odm.base import BANNED_FIELDS


def select_safe_scroll_fields(
    search_collections: Mapping[str, Any], fl: Any
) -> tuple[list[str], dict[str, list[str]], bool]:
    """Build the Elasticsearch source projection and per-index stored-field allowlists."""
    if isinstance(fl, str):
        requested_fields = [value.strip() for value in fl.split(",") if value.strip()]
    elif isinstance(fl, list):
        requested_fields = [
            field.strip() for value in fl if isinstance(value, str) for field in value.split(",") if field.strip()
        ]
    else:
        requested_fields = []

    allowed_fields_by_index: dict[str, list[str]] = {}
    include_id = not requested_fields

    for index, search_collection in search_collections.items():
        safe_fields = [
            field_name
            for field_name, field in search_collection.stored_fields.items()
            if field.store and field_name not in BANNED_FIELDS
        ]

        if not requested_fields:
            selected_fields = safe_fields
        else:
            expanded_fields = expand_field_patterns(search_collection.model_class, requested_fields, preserve_all=True)
            selected_fields = (
                safe_fields if "*" in expanded_fields else [field for field in safe_fields if field in expanded_fields]
            )
            include_id = include_id or "*" in expanded_fields or "id" in expanded_fields

        allowed_fields_by_index[index] = selected_fields

    source_fields = list(dict.fromkeys(field for fields in allowed_fields_by_index.values() for field in fields))
    if include_id and "id" not in source_fields:
        source_fields.append("id")

    return source_fields, allowed_fields_by_index, include_id


def _remove_banned_scroll_fields(value: Any) -> Any:
    """Remove banned field names at every level of a scroll result."""
    if isinstance(value, dict):
        return {key: _remove_banned_scroll_fields(item) for key, item in value.items() if key not in BANNED_FIELDS}
    if isinstance(value, list):
        return [_remove_banned_scroll_fields(item) for item in value]
    return value


def prune_scroll_items(
    items: list[dict[str, Any]], allowed_fields_by_index: Mapping[str, list[str]], include_id: bool
) -> list[dict[str, Any]]:
    """Project scroll items to stored fields, applying the correct allowlist per index."""
    safe_items: list[dict[str, Any]] = []
    single_index = next(iter(allowed_fields_by_index)) if len(allowed_fields_by_index) == 1 else None

    for item in items:
        item_index = item.get("__index")
        if not isinstance(item_index, str):
            item_index = single_index
        selected_fields = allowed_fields_by_index.get(item_index, []) if item_index is not None else []

        item_id = item.get("id") if include_id else None
        source = _remove_banned_scroll_fields(
            {key: value for key, value in item.items() if key not in {"__index", "id"}}
        )
        safe_item = cast(dict[str, Any], prune_to_paths(source, set(selected_fields)))

        if include_id and item_id is not None:
            safe_item["id"] = item_id
        if "__index" in item:
            safe_item["__index"] = item["__index"]

        safe_items.append(safe_item)

    return safe_items
