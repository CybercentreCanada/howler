from collections.abc import Iterator, Mapping
from typing import Any, AnyStr, Optional, cast, get_args, get_origin
from typing import Mapping as _Mapping

from pydantic import BaseModel


def strip_nulls(d: Any):
    """Remove null values from a dict"""
    if isinstance(d, dict):
        return {k: strip_nulls(v) for k, v in d.items() if v is not None}
    else:
        return d


def remove_path(value: Any, path: str) -> None:
    """Remove a dot-delimited path from nested dictionaries, including list items."""
    keys = path.split(".")

    def remove(node: Any, remaining: list[str]) -> None:
        if isinstance(node, list):
            for item in node:
                remove(item, remaining)
            return
        if not isinstance(node, dict) or not remaining:
            return
        if len(remaining) == 1:
            node.pop(remaining[0], None)
            return
        remove(node.get(remaining[0]), remaining[1:])

    remove(value, keys)


def recursive_update(
    d: Optional[dict[str, Any]],
    u: Optional[_Mapping[str, Any]],
    stop_keys: list[AnyStr] = [],
    allow_recursion: bool = True,
) -> dict[str, Any]:
    "Recursively update a dict with another value"
    if d is None:
        return cast(dict, u or {})

    if u is None:
        return d

    for k, v in u.items():
        if isinstance(v, Mapping) and allow_recursion:
            d[k] = recursive_update(d.get(k, {}), v, stop_keys=stop_keys, allow_recursion=k not in stop_keys)
        else:
            d[k] = v

    return d


def get_recursive_delta(
    d1: Optional[_Mapping[str, Any]],
    d2: Optional[_Mapping[str, Any]],
    stop_keys: list[AnyStr] = [],
    allow_recursion: bool = True,
) -> Optional[dict[str, Any]]:
    "Get the recursive difference between two objects"
    if d1 is None:
        return cast(dict, d2)

    if d2 is None:
        return cast(dict, d1)

    out = {}
    for k1, v1 in d1.items():
        if isinstance(v1, Mapping) and allow_recursion:
            internal = get_recursive_delta(
                v1,
                d2.get(k1, {}),
                stop_keys=stop_keys,
                allow_recursion=k1 not in stop_keys,
            )
            if internal:
                out[k1] = internal
        else:
            if k1 in d2:
                v2 = d2[k1]
                if v1 != v2:
                    out[k1] = v2

    for k2, v2 in d2.items():
        if k2 not in d1:
            out[k2] = v2

    return out


def flatten(
    data: _Mapping,
    parent_key: Optional[str] = None,
    odm: Optional[type[BaseModel]] = None,
    *,
    preserve_empty: bool = True,
) -> dict[str, Any]:
    """Flatten a nested dict.

    Args:
        data: The mapping to flatten
        parent_key: Optional parent key for nested flattening
        odm: Optional ODM model for field validation
        preserve_empty: Keep empty dictionaries instead of flattening them away

    Returns:
        Flattened dictionary with dot-notation keys
    """
    # Pre-compute ODM valid keys if provided
    valid_keys_set: set[str] | None = None
    if odm:
        from howler.models.registry import model_registry

        valid_keys_set = set(model_registry.flat_fields(odm))

    def _flatten_recursive(mapping: _Mapping, prefix: str = "") -> dict[str, Any]:
        """Inner recursive function for flattening."""
        result = {}

        for key, value in mapping.items():
            current_key = f"{prefix}.{key}" if prefix else key

            if isinstance(value, dict) and (value or not preserve_empty):
                # ODM validation check
                if valid_keys_set and not any(valid_key.startswith(f"{current_key}.") for valid_key in valid_keys_set):
                    result[current_key] = value
                else:
                    # Recursively flatten and merge
                    result.update(_flatten_recursive(value, current_key))
            else:
                result[current_key] = value

        return result

    flattened = _flatten_recursive(data, parent_key or "")
    return flattened


def flatten_deep(data: _Mapping) -> dict[str, Any]:
    "Aggressively and completely flatten an object."
    partially_flattened = flatten(data)

    final: dict[str, Any] = {}
    for key, value in partially_flattened.items():
        if not isinstance(value, list):
            final[key] = value
        elif not any(isinstance(entry, dict) for entry in value):
            # A later compound list can contribute to this same dotted key.
            final[key] = value.copy()
        else:
            for entry in value:
                flat_value = flatten_deep(entry)
                for child_key, child_value in flat_value.items():
                    full_key = f"{key}.{child_key}"
                    final.setdefault(full_key, []).extend(
                        child_value if isinstance(child_value, list) else [child_value]
                    )

    return final


def unflatten(data: _Mapping) -> _Mapping:
    "Unflatten a nested dict"
    out: dict[str, Any] = dict()
    for k, v in data.items():
        parts = k.split(".")
        d = out
        for p in parts[:-1]:
            if p not in d:
                d[p] = dict()
            d = d[p]
        d[parts[-1]] = v
    return out


def _leaf_paths(value: Any, path: str) -> Iterator[str]:
    """Walk document fields, keeping the same field path across array elements."""
    if isinstance(value, Mapping) and value:
        for key, child in value.items():
            yield from _leaf_paths(child, f"{path}.{key}")
    elif isinstance(value, list) and value:
        for child in value:
            yield from _leaf_paths(child, path)
    else:
        yield path


def _known_field_path(model: type[BaseModel], path: str) -> bool:
    """Follow serialized field names and consume one dynamic key per typed mapping."""
    from howler.models.registry import field_metadata, model_registry, unwrap_annotation

    annotation: Any = model
    metadata = None
    for part in path.split("."):
        value_type = unwrap_annotation(annotation)
        while get_origin(value_type) is list:
            annotation = get_args(value_type)[0]
            metadata = field_metadata(annotation)
            value_type = unwrap_annotation(annotation)

        if isinstance(value_type, type) and issubclass(value_type, BaseModel):
            definition = model_registry.fields(value_type).get(part)
            if definition is None:
                return False
            annotation, metadata = definition.annotation, definition.metadata
        elif metadata and metadata.kind in {"FlattenedObject", "FlattenedListObject", "Json"}:
            return True
        elif metadata and metadata.kind == "Mapping" and get_origin(value_type) is dict:
            annotation = get_args(value_type)[1]
            metadata = field_metadata(annotation)
        else:
            return False
    return True


def extra_keys(model: type[BaseModel], data: _Mapping) -> set[str]:
    """Return unknown flattened paths, allowing dynamic mapping keys."""
    paths = {path for key, value in data.items() for path in _leaf_paths(value, key)}
    return {path for path in paths if not _known_field_path(model, path)}


def prune(  # noqa: C901
    data: _Mapping, keys: list[str], mapping_paths: set[str], parent_key: Optional[str] = None
) -> dict[str, Any]:
    "Remove all keys in the given list from the dict if they exist"
    pruned_items: list[tuple[str, Any]] = []

    for key, val in data.items():
        cur_key = f"{parent_key}.{key}" if parent_key else key

        # If this key is a mapping, preserve all children
        if cur_key in mapping_paths:
            pruned_items.append((key, val))
        elif isinstance(val, dict):
            child_keys = [_key for _key in keys if _key.startswith(cur_key)]

            if len(child_keys) > 0:
                pruned_items.append((key, prune(val, child_keys, mapping_paths, cur_key)))
        elif isinstance(val, list):
            if cur_key not in keys and not any(_key.startswith(cur_key) for _key in keys):
                continue

            list_result = []
            for entry in val:
                if isinstance(val, dict):
                    child_keys = [_key for _key in keys if _key.startswith(cur_key)]

                    if len(child_keys) > 0:
                        pruned_items.append((key, prune(val, child_keys, mapping_paths, cur_key)))
                else:
                    list_result.append(entry)

            pruned_items.append((key, list_result))
        elif cur_key in keys:
            pruned_items.append((key, val))

    return {k: v for k, v in pruned_items}
