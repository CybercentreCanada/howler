"""Shared helpers for building field-scoped Elasticsearch operations from ODM models."""

from __future__ import annotations

import re
from collections.abc import Mapping as ABCMapping
from fnmatch import fnmatchcase
from typing import TYPE_CHECKING, Any, Iterable, Optional

from howler import odm
from howler.datastore.exceptions import SearchException
from howler.odm.base import BANNED_FIELDS, _Field

if TYPE_CHECKING:
    from howler.datastore.collection import ESCollection


def expand_field_patterns(
    model: Optional[type[odm.Model]], patterns: Iterable[str], preserve_all: bool = False
) -> set[str]:
    """Expand `*`-wildcard field patterns against a model's known dotted field paths.

    Entries without a `*` are kept as-is (even if the model doesn't recognize them, so
    synthetic keys like `__non_doc_raw__` still work). Without a model, patterns can't be
    expanded and are kept literally.
    """
    if model is None:
        return set(patterns)

    known_paths = list(model.flat_fields().keys())
    expanded: set[str] = set()
    for pattern in patterns:
        if "*" not in pattern:
            expanded.add(pattern)
            continue

        if pattern == "*" and preserve_all:
            expanded.add(pattern)
            continue

        regex = re.compile("^" + re.escape(pattern).replace(r"\*", ".*") + "$")
        matches = [path for path in known_paths if regex.match(path)]
        expanded.update(matches)
    return expanded


def prune_to_paths(value, allowed: set[str], prefix: str = ""):
    """Recursively keep only the parts of `value` selected by dotted paths in `allowed`.

    A key is kept wholesale (subtree included as-is) if its own path is in `allowed`;
    otherwise it's kept and recursed into if some allowed path starts with it, so
    e.g. `allowed={"items.type"}` prunes each entry of a list field named `items` down
    to just its `type` subfield.
    """
    if isinstance(value, dict):
        result = {}
        for key, sub_value in value.items():
            cur_path = f"{prefix}.{key}" if prefix else key
            if cur_path in allowed:
                result[key] = sub_value
            elif isinstance(sub_value, (dict, list)) and any(path.startswith(f"{cur_path}.") for path in allowed):
                result[key] = prune_to_paths(sub_value, allowed, cur_path)
        return result

    if isinstance(value, list):
        return [prune_to_paths(entry, allowed, prefix) for entry in value]

    return value


def normalize_field_list(fields: Any) -> list[str]:
    """Normalize a search field selection into comma-separated field names."""
    if fields is None:
        return []

    if isinstance(fields, str):
        entries = [fields]
    elif isinstance(fields, list) and all(isinstance(entry, str) for entry in fields):
        entries = fields
    else:
        raise SearchException("Field list must be a string or a list of strings.")

    return [field.strip() for entry in entries for field in entry.split(",") if field.strip()]


def field_paths_with_parents(field_names: Iterable[str]) -> set[str]:
    """Return field paths plus their compound-object parents."""
    paths = set(field_names)
    for field_name in paths.copy():
        parts = field_name.split(".")
        paths.update(".".join(parts[:depth]) for depth in range(1, len(parts)))
    return paths


def stored_field_paths(fields: ABCMapping[str, _Field]) -> set[str]:
    """Return stored, non-internal source paths from ODM field metadata."""
    return {name for name, field in fields.items() if field.store and name not in BANNED_FIELDS}


def _field_status(collection: ESCollection, path: str) -> bool | None:
    """Return whether a declared field, compound parent, or Mapping child is stored."""
    fields = collection.model_class.flat_fields() if collection.model_class else collection.stored_fields
    matches = [
        field
        for name, field in fields.items()
        if name == path
        or name.startswith(f"{path}.")
        or (isinstance(field, odm.Mapping) and path.startswith(f"{name}."))
    ]
    return any(field.store for field in matches) if matches else None


def _select_collection_fields(collection: ESCollection, requested_fields: list[str]) -> list[str]:
    fields = collection.stored_fields
    stored_names = stored_field_paths(fields) - {"id", "__index"}
    mapping_names = {name for name in stored_names if isinstance(fields[name], odm.Mapping)}
    selected: set[str] = set()

    def add_path(path: str) -> None:
        if path in stored_names:
            selected.add(path)
            return

        if any(name.startswith(f"{path}.") for name in stored_names):
            selected.update(name for name in stored_names if name.startswith(f"{path}."))
            return

        # Dynamic mapping keys are absent from the model's flat fields, but are still
        # addressable as stored source paths below a stored Mapping field.
        if any(path.startswith(f"{name}.") for name in mapping_names):
            selected.add(path)

    if not requested_fields or "*" in requested_fields:
        selected.update(stored_names)
    else:
        for requested in requested_fields:
            if "*" not in requested:
                add_path(requested)
                continue

            selected.update(name for name in stored_names if fnmatchcase(name, requested))
            # Mapping keys are dynamic. Retain their scoped patterns for Elasticsearch
            # source filtering and resolve them against the actual response when projecting.
            prefix = requested.split("*", 1)[0]
            for name in mapping_names:
                if requested.startswith(f"{name}."):
                    selected.add(requested)
                elif name.startswith(prefix):
                    # A wildcard may span the Mapping's root (e.g. *.team).
                    # Fetch that stored Mapping and intersect it with the original
                    # selector during projection, never with another index's schema.
                    selected.add(name)

    ordered_fields = [name for name in fields if name in selected]
    ordered_fields.extend(dict.fromkeys(name for name in requested_fields if name in selected and name not in fields))
    return ordered_fields


def _validate_explicit_fields(collections: ABCMapping[str, ESCollection], requested_fields: list[str]) -> None:
    """Reject explicitly declared non-stored fields unless another requested index stores them."""
    for requested in requested_fields:
        if "*" in requested or requested in {"id", "__index"}:
            continue
        if requested in BANNED_FIELDS:
            raise SearchException(f"Field '{requested}' is not stored in any requested index.")

        statuses = [_field_status(collection, requested) for collection in collections.values()]
        if any(status is True for status in statuses):
            continue
        if any(status is False for status in statuses):
            raise SearchException(f"Field '{requested}' is not stored in any requested index.")


def select_stored_fields(
    collections: ABCMapping[str, ESCollection],
    fields: Any,
) -> tuple[list[str], dict[str, list[str]], bool]:
    """Select only stored source paths and build a per-index output allowlist.

    Compound parents expand to their stored descendants. A descendant of a stored
    Mapping is accepted as an explicit dynamic source path without widening it to
    the whole mapping. The synthetic document ID is tracked separately from source
    projection because it is supplied by Elasticsearch hit metadata.
    """
    requested_fields = normalize_field_list(fields)
    _validate_explicit_fields(collections, requested_fields)
    fields_by_index = {
        index: _select_collection_fields(collection, requested_fields) for index, collection in collections.items()
    }
    include_id = any(fnmatchcase("id", field) for field in requested_fields)

    source_fields = list(dict.fromkeys(field for paths in fields_by_index.values() for field in paths))
    return source_fields, fields_by_index, include_id


def _remove_banned_fields(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _remove_banned_fields(item) for key, item in value.items() if key not in BANNED_FIELDS}

    if isinstance(value, list):
        return [_remove_banned_fields(item) for item in value]

    return value


def _matching_source_paths(
    value: Any, stored_patterns: list[str], requested_patterns: list[str], prefix: str = ""
) -> set[str]:
    """Intersect requested wildcards with this index's stored scopes using concrete source paths."""
    paths: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else key
            stored = any(
                path == pattern or path.startswith(f"{pattern}.") or ("*" in pattern and fnmatchcase(path, pattern))
                for pattern in stored_patterns
            )
            requested = any(
                path == pattern or path.startswith(f"{pattern}.") or fnmatchcase(path, pattern)
                for pattern in requested_patterns
            )
            if stored and requested:
                paths.add(path)
            else:
                paths.update(_matching_source_paths(item, stored_patterns, requested_patterns, path))
    elif isinstance(value, list):
        for item in value:
            paths.update(_matching_source_paths(item, stored_patterns, requested_patterns, prefix))
    return paths


def project_stored_fields(
    items: list[dict[str, Any]],
    allowed_fields_by_index: ABCMapping[str, list[str]],
    include_id: bool,
    *,
    fields: str | list[str] | None,
) -> list[dict[str, Any]]:
    """Project items to stored fields, intersecting Mapping scopes with the original field request."""
    safe_items: list[dict[str, Any]] = []
    default_fields = next(iter(allowed_fields_by_index.values())) if len(allowed_fields_by_index) == 1 else []
    requested_fields = normalize_field_list(fields)

    for item in items:
        item_index = item.get("__index")
        if isinstance(item_index, str):
            selected_fields = allowed_fields_by_index.get(item_index, [])
        else:
            selected_fields = default_fields

        source = {key: value for key, value in item.items() if key not in {"__index", "id"}}
        selected_paths = (
            _matching_source_paths(source, selected_fields, requested_fields)
            if any("*" in field for field in requested_fields)
            else set(selected_fields)
        )
        safe_item = _remove_banned_fields(prune_to_paths(source, selected_paths))

        if include_id and item.get("id") is not None:
            safe_item["id"] = item["id"]
        if "__index" in item:
            safe_item["__index"] = item["__index"]

        safe_items.append(safe_item)

    return safe_items
