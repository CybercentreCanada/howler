"""Spark schema compatibility against annotated Howler Pydantic fields."""

import pytest
from howler.common.exceptions import HowlerValueError
from howler.models import (
    HowlerEmbeddedModel,
    boolean,
    compound,
    date,
    float_field,
    integer,
    keyword,
    list_field,
    mapping,
    optional,
    register_model,
    text,
)
from howler.models.hit import Hit
from pyspark.sql.types import (
    ArrayType,
    BooleanType,
    DoubleType,
    IntegerType,
    MapType,
    StringType,
    StructType,
    TimestampType,
)

from sync.iceberg.build import build_schema


@register_model(embedded=True)
class Simple(HowlerEmbeddedModel):
    keyword_field: keyword()
    boolean_field: boolean()
    integer_field: integer()
    float_field: float_field()
    text_field: text()
    date_field: date()


@register_model(embedded=True)
class Nested(HowlerEmbeddedModel):
    nested_keyword: keyword()
    nested_integer: integer()
    nested_date: date()
    nested_complex_type: mapping(text())


@register_model(embedded=True)
class Containers(HowlerEmbeddedModel):
    top_level_field: keyword(description="top level description")
    compound_field: compound(Nested)
    list_field: list_field(integer(description="internal description"))
    mapping_field: mapping(text(), description="parent level description")


@register_model(embedded=True)
class Defaults(HowlerEmbeddedModel):
    required_field: keyword()
    optional_field: optional(integer())
    default_value_field: date(default="NOW")
    nullable_default_field: optional(text())
    nullable_list: optional(list_field(text()))
    list_with_nullable_elements: list_field(optional(text()), default=[])
    nullable_mapping: optional(mapping(text()))
    mapping_with_nullable_values: mapping(optional(text()), default={})
    nullable_compound: optional(compound(Nested))


@register_model(embedded=True)
class SyncFalse(HowlerEmbeddedModel):
    included: keyword()
    excluded: keyword(sync=False)


@register_model(embedded=True)
class AnyField(HowlerEmbeddedModel):
    raw: object


def test_basic_types_and_instance():
    for model in (Simple, Simple.model_construct()):
        schema = build_schema(model)
        assert schema.fieldNames() == list(Simple.model_fields)
        assert schema["keyword_field"].dataType == StringType()
        assert schema["boolean_field"].dataType == BooleanType()
        assert schema["integer_field"].dataType == IntegerType()
        assert schema["float_field"].dataType == DoubleType()
        assert schema["text_field"].dataType == StringType()
        assert schema["date_field"].dataType == TimestampType()


def test_nested_types_and_descriptions():
    schema = build_schema(Containers)
    assert schema.fieldNames() == list(Containers.model_fields)
    nested = schema["compound_field"].dataType
    assert isinstance(nested, StructType)
    assert nested.fieldNames() == list(Nested.model_fields)
    assert isinstance(nested["nested_complex_type"].dataType, MapType)
    assert schema["list_field"].dataType == ArrayType(IntegerType(), containsNull=False)
    assert schema["mapping_field"].dataType == MapType(StringType(), StringType(), valueContainsNull=False)
    assert schema["top_level_field"].metadata == {"description": "top level description"}
    assert schema["list_field"].metadata == {"description": "internal description"}
    assert schema["mapping_field"].metadata == {"description": "parent level description"}


def test_optional_fields_and_elements():
    schema = build_schema(Defaults)
    assert schema["required_field"].nullable
    assert schema["optional_field"].nullable
    assert not schema["default_value_field"].nullable
    assert schema["nullable_default_field"].nullable
    assert schema["nullable_list"].nullable
    assert not schema["list_with_nullable_elements"].nullable
    assert schema["list_with_nullable_elements"].dataType.containsNull
    assert schema["nullable_mapping"].nullable
    assert not schema["mapping_with_nullable_values"].nullable
    assert schema["mapping_with_nullable_values"].dataType.valueContainsNull
    assert schema["nullable_compound"].nullable
    assert isinstance(schema["nullable_compound"].dataType, StructType)


def test_sync_false_excluded_and_any_fallback():
    assert build_schema(SyncFalse).fieldNames() == ["included"]
    with pytest.raises(HowlerValueError, match="``Any`` type is not supported"):
        build_schema(AnyField)
    assert build_schema(AnyField, allow_any_as_string=True)["raw"].dataType == StringType()


def test_hit_schema_contains_timestamp_and_ip_binary():
    schema = build_schema(Hit)
    assert schema["timestamp"].dataType == TimestampType()
    assert isinstance(schema["related"].dataType, StructType)
    assert isinstance(schema["related"].dataType["ip"].dataType, ArrayType)
    assert schema["related"].dataType["ip"].dataType.elementType.typeName() == "binary"
