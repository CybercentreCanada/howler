"""Canonical metadata registry for Pydantic/DSL models."""

from __future__ import annotations

import types
from collections.abc import Iterable
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Annotated, Any, Callable, Generic, TypeVar, Union, get_args, get_origin

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
_KEYWORD_DEFAULT: dict[str, Any] = {"type": "keyword", "ignore_above": 8191}
_KEYWORD_LOWER: dict[str, Any] = {"type": "keyword", "ignore_above": 8191, "normalizer": "lowercase_normalizer"}
KIND_MAPPING_PROPERTIES: dict[str, dict[str, Any]] = {
    "Any": {"type": "keyword", "index": False, "doc_values": False},
    "Boolean": {"type": "boolean"},
    "CaseInsensitiveKeyword": _KEYWORD_LOWER,
    "Classification": {"type": "keyword"},
    "ClassificationString": {"type": "keyword"},
    "Date": {"type": "date", "format": "date_optional_time||epoch_millis"},
    "Domain": _KEYWORD_DEFAULT,
    "Email": _KEYWORD_DEFAULT,
    "EmptyableKeyword": _KEYWORD_DEFAULT,
    "Enum": _KEYWORD_DEFAULT,
    "Float": {"type": "float"},
    "HowlerHash": _KEYWORD_LOWER,
    "IP": {"type": "ip"},
    "IndexText": {"type": "text"},
    "Integer": {"type": "integer"},
    "Json": _KEYWORD_DEFAULT,
    "Keyword": _KEYWORD_DEFAULT,
    "Long": {"type": "long"},
    "LowerKeyword": _KEYWORD_DEFAULT,
    "MAC": _KEYWORD_DEFAULT,
    "MD5": _KEYWORD_LOWER,
    "PhoneNumber": _KEYWORD_DEFAULT,
    "Platform": _KEYWORD_DEFAULT,
    "Processor": _KEYWORD_DEFAULT,
    "SHA1": _KEYWORD_LOWER,
    "SHA256": _KEYWORD_LOWER,
    "SSDeepHash": {"type": "text", "analyzer": "text_fuzzy"},
    "Text": {"type": "text"},
    "URI": _KEYWORD_DEFAULT,
    "URIPath": _KEYWORD_DEFAULT,
    "UUID": _KEYWORD_DEFAULT,
    "UpperKeyword": _KEYWORD_DEFAULT,
    "ValidatedKeyword": _KEYWORD_DEFAULT,
}
_PYTHON_TYPE_MAPPINGS: dict[Any, str] = {
    str: "text",
    int: "long",
    float: "float",
    bool: "boolean",
    datetime: "date",
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


def _snapshot(value: Any) -> Any:
    # Most metadata contains only immutable scalar/tuple options. Reuse it on the hot path.
    if isinstance(value, HowlerFieldMetadata) and deepcopy(value.options) is value.options:
        return value
    return deepcopy(value)


_T = TypeVar("_T")


class _DeclaredValue(Generic[_T]):
    """Keep mutable defaults and field options out of shared views without changing their public types."""

    def __set_name__(self, owner: type, name: str) -> None:
        self.storage = f"_declared_{name}"

    def __get__(self, instance: FieldDefinition | None, owner: type | None = None) -> _T:
        if instance is None:
            # A descriptor-typed dataclass field with no class default is a required constructor argument.
            raise AttributeError(self.storage)
        snapshot, copy_on_read = vars(instance)[self.storage]
        return deepcopy(snapshot) if copy_on_read else snapshot

    def __set__(self, instance: FieldDefinition, value: _T) -> None:
        snapshot = _snapshot(value)
        vars(instance)[self.storage] = (snapshot, snapshot is not value)


@dataclass(frozen=True, kw_only=True)
class FieldDefinition:
    """Canonical field view independent of Pydantic's internal structures."""

    name: str
    path: str
    annotation: _DeclaredValue[Any] = _DeclaredValue()
    metadata: _DeclaredValue[HowlerFieldMetadata | None] = _DeclaredValue()
    required: bool
    default: _DeclaredValue[Any] = _DeclaredValue()
    default_factory: Any
    description: str | None
    multivalued: bool = False
    compound_model: type[BaseModel] | None = None


def serialized_field_name(python_name: str, info: FieldInfo) -> str:
    """Return the field's name in serialized Howler documents."""
    return info.serialization_alias or info.alias or python_name.rstrip("_")


def annotation_metadata(annotation: Any, extra: list[Any] | None = None) -> list[Any]:
    """Return all metadata attached to nested Annotated/Optional annotations."""
    metadata = list(extra or [])
    origin = get_origin(annotation)
    if origin is Annotated:
        nested, *items = get_args(annotation)
        for item in items:
            metadata.append(item)
            if isinstance(item, FieldInfo):
                metadata.extend(item.metadata)
        metadata.extend(annotation_metadata(nested))
    elif origin is not None:
        for item in get_args(annotation):
            if item is not type(None):
                metadata.extend(annotation_metadata(item))
    return metadata


def _append_metadata_items(collected: list[HowlerFieldMetadata], items: Iterable[Any]) -> None:
    for item in items:
        if isinstance(item, HowlerFieldMetadata):
            collected.append(item)
        elif isinstance(item, FieldInfo):
            collected.extend(meta for meta in item.metadata if isinstance(meta, HowlerFieldMetadata))


def _layer_metadata(annotation: Any, extra: list[Any] | None = None) -> list[HowlerFieldMetadata]:
    """Collect HowlerFieldMetadata from innermost annotation layer to outermost."""
    collected: list[HowlerFieldMetadata] = []
    origin = get_origin(annotation)
    if origin is Annotated:
        nested, *items = get_args(annotation)
        collected.extend(_layer_metadata(nested))
        _append_metadata_items(collected, items)
    elif origin in (Union, types.UnionType):
        members = [item for item in get_args(annotation) if item is not type(None)]
        if len(members) == 1:
            collected.extend(_layer_metadata(members[0]))
    if extra:
        _append_metadata_items(collected, extra)
    return collected


def _merge_howler_metadata(layers: list[HowlerFieldMetadata]) -> HowlerFieldMetadata | None:
    if not layers:
        return None
    merged = layers[0]
    for outer in layers[1:]:
        explicit = outer._explicit
        merged = replace(
            merged,
            kind=outer.kind if outer.kind is not None else merged.kind,
            index=outer.index if outer.index is not None or "index" in explicit else merged.index,
            store=outer.store if outer.store is not None or "store" in explicit else merged.store,
            copy_to=outer.copy_to if outer.copy_to or "copy_to" in explicit else merged.copy_to,
            reference=outer.reference if outer.reference is not None or "reference" in explicit else merged.reference,
            deprecated=outer.deprecated if outer.deprecated or "deprecated" in explicit else merged.deprecated,
            deprecated_description=(
                outer.deprecated_description
                if outer.deprecated_description is not None or "deprecated_description" in explicit
                else merged.deprecated_description
            ),
            sync=outer.sync if (not outer.sync) or "sync" in explicit else merged.sync,
            options=outer.options if outer.options or "options" in explicit else merged.options,
            optional=outer.optional if outer.optional or "optional" in explicit else merged.optional,
            es_name=outer.es_name if outer.es_name is not None or "es_name" in explicit else merged.es_name,
            _explicit=merged._explicit | explicit,
        )
    return merged


def field_metadata(annotation: Any, extra: list[Any] | None = None) -> HowlerFieldMetadata | None:
    """Find and merge Howler field metadata across nested Annotated/Optional wrappers."""
    return _snapshot(_merge_howler_metadata(_layer_metadata(annotation, extra)))


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
    if defaults is None:
        return metadata
    if metadata is None:
        if defaults.index is None and defaults.store is None:
            return None
        return HowlerFieldMetadata(index=defaults.index, store=defaults.store)
    return replace(
        metadata,
        index=metadata.index if metadata.index is not None else defaults.index,
        store=metadata.store if metadata.store is not None else defaults.store,
    )


class ModelRegistry:
    """Registry exposing one stable view of model and field metadata."""

    def __init__(self) -> None:
        self._models: dict[type[BaseModel], ModelMetadata] = {}
        self._fields: dict[type[BaseModel], types.MappingProxyType[str, FieldDefinition]] = {}
        self._flat_fields: dict[tuple[type[BaseModel], bool, bool], types.MappingProxyType[str, FieldDefinition]] = {}

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

        if id_field is not None:
            root, *children = id_field.split(".")
            definition = definitions.get(root)
            for name in children:
                child = model_annotation(definition.annotation) if definition else None
                definition = self.fields(child).get(name) if child else None
            if definition is None:
                raise HowlerValueError(f"id_field must reference a declared field: {id_field}")

        self._models[model_type] = ModelMetadata(
            name=model_type.__name__,
            description=description if description is not None else model_type.__doc__,
            id_field=resolved_id,
            index=index,
            store=store,
            embedded=embedded,
        )
        # If this model has been traversed, it can also appear inside several cached parents.
        if self._fields.pop(model_type, None) is not None:
            self._flat_fields.clear()
        return model_type

    def register_derived(self, model_type: type[BaseModel], base_type: type[BaseModel]) -> type[BaseModel]:
        """Register a derived model while preserving inherited resolved metadata.

        The base model's already-resolved identifier is inherited without re-validating it as
        an explicit field declaration.
        """
        base_metadata = self.metadata(base_type)
        self.register(
            model_type,
            description=base_metadata.description,
            index=base_metadata.index,
            store=base_metadata.store,
            embedded=base_metadata.embedded,
        )
        self._models[model_type] = replace(self._models[model_type], id_field=base_metadata.id_field)
        return model_type

    def metadata(self, model_type: type[BaseModel]) -> ModelMetadata:
        """Return model metadata, registering embedded models on demand."""
        if model_type not in self._models:
            self.register(model_type, embedded=True)
        return self._models[model_type]

    def fields(self, model_type: type[BaseModel]) -> types.MappingProxyType[str, FieldDefinition]:
        """Return the read-only top-level field definitions."""
        if model_type not in self._fields:
            self._fields[model_type] = types.MappingProxyType(self._field_definitions(model_type))
        return self._fields[model_type]

    def flat_fields(
        self,
        model_type: type[BaseModel],
        *,
        show_compound: bool = False,
        skip_mappings: bool = False,
    ) -> dict[str, FieldDefinition]:
        """Return a caller-owned dictionary backed by the cached traversal's definitions."""
        return self.flat_field_view(model_type, show_compound=show_compound, skip_mappings=skip_mappings).copy()

    def flat_field_view(
        self, model_type: type[BaseModel], *, show_compound: bool = False, skip_mappings: bool = False
    ) -> types.MappingProxyType[str, FieldDefinition]:
        """Share a read-only traversal for this concrete model and flag combination."""
        key = (model_type, show_compound, skip_mappings)
        if key in self._flat_fields:
            return self._flat_fields[key]
        output: dict[str, FieldDefinition] = {}
        for definition in self.fields(model_type).values():
            self._flatten_definition(
                definition,
                output,
                show_compound=show_compound,
                skip_mappings=skip_mappings,
            )
        self._flat_fields[key] = types.MappingProxyType(output)
        return self._flat_fields[key]

    def mapping(self, model_type: type[BaseModel]) -> dict[str, Any]:
        """Return the Elasticsearch mapping derived from registered model metadata."""
        if "meta" not in model_type.model_fields:
            raise HowlerTypeError(f"{model_type.__name__} is not an Elasticsearch document model")
        properties = self._model_properties(model_type)
        if any(
            definition.metadata is not None and definition.metadata.kind == "Classification"
            for definition in self.fields(model_type).values()
        ):
            properties.update({name: dict(field_mapping) for name, field_mapping in ACCESS_FIELD_MAPPINGS.items()})
        return {"properties": properties}

    def clear(self) -> None:
        """Clear registrations, primarily for isolated tests."""
        self._models.clear()
        self._fields.clear()
        self._flat_fields.clear()

    def _field_definitions(self, model_type: type[BaseModel]) -> dict[str, FieldDefinition]:
        definitions: dict[str, FieldDefinition] = {}
        model_defaults = self._models.get(model_type)
        for python_name, info in model_type.model_fields.items():
            if python_name == "meta":
                continue
            name = serialized_field_name(python_name, info)
            if name in definitions or (name != python_name and name in model_type.model_fields):
                raise HowlerValueError(f"Duplicate serialized field name {name!r} on {model_type.__name__}")
            metadata = field_metadata(info.annotation, info.metadata)
            metadata = _resolve_metadata(metadata, model_defaults)
            definitions[name] = self._definition(name, name, info, metadata)
        return definitions

    def _model_properties(
        self,
        model_type: type[BaseModel],
        *,
        inherited_index: bool | None = None,
    ) -> dict[str, Any]:
        properties: dict[str, Any] = {}
        for definition in self.fields(model_type).values():
            metadata = definition.metadata
            effective_index = metadata.index if metadata is not None and metadata.index is not None else inherited_index
            storage_name = (metadata.es_name if metadata is not None and metadata.es_name is not None else None) or (
                definition.name
            )
            unwrapped = unwrap_annotation(definition.annotation)
            origin = get_origin(unwrapped)
            is_list = origin is list
            child_annotation = get_args(unwrapped)[0] if is_list else unwrapped
            child_model = model_annotation(child_annotation)

            if child_model is not None:
                properties[storage_name] = {
                    "type": "object",
                    "properties": self._model_properties(child_model, inherited_index=effective_index),
                }
                continue

            if (metadata is not None and metadata.kind in {"Mapping", "FlattenedObject", "FlattenedListObject"}) or (
                metadata is None and (unwrapped is dict or origin is dict)
            ):
                mapping_prop: dict[str, Any] = {"type": "object"}
                if effective_index is False:
                    mapping_prop["enabled"] = False
                properties[storage_name] = mapping_prop
                continue

            leaf_metadata = (
                _resolve_metadata(field_metadata(child_annotation), metadata) or metadata if is_list else metadata
            )
            leaf_index = (
                leaf_metadata.index
                if leaf_metadata is not None and leaf_metadata.index is not None
                else effective_index
            )
            if leaf_metadata is not None and leaf_metadata.kind in KIND_MAPPING_PROPERTIES:
                field_prop: dict[str, Any] = dict(KIND_MAPPING_PROPERTIES[leaf_metadata.kind])
            else:
                es_type = _PYTHON_TYPE_MAPPINGS.get(unwrap_annotation(child_annotation), "keyword")
                field_prop = {"type": es_type}

            if leaf_metadata is not None and leaf_metadata.copy_to:
                field_prop["copy_to"] = leaf_metadata.copy_to[0]
            if leaf_index is not None and (leaf_metadata is None or leaf_metadata.kind != "Any"):
                field_prop["index"] = leaf_index
                if field_prop.get("type", "text") != "text":
                    field_prop["doc_values"] = leaf_index
            properties[storage_name] = field_prop
        return properties

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
            for child in self.fields(child_model).values():
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
ModelT = TypeVar("ModelT", bound=BaseModel)


def register_model(
    *,
    description: str | None = None,
    id_field: str | None = None,
    index: bool | None = None,
    store: bool | None = None,
    embedded: bool = False,
) -> Callable[[type[ModelT]], type[ModelT]]:
    """Register a model with its legacy-compatible defaults."""

    def decorator(model_type: type[ModelT]) -> type[ModelT]:
        model_registry.register(
            model_type,
            description=description,
            id_field=id_field,
            index=index,
            store=store,
            embedded=embedded,
        )
        return model_type

    return decorator
