"""Lenient field-by-field construction for Pydantic Howler models."""

from __future__ import annotations

import types
from typing import Any, Union, get_args, get_origin

from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError

from howler.models.fields import _make_annotated
from howler.models.registry import model_annotation, unwrap_annotation

SAFE_ADAPTER_CONFIG = ConfigDict(arbitrary_types_allowed=True)


def _merge_dropped(dropped: dict[str, Any], clean: dict[str, Any]) -> dict[str, Any]:
    output = dict(dropped)
    for key, value in clean.items():
        if key in output and isinstance(output[key], dict) and isinstance(value, dict):
            output[key] = _merge_dropped(output[key], value)
        elif key not in output:
            output[key] = value
    return output


def _annotated(annotation: Any, metadata: list[Any]) -> Any:
    return _make_annotated(annotation, *metadata) if metadata else annotation


def _safe_value(annotation: Any, value: Any, metadata: list[Any] | None = None) -> tuple[Any, Any]:
    full_annotation = _annotated(annotation, list(metadata or []))
    unwrapped = unwrap_annotation(full_annotation)
    origin = get_origin(unwrapped)

    if origin is list:
        child_annotation = get_args(unwrapped)[0]
        clean_items: list[Any] = []
        dropped_items: list[Any] = []
        try:
            items = list(value)
        except TypeError:
            return None, value
        for item in items:
            clean, dropped = _safe_value(child_annotation, item)
            if clean is not None:
                clean_items.append(clean)
            if dropped not in (None, ""):
                dropped_items.append(dropped)
        return clean_items or None, dropped_items or None

    embedded = model_annotation(unwrapped)
    if embedded is not None:
        clean, dropped = construct_safe(embedded, value)
        return clean, dropped or None

    optional_origin = get_origin(full_annotation)
    if optional_origin in (Union, types.UnionType) and value is None:
        return None, None

    try:
        return TypeAdapter(full_annotation, config=SAFE_ADAPTER_CONFIG).validate_python(value), None
    except (TypeError, ValueError, ValidationError):
        return None, value


def construct_safe(model_type: type[BaseModel], data: Any) -> tuple[BaseModel | None, Any]:  # noqa: C901
    """Build the valid portion of a model and return rejected values by path."""
    if not isinstance(data, dict):
        return None, data

    fields_by_input: dict[str, tuple[str, Any]] = {}
    for python_name, info in model_type.model_fields.items():
        if python_name == "meta":
            continue
        for name in (python_name, info.alias, info.validation_alias):
            if isinstance(name, str):
                fields_by_input[name] = (python_name, info)

    clean: dict[str, Any] = {}
    dropped: dict[str, Any] = {}
    for key, value in data.items():
        field_entry = fields_by_input.get(key)
        if field_entry is None:
            dropped[key] = value
            continue
        python_name, info = field_entry
        validated, rejected = _safe_value(info.annotation, value, info.metadata)
        if validated is not None:
            clean[python_name] = validated
        if rejected is not None:
            dropped[key] = rejected

    try:
        return model_type.model_validate(clean), dropped
    except ValidationError:
        return None, _merge_dropped(dropped, clean)
