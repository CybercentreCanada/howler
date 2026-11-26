"""Spark schema compatibility against annotated Howler Pydantic fields."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from howler.common.exceptions import HowlerValueError
from howler.models import (
    HowlerEmbeddedModel,
    ModelExtensionRegistry,
    boolean,
    clue,
    date,
    float_field,
    integer,
    keyword,
    list_field,
    mapping,
    register_model,
    text,
    uuid,
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
    _make_type_verifier,
)

from sync.iceberg.build import build_schema
from sync.services import sync_service


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
    compound_field: Nested
    list_field: list_field(integer(description="internal description"))
    mapping_field: mapping(text(), description="parent level description")
    optional_items: list_field(integer(description="optional item description", optional=True))


@register_model(embedded=True)
class Defaults(HowlerEmbeddedModel):
    required_field: keyword()
    optional_field: integer(optional=True)
    default_value_field: date(default="NOW")
    nullable_default_field: text(optional=True, default="value")
    nullable_list: list_field(text(), optional=True)
    list_with_nullable_elements: list_field(text(optional=True, default="value"), default=[])
    list_with_defaulted_elements: list_field(integer(default=0))
    nullable_mapping: mapping(text(), optional=True)
    mapping_with_nullable_values: mapping(text(optional=True), default={})
    mapping_with_generated_values: mapping(uuid())
    mapping_of_lists: mapping(list_field(date(default="NOW")))
    nullable_compound: Nested | None = None


@register_model(embedded=True)
class SyncFalse(HowlerEmbeddedModel):
    included: keyword()
    excluded: keyword(sync=False)


@register_model(embedded=True)
class AnyField(HowlerEmbeddedModel):
    raw: object


@register_model()
class ExtendedHit(Hit):
    plugin_field: keyword(optional=True)


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
    assert schema["list_field"].dataType == ArrayType(IntegerType(), containsNull=True)
    assert schema["mapping_field"].dataType == MapType(StringType(), StringType(), valueContainsNull=True)
    assert schema["top_level_field"].metadata == {"description": "top level description"}
    assert schema["list_field"].metadata == {"description": "internal description"}
    assert schema["mapping_field"].metadata == {"description": "parent level description"}
    assert schema["optional_items"].metadata == {"description": "optional item description"}


def test_optional_fields_and_elements():
    schema = build_schema(Defaults)
    assert schema["required_field"].nullable
    assert schema["optional_field"].nullable
    assert not schema["default_value_field"].nullable
    assert schema["nullable_default_field"].nullable
    assert schema["nullable_list"].nullable
    assert not schema["list_with_nullable_elements"].nullable
    assert schema["list_with_nullable_elements"].dataType.containsNull
    assert not schema["list_with_defaulted_elements"].dataType.containsNull
    assert schema["nullable_mapping"].nullable
    assert not schema["mapping_with_nullable_values"].nullable
    assert schema["mapping_with_nullable_values"].dataType.valueContainsNull
    assert not schema["mapping_with_generated_values"].dataType.valueContainsNull
    assert schema["mapping_of_lists"].dataType == MapType(
        StringType(), ArrayType(TimestampType(), containsNull=False), valueContainsNull=True
    )
    assert schema["nullable_compound"].nullable
    assert isinstance(schema["nullable_compound"].dataType, StructType)


def test_sync_false_excluded_and_any_fallback():
    assert build_schema(SyncFalse).fieldNames() == ["included"]
    with pytest.raises(HowlerValueError, match="``Any`` type is not supported"):
        build_schema(AnyField)
    assert build_schema(AnyField, allow_any_as_string=True)["raw"].dataType == StringType()


def test_public_hit_schema_matches_legacy_fields():
    """Representative build_schema(Hit).jsonValue() fields at 3bd051b72cf7e3fbd96fba2d495c8d83f1ae2f4c."""
    schema = build_schema(Hit)
    assert schema["tags"].jsonValue() == {
        "name": "tags",
        "type": {"type": "array", "elementType": "string", "containsNull": True},
        "nullable": False,
        "metadata": {"description": "List of keywords used to tag each event."},
    }
    assert schema["labels"].jsonValue() == {
        "name": "labels",
        "type": {"type": "map", "keyType": "string", "valueType": "string", "valueContainsNull": True},
        "nullable": False,
        "metadata": {"description": "Custom key/value pairs."},
    }
    assert schema["howler"].dataType["labels"].nullable
    assert schema["timestamp"].dataType == TimestampType()
    assert not schema["timestamp"].nullable
    assert isinstance(schema["related"].dataType, StructType)
    assert isinstance(schema["related"].dataType["ip"].dataType, ArrayType)
    assert schema["related"].dataType["ip"].dataType.elementType.typeName() == "binary"


def test_finalized_hit_extension_schema(monkeypatch):
    """Read the same public schema fields as on the legacy Hit with all three extensions enabled."""
    plugins = Path(__file__).resolve().parents[4]
    monkeypatch.syspath_prepend(plugins / "evidence")
    monkeypatch.syspath_prepend(plugins / "sentinel")
    from evidence.models import hit as evidence
    from sentinel.models import hit as sentinel

    registry = ModelExtensionRegistry()
    for module in (clue, evidence, sentinel):
        monkeypatch.setattr(module, "model_extensions", registry)
        module.declare_hit_extension()
    schema = build_schema(registry.finalize(Hit))

    field = schema["evidence"]
    assert not field.nullable
    assert field.dataType.containsNull
    assert field.dataType.elementType["tags"].dataType == ArrayType(StringType(), containsNull=True)
    assert field.dataType.elementType["labels"].dataType == MapType(StringType(), StringType(), valueContainsNull=True)
    assert schema["clue"].nullable
    assert schema["clue"].dataType["types"].dataType.containsNull
    assert schema["sentinel"].nullable
    assert schema["sentinel"].dataType["alert_id"].nullable


def test_spark_accepts_null_batches_from_finalized_hit():
    registry = ModelExtensionRegistry()
    batch = list_field(keyword(), optional=True, default=[])
    registry.declare(Hit, "batch", batch, plugin="test")
    registry.declare(Hit, "batches", list_field(batch, default=[]), plugin="test")
    model = registry.finalize(Hit)

    hit = model.model_validate(
        {"howler": {"analytic": "Test", "hash": "ab"}, "batch": None, "batches": [None, ["abc"]]}
    )
    row = hit.as_primitives(strip_null=False)
    assert row["batch"] is None
    assert row["batches"] == [None, ["abc"]]

    schema = build_schema(model)
    # Use Spark's createDataFrame row verifier on the extension columns, without starting a JVM.
    _make_type_verifier(StructType([schema["batches"], schema["batch"]]))(row)
    assert not schema["batches"].nullable
    assert not schema["timestamp"].nullable  # date(default="NOW")


@pytest.mark.parametrize("model", [ExtendedHit, None])
def test_hit_service_schema_uses_datastore_model(monkeypatch, model):
    monkeypatch.setattr(sync_service, "datastore", lambda: SimpleNamespace(hit=SimpleNamespace(model_class=model)))

    schema = sync_service.get_model_struct_schema(Hit)

    assert schema == build_schema(model or Hit)
    assert ("plugin_field" in schema.fieldNames()) is (model is ExtendedHit)
