from howler import odm
from howler.common.exceptions import HowlerValueError
from howler.common.logging import get_logger
from howler.odm import (
    Any,
    Compound,
    List,
    Mapping,
    Optional,
    base,
)
from pyspark.sql.types import (
    ArrayType,
    DataType,
    MapType,
    StructField,
    StructType,
)

from sync.iceberg.mappings import TYPE_MAPPING

logger = get_logger(__file__)


def _is_optional(field: base._Field) -> bool:
    """Check if a field is optional."""
    return field.optional or field.default_set


def data_type_from_field(field: base._Field, allow_any_as_string: bool = False) -> tuple[DataType, bool]:
    """Get the Spark data type and nullability for a given field."""
    field_name = field.__class__.__name__
    if field_name in TYPE_MAPPING:
        return TYPE_MAPPING[field_name], _is_optional(field)
    else:
        if isinstance(field, Optional):
            child_type, nullable = data_type_from_field(field.child_type, allow_any_as_string=allow_any_as_string)
            return child_type, True

        elif isinstance(field, List):
            child_type, nullable = data_type_from_field(field.child_type, allow_any_as_string=allow_any_as_string)
            return ArrayType(elementType=child_type, containsNull=nullable), _is_optional(field)

        elif isinstance(field, Compound):
            schema = build_schema(field.child_type)
            return schema, _is_optional(field)

        elif isinstance(field, Mapping):
            child_type, nullable = data_type_from_field(field.child_type, allow_any_as_string=allow_any_as_string)
            return (
                MapType(keyType=TYPE_MAPPING["Keyword"], valueType=child_type, valueContainsNull=nullable),
                _is_optional(field),
            )

        elif isinstance(field, Any):
            if not allow_any_as_string:
                raise HowlerValueError(f"``Any`` type is not supported for Spark schema: {field.name}")
            logger.warning(f"Using string type for ``Any`` field: {field.name}")
            return TYPE_MAPPING["Any"], _is_optional(field)

        else:
            raise HowlerValueError(f"Unknown type for Spark schema: {field_name}")


def build_schema(model: type[odm.Model] | odm.Model) -> StructType:
    """The spark schema based on a python model object."""
    field_data: list[base._Field] = model.fields().values()  # type: ignore
    fields = []

    for field in field_data:
        if not field.sync:
            continue

        name: str = field.name  # type: ignore
        data_type, nullable = data_type_from_field(field)
        fields.append(StructField(name, data_type, nullable=nullable))

    return StructType(fields=fields)
