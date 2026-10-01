"""Build Spark schemas from finalized Howler Pydantic model metadata."""

import types
from typing import Annotated, Any, Union, get_args, get_origin

from howler.common.exceptions import HowlerValueError
from howler.common.logging import get_logger
from howler.models.registry import (
    FieldDefinition,
    field_metadata,
    model_annotation,
    model_registry,
    unwrap_annotation,
)
from pydantic import BaseModel
from pyspark.sql.types import ArrayType, DataType, MapType, StructField, StructType

from sync.iceberg.mappings import TYPE_MAPPING

logger = get_logger(__file__)


def _is_optional(annotation: Any) -> bool:
    origin = get_origin(annotation)
    if origin in (Union, types.UnionType):
        return type(None) in get_args(annotation)
    if origin is Annotated:
        return _is_optional(get_args(annotation)[0])
    return False


def _nullable(field: FieldDefinition) -> bool:
    """Required fields and fields without a default or factory are nullable in the sync schema."""
    return field.required or (field.default is None and field.default_factory is None)


def _type_from_annotation(annotation: Any, field: FieldDefinition, allow_any_as_string: bool) -> DataType:
    unwrapped = unwrap_annotation(annotation)
    origin = get_origin(unwrapped)
    if origin is list:
        child = get_args(unwrapped)[0]
        return ArrayType(
            _type_from_annotation(child, field, allow_any_as_string),
            containsNull=_is_optional(child),
        )
    if origin is dict:
        child = get_args(unwrapped)[1]
        return MapType(
            TYPE_MAPPING["Keyword"],
            _type_from_annotation(child, field, allow_any_as_string),
            valueContainsNull=_is_optional(child),
        )
    if nested := model_annotation(unwrapped):
        return build_schema(nested, allow_any_as_string=allow_any_as_string)

    metadata = field_metadata(annotation) or field.metadata
    kind = metadata.kind if metadata else "Any"
    if kind == "Any" or unwrapped is Any:
        if not allow_any_as_string:
            raise HowlerValueError(f"``Any`` type is not supported for Spark schema: {field.name}")
        logger.warning("Using string type for ``Any`` field: %s", field.name)
        return TYPE_MAPPING["Any"]
    if kind not in TYPE_MAPPING:
        raise HowlerValueError(f"Unknown type for Spark schema: {kind}")
    return TYPE_MAPPING[kind]


def data_type_from_field(field: FieldDefinition, allow_any_as_string: bool = False) -> tuple[DataType, bool]:
    """Get the Spark data type and nullability for a registered field."""
    return _type_from_annotation(field.annotation, field, allow_any_as_string), _nullable(field)


def build_schema(model: type[BaseModel] | BaseModel, allow_any_as_string: bool = False) -> StructType:
    """Build the Spark schema from a model class or instance."""
    fields = []
    for field in model_registry.fields(model if isinstance(model, type) else type(model)).values():
        if field.metadata and not field.metadata.sync:
            continue
        data_type, nullable = data_type_from_field(field, allow_any_as_string=allow_any_as_string)
        description = field.description
        if not description:
            annotation = unwrap_annotation(field.annotation)
            if get_origin(annotation) in (list, dict):
                child = get_args(annotation)[-1]
                for item in getattr(child, "__metadata__", ()):
                    if getattr(item, "description", None):
                        description = item.description
                        break
        metadata = {"description": description} if description else None
        fields.append(StructField(field.name, data_type, nullable=nullable, metadata=metadata))
    return StructType(fields=fields)
