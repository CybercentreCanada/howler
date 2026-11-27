"""Build Spark schemas from finalized Howler Pydantic model metadata."""

import types
from typing import Any, Union, get_args, get_origin

from howler.common.exceptions import HowlerValueError
from howler.common.logging import get_logger
from howler.models.registry import (
    FieldDefinition,
    annotation_metadata,
    field_metadata,
    model_annotation,
    model_registry,
    unwrap_annotation,
)
from pydantic import BaseModel
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined
from pyspark.sql.types import ArrayType, DataType, MapType, StructField, StructType

from sync.iceberg.mappings import TYPE_MAPPING

logger = get_logger(__file__)


def _nullable(field: FieldDefinition | FieldInfo) -> bool:
    """Sync permits null unless this field has a non-null default without optional=True."""
    if field.default_factory is None and (field.default is None or field.default is PydanticUndefined):
        return True

    annotation = field.annotation
    if get_origin(annotation) not in (Union, types.UnionType) or type(None) not in get_args(annotation):
        return False

    # Scalar builders like date(default="NOW") keep datetime | None as their annotation
    # without setting optional=True on HowlerFieldMetadata.
    metadata = field.metadata if isinstance(field, FieldDefinition) else field_metadata(annotation, field.metadata)
    return metadata is None or metadata.optional


def _type_from_annotation(annotation: Any, field: FieldDefinition, allow_any_as_string: bool) -> DataType:
    unwrapped = unwrap_annotation(annotation)
    origin = get_origin(unwrapped)
    if origin is list:
        child = get_args(unwrapped)[0]
        return ArrayType(
            _type_from_annotation(child, field, allow_any_as_string),
            containsNull=_nullable(FieldInfo.from_annotation(child)),
        )
    if origin is dict:
        child = get_args(unwrapped)[1]
        return MapType(
            TYPE_MAPPING["Keyword"],
            _type_from_annotation(child, field, allow_any_as_string),
            valueContainsNull=_nullable(FieldInfo.from_annotation(child)),
        )
    if nested := model_annotation(unwrapped):
        return build_schema(nested, allow_any_as_string=allow_any_as_string)

    metadata = field_metadata(annotation) or field.metadata
    kind = metadata.kind if metadata and metadata.kind else "Any"
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
                for item in annotation_metadata(child):
                    if getattr(item, "description", None):
                        description = item.description
                        break
        metadata = {"description": description} if description else None
        fields.append(StructField(field.name, data_type, nullable=nullable, metadata=metadata))
    return StructType(fields=fields)
