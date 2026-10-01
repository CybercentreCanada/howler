"""Runtime compatibility for nullable field annotations on supported Python versions."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Annotated, Any

import pytest
from elasticsearch import dsl
from pydantic import Field, TypeAdapter, ValidationError

from howler.models import (
    HowlerESModel,
    integer,
    keyword,
    list_field,
    mapping,
    model_registry,
    optional,
)

API_ROOT = Path(__file__).parents[3]


class NullableAnnotationRuntimeModel(HowlerESModel):
    """Exercise optional primitive, list, and mapping annotations in one model."""

    maybe: optional(keyword(), alias="external_value")  # pyright: ignore[reportInvalidTypeForm]
    disabled: optional(keyword(index=False, store=False))  # pyright: ignore[reportInvalidTypeForm]
    with_default: optional(keyword(), default="fallback")  # pyright: ignore[reportInvalidTypeForm]
    items: optional(list_field(keyword()))  # pyright: ignore[reportInvalidTypeForm]
    values: optional(mapping(integer(), index=True, store=True))  # pyright: ignore[reportInvalidTypeForm]


def test_models_with_nullable_fields_import_in_a_fresh_interpreter() -> None:
    """Cold imports cover model declarations that construct nullable DSL fields."""
    imports = """
from importlib import import_module
for name in (
    'howler.models.fields',
    'howler.models.case',
    'howler.models.record',
    'howler.models.hit',
    'howler.models.howler_data',
    'howler.models.user',
    'howler.models.template',
):
    import_module(name)
"""
    result = subprocess.run(
        [sys.executable, "-c", imports],
        check=False,
        cwd=API_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, f"cold model import failed:\n{result.stdout}\n{result.stderr}"


def test_nullable_fields_preserve_nulls_validation_defaults_and_aliases() -> None:
    """Null bypasses child validators while non-null values retain child validation."""
    defaults = NullableAnnotationRuntimeModel.model_validate({})

    assert defaults.maybe is None
    assert defaults.disabled is None
    assert defaults.with_default == "fallback"
    assert defaults.items is None
    assert defaults.values is None

    explicit_nulls = NullableAnnotationRuntimeModel.model_validate(
        {"external_value": None, "disabled": None, "items": None, "values": None}
    )
    assert explicit_nulls.maybe is None
    assert explicit_nulls.disabled is None
    assert explicit_nulls.items is None
    assert explicit_nulls.values is None

    model = NullableAnnotationRuntimeModel.model_validate(
        {
            "external_value": 123,
            "items": [1, "two"],
            "values": {"valid_key": "2"},
        }
    )

    assert model.maybe == "123"
    assert model.items == ["1", "two"]
    assert model.values == {"valid_key": 2}
    assert model.model_dump(by_alias=True)["external_value"] == "123"

    with pytest.raises(ValidationError):
        NullableAnnotationRuntimeModel.model_validate({"external_value": b"bytes"})
    with pytest.raises(ValidationError):
        NullableAnnotationRuntimeModel.model_validate({"items": [b"bytes"]})
    with pytest.raises(ValidationError):
        NullableAnnotationRuntimeModel.model_validate({"values": {"Invalid-Key": "2"}})


def test_nullable_tuple_preserves_reversed_ordered_union_branches() -> None:
    """Moving map metadata must not collapse opposite ordered unions in a tuple."""
    mode = Field(union_mode="left_to_right")
    first = Annotated[int | str, dsl.mapped_field(dsl.Keyword()), mode]
    second = Annotated[str | int, dsl.mapped_field(dsl.Keyword()), mode]

    value = TypeAdapter(optional(tuple[first, second])).validate_python(("12", "12"))

    assert type(value[0]) is int
    assert type(value[1]) is str
    assert value == (12, "12")


def test_nullable_ordered_union_preserves_none_zero_and_string_coercion() -> None:
    """A nullable ordered union accepts None and retains both coercion branches."""
    child_type = Annotated[int | str, dsl.mapped_field(dsl.Keyword()), Field(union_mode="left_to_right")]
    adapter = TypeAdapter(optional(child_type))

    assert adapter.validate_python(None) is None
    zero = adapter.validate_python("0")
    assert type(zero) is int
    assert zero == 0
    text = adapter.validate_python("not-a-number")
    assert type(text) is str
    assert text == "not-a-number"


def test_nullable_fields_keep_mapping_metadata_and_container_mappings() -> None:
    """Extracted DSL metadata still describes aliases, index flags, and list leaves."""
    fields = model_registry.fields(NullableAnnotationRuntimeModel)
    disabled = fields["disabled"].metadata
    assert disabled is not None
    assert disabled.index is False
    assert disabled.store is False
    values = fields["values"].metadata
    assert values is not None
    assert values.index is True
    assert values.store is True

    model_mapping: dict[str, Any] = model_registry.mapping(NullableAnnotationRuntimeModel)["properties"]
    assert model_mapping["external_value"]["type"] == "keyword"
    assert model_mapping["disabled"]["index"] is False
    assert model_mapping["disabled"]["doc_values"] is False
    assert model_mapping["items"]["type"] == "keyword"
    assert model_mapping["values"]["type"] == "object"
