from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, AnyStr, Optional, cast
from typing import Mapping as _Mapping

if TYPE_CHECKING:
    from howler.odm.base import Model, _Field


def strip_nulls(d: Any):
    """Remove null values from a dict"""
    if isinstance(d, dict):
        return {k: strip_nulls(v) for k, v in d.items() if v is not None}
    else:
        return d


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


def flatten(data: _Mapping, parent_key: Optional[str] = None, odm: Optional[type["Model"]] = None) -> dict[str, Any]:
    "Flatten a nested dict"
    items: list[tuple[str, Any]] = []
    for k, v in data.items():
        cur_key = f"{parent_key}.{k}" if parent_key is not None else k

        if isinstance(v, dict):
            if odm:
                valid_keys = list(odm.flat_fields().keys())
                if not next((key for key in valid_keys if key.startswith(f"{cur_key}.")), False):
                    items.append((cur_key, v))
                    continue

            items.extend(flatten(v, cur_key, odm=odm).items())
        else:
            items.append((cur_key, v))

    return dict(items)


def flatten_deep(data: _Mapping):
    "Aggressively and completely flatten an object."
    partially_flattened = flatten(data)

    final: dict[str, Any] = {}
    for key, value in partially_flattened.items():
        if not isinstance(value, list) or len(value) == 0 or all(not isinstance(entry, dict) for entry in value):
            final[key] = value
        else:
            for entry in value:
                flat_value = flatten_deep(entry)
                for child_key, child_value in flat_value.items():
                    full_key = f"{key}.{child_key}"
                    if full_key not in final:
                        if isinstance(child_value, list):
                            final[full_key] = child_value
                        else:
                            final[full_key] = [child_value]
                    else:
                        if isinstance(child_value, list):
                            final[full_key].extend(child_value)
                        else:
                            final[full_key].append(child_value)

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


def extra_keys(odm: type["Model"], data: _Mapping) -> set[str]:
    "Geta list of extra keys when compared to a list of permitted keys"
    from howler.odm.base import Mapping, Optional

    data = flatten_deep(data)

    result: set[str] = set()
    for key in data.keys():
        parts = key.split(".")
        current_odm = odm
        for part in parts:
            sub_fields: dict[str, Any] = current_odm.fields()

            if part in sub_fields:
                current_odm = sub_fields[part]
            else:
                if isinstance(current_odm, Optional):
                    current_odm = current_odm.child_type

                if isinstance(current_odm, Mapping):
                    current_odm = current_odm.child_type
                else:
                    result.add(key)
                    break

    return result


def prune(  # noqa: C901
    data: _Mapping, keys: list[str], fields: dict[str, "_Field"], mapping_class: type, parent_key: Optional[str] = None
) -> dict[str, Any]:
    "Remove all keys in the given list from the dict if they exist"
    pruned_items: list[tuple[str, Any]] = []

    for key, val in data.items():
        cur_key = f"{parent_key}.{key}" if parent_key else key

        # If this key is a mapping, preserve all children
        if isinstance(fields.get(cur_key, None), mapping_class):
            pruned_items.append((key, val))
        elif isinstance(val, dict):
            child_keys = [_key for _key in keys if _key.startswith(cur_key)]

            if len(child_keys) > 0:
                pruned_items.append((key, prune(val, child_keys, fields, mapping_class, cur_key)))
        elif isinstance(val, list):
            if cur_key not in keys and not any(_key.startswith(cur_key) for _key in keys):
                continue

            list_result = []
            for entry in val:
                if isinstance(val, dict):
                    child_keys = [_key for _key in keys if _key.startswith(cur_key)]

                    if len(child_keys) > 0:
                        pruned_items.append((key, prune(val, child_keys, fields, mapping_class, cur_key)))
                else:
                    list_result.append(entry)

            pruned_items.append((key, list_result))
        elif cur_key in keys:
            pruned_items.append((key, val))

    return {k: v for k, v in pruned_items}
