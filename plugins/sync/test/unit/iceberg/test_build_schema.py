import pytest
from howler import odm
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


@pytest.fixture(scope="module")
def model_with_basic_fields() -> type[odm.Model]:
    @odm.model()
    class TestModel(odm.Model):
        keyword_field = odm.Keyword()
        boolean_field = odm.Boolean()
        integer_field = odm.Integer()
        float_field = odm.Float()
        text_field = odm.Text()
        date_field = odm.Date()

    return TestModel


@pytest.fixture(scope="module")
def nested_model() -> type[odm.Model]:
    @odm.model()
    class NestedModel(odm.Model):
        nested_keyword = odm.Keyword()
        nested_integer = odm.Integer()
        nested_date = odm.Date()
        nested_complex_type = odm.Mapping(odm.Text())

    return NestedModel


@pytest.fixture(scope="module")
def model_with_nested_fields(nested_model) -> type[odm.Model]:
    @odm.model()
    class TestModel(odm.Model):
        top_level_field = odm.Keyword(description="top level description")
        compound_field = odm.Compound(nested_model)
        list_field = odm.List(odm.Integer(description="internal description"))
        mapping_field = odm.Mapping(odm.Text(), description="parent level description")

    return TestModel


@pytest.fixture(scope="module")
def model_with_optional_fields(nested_model) -> type[odm.Model]:
    @odm.model()
    class TestModel(odm.Model):
        required_field = odm.Keyword()
        optional_field = odm.Optional(odm.Integer())
        default_value_field = odm.Date(default="NOW")
        nullable_default_field = odm.Optional(odm.Text(default="default_value"))
        nullable_list = odm.Optional(odm.List(odm.Text(default="default_value")))
        list_with_nullable_elements = odm.List(odm.Optional(odm.Text()), default=[])
        nullable_mapping = odm.Optional(odm.Mapping(odm.Text(default="default_value")))
        mapping_with_nullable_values = odm.Mapping(odm.Optional(odm.Text()), default={})
        nullable_compound = odm.Optional(odm.Compound(nested_model))

    return TestModel


@pytest.fixture(scope="module")
def model_with_any_field() -> type[odm.Model]:
    @odm.model()
    class TestModel(odm.Model):
        any_field = odm.Any()

    return TestModel


@pytest.fixture(scope="module")
def model_with_sync_false_field(model_with_basic_fields) -> type[odm.Model]:
    @odm.model()
    class TestModel(model_with_basic_fields):
        sync_false_field = odm.Keyword(sync=False)

    return TestModel


@pytest.fixture(scope="module")
def instance_with_basic_fields(model_with_basic_fields):
    return model_with_basic_fields(
        {
            "keyword_field": "test",
            "boolean_field": True,
            "integer_field": 42,
            "float_field": 3.14,
            "text_field": "Hello, world!",
            "date_field": "2023-01-01T00:00:00Z",
        }
    )


def test_build_schema_with_basic_fields(model_with_basic_fields):
    schema = build_schema(model_with_basic_fields)

    assert schema.fieldNames() == [
        "keyword_field",
        "boolean_field",
        "integer_field",
        "float_field",
        "text_field",
        "date_field",
    ]

    assert schema["keyword_field"].dataType == StringType()
    assert schema["boolean_field"].dataType == BooleanType()
    assert schema["integer_field"].dataType == IntegerType()
    assert schema["float_field"].dataType == DoubleType()
    assert schema["text_field"].dataType == StringType()
    assert schema["date_field"].dataType == TimestampType()


def test_build_schema_with_nested_fields(model_with_nested_fields):
    schema = build_schema(model_with_nested_fields)

    assert schema.fieldNames() == ["top_level_field", "compound_field", "list_field", "mapping_field"]

    compound_field = schema["compound_field"]
    assert isinstance(compound_field.dataType, StructType)
    assert compound_field.dataType.fieldNames() == [
        "nested_keyword",
        "nested_integer",
        "nested_date",
        "nested_complex_type",
    ]
    nested_complex_type_field = compound_field.dataType["nested_complex_type"]
    assert isinstance(nested_complex_type_field.dataType, MapType)

    list_field = schema["list_field"]
    assert isinstance(list_field.dataType, ArrayType)
    assert list_field.dataType.elementType == IntegerType()

    mapping_field = schema["mapping_field"]
    assert isinstance(mapping_field.dataType, MapType)
    assert mapping_field.dataType.keyType == StringType()
    assert mapping_field.dataType.valueType == StringType()


def test_descriptions_added_to_metadata(model_with_nested_fields):
    schema = build_schema(model_with_nested_fields)

    top_level_field = schema["top_level_field"]
    assert top_level_field.metadata == {"description": "top level description"}

    compound_field = schema["compound_field"]
    assert compound_field.metadata == {}  # check that it's not {"description": None}

    list_field = schema["list_field"]
    assert list_field.metadata == {"description": "internal description"}

    mapping_field = schema["mapping_field"]
    assert mapping_field.metadata == {"description": "parent level description"}


def test_build_schema_with_optional_fields(model_with_optional_fields):
    schema = build_schema(model_with_optional_fields)

    assert schema.fieldNames() == [
        "required_field",
        "optional_field",
        "default_value_field",
        "nullable_default_field",
        "nullable_list",
        "list_with_nullable_elements",
        "nullable_mapping",
        "mapping_with_nullable_values",
        "nullable_compound",
    ]

    required_field = schema["required_field"]
    assert required_field.nullable is True

    optional_field = schema["optional_field"]
    assert optional_field.nullable is True

    default_value_field = schema["default_value_field"]
    assert default_value_field.nullable is False

    nullable_default_field = schema["nullable_default_field"]
    assert nullable_default_field.nullable is True

    nullable_list = schema["nullable_list"]
    assert nullable_list.nullable is True

    list_with_nullable_elements = schema["list_with_nullable_elements"]
    assert list_with_nullable_elements.nullable is False
    assert isinstance(list_with_nullable_elements.dataType, ArrayType)
    assert list_with_nullable_elements.dataType.containsNull is True

    nullable_mapping = schema["nullable_mapping"]
    assert nullable_mapping.nullable is True

    mapping_with_nullable_values = schema["mapping_with_nullable_values"]
    assert mapping_with_nullable_values.nullable is False
    assert isinstance(mapping_with_nullable_values.dataType, MapType)
    assert mapping_with_nullable_values.dataType.valueContainsNull is True

    nullable_compound = schema["nullable_compound"]
    assert nullable_compound.nullable is True
    assert isinstance(nullable_compound.dataType, StructType)


def test_build_schema_with_instance(instance_with_basic_fields):
    instance = instance_with_basic_fields
    schema = build_schema(instance)

    assert schema.fieldNames() == [
        "keyword_field",
        "boolean_field",
        "integer_field",
        "float_field",
        "text_field",
        "date_field",
    ]

    assert schema["keyword_field"].dataType == StringType()
    assert schema["boolean_field"].dataType == BooleanType()
    assert schema["integer_field"].dataType == IntegerType()
    assert schema["float_field"].dataType == DoubleType()
    assert schema["text_field"].dataType == StringType()
    assert schema["date_field"].dataType == TimestampType()


def test_build_schema_does_not_include_sync_false_fields(model_with_sync_false_field):
    schema = build_schema(model_with_sync_false_field)

    assert "sync_false_field" not in schema.fieldNames()
    assert len(schema.fieldNames()) == len(model_with_sync_false_field.fields()) - 1
