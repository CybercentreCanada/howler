"""Shared helpers for building field-scoped Elasticsearch operations from ODM models."""

import re
from typing import Iterable, Optional

from howler import odm


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
            elif any(path.startswith(f"{cur_path}.") for path in allowed):
                result[key] = prune_to_paths(sub_value, allowed, cur_path)
        return result

    if isinstance(value, list):
        return [prune_to_paths(entry, allowed, prefix) for entry in value]

    return value
