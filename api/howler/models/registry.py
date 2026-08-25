"""Canonical metadata registry for Pydantic/DSL models."""

from __future__ import annotations

import types
from copy import deepcopy
from dataclasses import dataclass, replace
from typing import Annotated, Any, Union, get_args, get_origin

from pydantic import BaseModel
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined

from howler.common.exceptions import HowlerTypeError, HowlerValueError
from howler.models.fields import FIELD_SANITIZER, FLATTENED_OBJECT_SANITIZER, HowlerFieldMetadata

BANNED_FIELDS = {
    "_id",
    "__access_grp1__",
    "__access_lvl__",
    "__access_req__",
    "__access_grp2__",
}
ACCESS_FIELD_MAPPINGS = {
    "__access_lvl__": {"type": "integer", "index": True},
    "__access_req__": {"type": "keyword", "index": True},
    "__access_grp1__": {"type": "keyword", "index": True},
    "__access_grp2__": {"type": "keyword", "index": True},
}


@dataclass(frozen=True)
class ModelMetadata:
    """Metadata shared by datastore and generated model consumers."""

    name: str
    description: str | None
    id_field: str
    index: bool | None
    store: bool | None
    embedded: bool


@dataclass(frozen=True)
class FieldDefinition:
    """Canonical field view independent of Pydantic's internal structures."""

    name: str
    path: str
    annotation: Any
    metadata: HowlerFieldMetadata | None
    required: bool
    default: Any
    default_factory: Any
    description: str | None
    multivalued: bool = False
    compound_model: type[BaseModel] | None = None


def annotation_metadata(annotation: Any, extra: list[Any] | None = None) -> list[Any]:
    """Return all metadata attached to nested Annotated/Optional annotations."""
    metadata = list(extra or [])
    origin = get_origin(annotation)
    if origin is Annotated:
        nested, *items = get_args(annotation)
        metadata.extend(items)
        metadata.extend(annotation_metadata(nested))
    elif origin is not None:
        for item in get_args(annotation):
            if item is not type(None):
                metadata.extend(annotation_metadata(item))
    return metadata


def field_metadata(annotation: Any, extra: list[Any] | None = None) -> HowlerFieldMetadata | None:
    """Find the outermost Howler field metadata for an annotation."""
    return next(
        (item for item in annotation_metadata(annotation, extra) if isinstance(item, HowlerFieldMetadata)),
        None,
    )


def unwrap_annotation(annotation: Any) -> Any:
    """Remove Annotated and Optional wrappers while retaining containers."""
    origin = get_origin(annotation)
    if origin is Annotated:
        return unwrap_annotation(get_args(annotation)[0])
    if origin in (Union, types.UnionType):
        members = [item for item in get_args(annotation) if item is not type(None)]
        if len(members) == 1:
            return unwrap_annotation(members[0])
    return annotation


def model_annotation(annotation: Any) -> type[BaseModel] | None:
    """Return an embedded model contained directly or in a list annotation."""
    unwrapped = unwrap_annotation(annotation)
    origin = get_origin(unwrapped)
    if origin is list:
        unwrapped = unwrap_annotation(get_args(unwrapped)[0])
    return unwrapped if isinstance(unwrapped, type) and issubclass(unwrapped, BaseModel) else None


def _resolve_metadata(
    metadata: HowlerFieldMetadata | None,
    defaults: ModelMetadata | HowlerFieldMetadata | None,
) -> HowlerFieldMetadata | None:
    if metadata is None or defaults is None:
        return metadata
    return replace(
        metadata,
        index=metadata.index if metadata.index is not None else defaults.index,
        store=metadata.store if metadata.store is not None else defaults.store,
    )


class ModelRegistry:
    """Registry exposing one stable view of model and field metadata."""

    def __init__(self) -> None:
        self._models: dict[type[BaseModel], ModelMetadata] = {}

    def register(
        self,
        model_type: type[BaseModel],
        *,
        description: str | None = None,
        id_field: str | None = None,
        index: bool | None = None,
        store: bool | None = None,
        embedded: bool = False,
    ) -> type[BaseModel]:
        """Register or replace metadata for a model class."""
        if id_field is not None and not isinstance(id_field, str):
            raise HowlerTypeError(f"id_field must be a str, got {type(id_field).__name__}")

        resolved_id = id_field or f"{model_type.__name__.lower()}_id"
        if not FLATTENED_OBJECT_SANITIZER.match(resolved_id) or resolved_id in BANNED_FIELDS:
            raise HowlerValueError(f"Illegal id_field name: {resolved_id}")

        definitions = self._field_definitions(model_type)
        for name in definitions:
            if not FIELD_SANITIZER.match(name) or name in BANNED_FIELDS:
                raise HowlerValueError(f"Illegal variable name: {name}")

        if (
            id_field is not None
            and id_field not in definitions
            and id_field
            not in self.flat_fields(
                model_type,
                show_compound=True,
            )
        ):
            raise HowlerValueError(f"id_field must reference a declared field: {id_field}")

        self._models[model_type] = ModelMetadata(
            name=model_type.__name__,
            description=description if description is not None else model_type.__doc__,
            id_field=resolved_id,
            index=index,
            store=store,
            embedded=embedded,
        )
        return model_type

    def metadata(self, model_type: type[BaseModel]) -> ModelMetadata:
        """Return model metadata, registering embedded models on demand."""
        if model_type not in self._models:
            self.register(model_type, embedded=True)
        return self._models[model_type]

    def fields(self, model_type: type[BaseModel]) -> dict[str, FieldDefinition]:
        """Return the canonical top-level field definitions."""
        return self._field_definitions(model_type)

    def flat_fields(
        self,
        model_type: type[BaseModel],
        *,
        show_compound: bool = False,
        skip_mappings: bool = False,
    ) -> dict[str, FieldDefinition]:
        """Return field definitions keyed by dotted storage path."""
        output: dict[str, FieldDefinition] = {}
        for definition in self._field_definitions(model_type).values():
            self._flatten_definition(
                definition,
                output,
                show_compound=show_compound,
                skip_mappings=skip_mappings,
            )
        return output

    def mapping(self, model_type: type[BaseModel]) -> dict[str, Any]:
        """Return the DSL-generated Elasticsearch mapping."""
        document_type = getattr(model_type, "_doc", None)
        if document_type is None:
            raise HowlerTypeError(f"{model_type.__name__} is not an Elasticsearch document model")
        mapping = deepcopy(document_type._doc_type.mapping.to_dict())
        properties = mapping.setdefault("properties", {})
        for definition in self.flat_fields(model_type).values():
            self._apply_field_mapping(properties, definition)
        if any(
            definition.metadata is not None and definition.metadata.kind == "Classification"
            for definition in self.fields(model_type).values()
        ):
            mapping.setdefault("properties", {}).update(
                {name: dict(field_mapping) for name, field_mapping in ACCESS_FIELD_MAPPINGS.items()}
            )
        return mapping

    def clear(self) -> None:
        """Clear registrations, primarily for isolated tests."""
        self._models.clear()

    def _field_definitions(self, model_type: type[BaseModel]) -> dict[str, FieldDefinition]:
        definitions: dict[str, FieldDefinition] = {}
        model_defaults = self._models.get(model_type)
        for python_name, info in model_type.model_fields.items():
            if python_name == "meta":
                continue
            name = info.serialization_alias or info.alias or python_name.rstrip("_")
            metadata = field_metadata(info.annotation, info.metadata)
            metadata = _resolve_metadata(metadata, model_defaults)
            definitions[name] = self._definition(name, name, info, metadata)
        return definitions

    @staticmethod
    def _apply_field_mapping(properties: dict[str, Any], definition: FieldDefinition) -> None:
        metadata = definition.metadata
        if metadata is None or metadata.index is None:
            return

        current = properties
        field_mapping: dict[str, Any] | None = None
        for component in definition.path.split("."):
            candidate = current.get(component)
            if not isinstance(candidate, dict):
                return
            field_mapping = candidate
            nested = candidate.get("properties")
            current = nested if isinstance(nested, dict) else {}

        if field_mapping is None or field_mapping.get("type") in {"object", "nested"}:
            return
        field_mapping["index"] = metadata.index
        if field_mapping.get("type", "text") != "text":
            field_mapping["doc_values"] = metadata.index

    @staticmethod
    def _definition(
        name: str,
        path: str,
        info: FieldInfo,
        metadata: HowlerFieldMetadata | None,
        *,
        annotation: Any | None = None,
        multivalued: bool = False,
        compound_model: type[BaseModel] | None = None,
    ) -> FieldDefinition:
        return FieldDefinition(
            name=name,
            path=path,
            annotation=info.annotation if annotation is None else annotation,
            metadata=metadata,
            required=info.is_required(),
            default=None if info.default is PydanticUndefined else info.default,
            default_factory=info.default_factory,
            description=info.description,
            multivalued=multivalued,
            compound_model=compound_model,
        )

    def _flatten_definition(
        self,
        definition: FieldDefinition,
        output: dict[str, FieldDefinition],
        *,
        show_compound: bool,
        skip_mappings: bool,
    ) -> None:
        annotation = unwrap_annotation(definition.annotation)
        origin = get_origin(annotation)
        is_list = origin is list
        child_annotation = get_args(annotation)[0] if is_list else annotation
        child_model = model_annotation(child_annotation)

        if child_model is not None:
            if show_compound:
                output[definition.path] = replace(
                    definition,
                    multivalued=definition.multivalued or is_list,
                    compound_model=child_model,
                )
            for child in self._field_definitions(child_model).values():
                nested = replace(
                    child,
                    path=f"{definition.path}.{child.name}",
                    metadata=_resolve_metadata(child.metadata, definition.metadata),
                    multivalued=definition.multivalued or is_list or child.multivalued,
                )
                self._flatten_definition(
                    nested,
                    output,
                    show_compound=show_compound,
                    skip_mappings=skip_mappings,
                )
            return

        metadata = definition.metadata
        if is_list:
            metadata = _resolve_metadata(field_metadata(child_annotation), metadata) or metadata
        if (
            skip_mappings
            and metadata is not None
            and metadata.kind
            in {
                "Mapping",
                "FlattenedObject",
                "FlattenedListObject",
            }
        ):
            return
        output[definition.path] = replace(
            definition,
            annotation=child_annotation if is_list else annotation,
            metadata=metadata,
            multivalued=definition.multivalued or is_list,
        )


model_registry = ModelRegistry()


def register_model(
    *,
    description: str | None = None,
    id_field: str | None = None,
    index: bool | None = None,
    store: bool | None = None,
    embedded: bool = False,
):
    """Register a model with its legacy-compatible defaults."""

    def decorator(model_type: type[BaseModel]) -> type[BaseModel]:
        return model_registry.register(
            model_type,
            description=description,
            id_field=id_field,
            index=index,
            store=store,
            embedded=embedded,
        )

    return decorator
