"""Howler-owned wrappers around the Elasticsearch Pydantic integration."""

from __future__ import annotations

import copy
import types
from datetime import datetime, timezone
from typing import Annotated, Any, Literal, TypeVar, Union, cast, get_args, get_origin

from elasticsearch import dsl
from elasticsearch.dsl.pydantic import BaseESModel, BaseESModelMetaclass
from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError, model_validator
from typing_extensions import Self

from howler.common.exceptions import HowlerValueError
from howler.models.fields import (
    FIELD_SANITIZER,
    NOT_INDEXED_SANITIZER,
    ClassificationValue,
    _make_annotated,
    ip_to_primitive,
)
from howler.models.registry import annotation_metadata, field_metadata, model_annotation, unwrap_annotation

ModelType = TypeVar("ModelType", bound=BaseModel)
DATEFORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"
IPFormat = Literal["str", "int", "encoded_bytes"]
TimestampFormat = Literal["iso", "posix"]
ADAPTER_CONFIG = ConfigDict(arbitrary_types_allowed=True)
ACCESS_FIELDS = {
    "__access_lvl__",
    "__access_req__",
    "__access_grp1__",
    "__access_grp2__",
}
SYNTHETIC_SOURCE_FIELDS = {*ACCESS_FIELDS, "id", "__index"}


def flat_to_nested(data: dict[str, Any]) -> dict[str, Any]:
    """Convert dotted input keys to nested dictionaries."""
    nested: dict[str, Any] = {}
    for key, value in data.items():
        path = key.split(".")
        current = nested
        for component in path[:-1]:
            child = current.setdefault(component, {})
            if not isinstance(child, dict):
                child = {}
                current[component] = child
            current = child
        current[path[-1]] = value
    return nested


def _list_item_annotation(annotation: Any) -> Any | None:
    unwrapped = unwrap_annotation(annotation)
    return get_args(unwrapped)[0] if get_origin(unwrapped) is list else None


def _mapped_field_metadata(annotation: Any) -> dict[str, Any] | None:
    mapped_fields = [
        item
        for item in annotation_metadata(annotation)
        if isinstance(item, dict) and set(item) >= {"_field", "_es_name", "exclude"}
    ]
    if not mapped_fields:
        return None

    resolved = copy.deepcopy(mapped_fields[0])
    for mapped_field in mapped_fields[1:]:
        if resolved.get("_field") is None and mapped_field.get("_field") is not None:
            resolved["_field"] = copy.deepcopy(mapped_field["_field"])
        if resolved.get("_es_name") is None and mapped_field.get("_es_name") is not None:
            resolved["_es_name"] = mapped_field["_es_name"]
        resolved["exclude"] = resolved.get("exclude", False) or mapped_field.get("exclude", False)
    return resolved


def _compound_model(annotation: Any) -> tuple[type[BaseModel], bool] | None:
    unwrapped = unwrap_annotation(annotation)
    is_list = get_origin(unwrapped) is list
    if is_list:
        unwrapped = unwrap_annotation(get_args(unwrapped)[0])
    if isinstance(unwrapped, type) and issubclass(unwrapped, BaseModel):
        return unwrapped, is_list
    return None


def _dsl_annotation(metacls: Any, annotation: Any) -> Any:
    origin = get_origin(annotation)
    if origin is Annotated:
        annotation = get_args(annotation)[0]
        origin = get_origin(annotation)

    if origin in (Union, types.UnionType):
        members = get_args(annotation)
        concrete = [item for item in members if item is not type(None)]
        if len(concrete) == 1 and len(members) == 2:
            return _dsl_annotation(metacls, concrete[0]) | None

    if origin is list:
        return types.GenericAlias(list, (_dsl_annotation(metacls, get_args(annotation)[0]),))

    if origin is dict:
        key_type, value_type = get_args(annotation)
        return types.GenericAlias(
            dict,
            (
                _dsl_annotation(metacls, key_type),
                _dsl_annotation(metacls, value_type),
            ),
        )

    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return metacls.make_dsl_class(metacls, dsl.InnerDoc, annotation)
    return annotation


class HowlerESModelMetaclass(BaseESModelMetaclass):
    """Separate Pydantic validation annotations from DSL mapping annotations."""

    @staticmethod
    def make_dsl_class(
        metacls: Any,
        dsl_class: type,
        pydantic_model: type[BaseModel],
        pydantic_attrs: dict[str, Any] | None = None,
    ) -> type:
        """Generate DSL classes from Pydantic's resolved fields, including inherited fields."""
        dsl_attrs = {name: value for name, value in dsl_class.__dict__.items() if not name.startswith("__")}
        resolved_annotations = {
            name: _make_annotated(info.annotation, *info.metadata) if info.metadata else info.annotation
            for name, info in pydantic_model.model_fields.items()
        }
        attributes = {
            **(pydantic_attrs or {}),
            "__annotations__": metacls.process_annotations(metacls, resolved_annotations),
        }
        return type(dsl_class)(
            f"_ES{pydantic_model.__name__}",
            (dsl_class,),
            {
                **attributes,
                **dsl_attrs,
                "__qualname__": f"_ES{pydantic_model.__name__}",
            },
        )

    @staticmethod
    def process_annotations(
        metacls: Any,
        annotations: dict[str, Any],
    ) -> dict[str, Any]:
        """Return DSL-safe annotations while preserving explicit field mappings."""
        output: dict[str, Any] = {}
        for name, annotation in annotations.items():
            sanitized = _dsl_annotation(metacls, annotation)
            mapped_field = _mapped_field_metadata(annotation)
            compound = _compound_model(annotation)
            if compound is not None and not (mapped_field is not None and mapped_field.get("exclude")):
                model_type, is_list = compound
                inner_doc = metacls.make_dsl_class(metacls, dsl.InnerDoc, model_type)
                mapped_field = copy.deepcopy(mapped_field) if mapped_field is not None else dsl.mapped_field()
                mapped_field["_field"] = dsl.Object(inner_doc, multi=is_list)
            output[name] = _make_annotated(sanitized, mapped_field) if mapped_field is not None else sanitized
        return output


def _expand_compound_list(value: dict[str, Any]) -> list[dict[str, Any]]:
    flattened: dict[str, Any] = {}

    def flatten(data: dict[str, Any], prefix: str = "") -> None:
        for key, item in data.items():
            path = f"{prefix}.{key}" if prefix else key
            if isinstance(item, dict):
                flatten(item, path)
            else:
                flattened[path] = item

    flatten(value)
    expected_length: int | None = None
    output: list[dict[str, Any]] = []
    for path, item in flattened.items():
        values = item if isinstance(item, list) else [item]
        if expected_length is None:
            expected_length = len(values)
            output = [{} for _ in values]
        elif len(values) != expected_length:
            raise ValueError(
                f"Flattened fields creating lists of models must have equal lengths; {path} has {len(values)} "
                f"values instead of {expected_length}"
            )
        for index, child in enumerate(values):
            output[index][path] = child
    return [flat_to_nested(item) for item in output]


class HowlerModelValidationError(HowlerValueError):
    """Stable Howler error wrapping Pydantic's implementation-specific error."""

    def __init__(self, error: ValidationError):
        self.errors = error.errors(include_url=False)
        super().__init__(str(error), cause=error)


class HowlerModelMixin:
    """Shared strict input and primitive serialization behavior."""

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="forbid",
        populate_by_name=True,
        validate_assignment=True,
        validate_by_alias=True,
        validate_default=True,
        validate_by_name=True,
    )

    @model_validator(mode="before")
    @classmethod
    def _normalize_flat_input(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        nested = flat_to_nested(copy.deepcopy(value))
        model_type = cast(type[BaseModel], cls)
        for python_name, info in model_type.model_fields.items():
            if python_name == "meta":
                continue
            input_names = (info.validation_alias, info.alias, python_name)
            key = next(
                (candidate for candidate in input_names if isinstance(candidate, str) and candidate in nested),
                None,
            )
            if key is None or not isinstance(nested[key], dict):
                continue
            item_annotation = _list_item_annotation(info.annotation)
            if item_annotation is not None and model_annotation(item_annotation) is not None:
                nested[key] = _expand_compound_list(nested[key])
        return nested

    @classmethod
    def validate_howler(cls, data: Any) -> Self:
        """Validate data while exposing the stable Howler exception hierarchy."""
        model_type = cast(type[BaseModel], cls)
        try:
            return cast(Self, model_type.model_validate(data))
        except ValidationError as error:
            raise HowlerModelValidationError(error) from error

    def as_primitives(
        self,
        *,
        hidden_fields: bool = False,
        strip_null: bool = True,
        ip_format: Literal["str", "int", "encoded_bytes"] | None = None,
        timestamp_format: Literal["iso", "posix"] | None = None,
    ) -> dict[str, Any]:
        """Return the legacy stored/API primitive representation."""
        output: dict[str, Any] = {}
        model_type = cast(type[BaseModel], type(self))
        for python_name, info in model_type.model_fields.items():
            if python_name == "meta":
                continue
            if python_name not in self.__dict__:
                continue
            value = getattr(self, python_name)
            if value is None and strip_null:
                continue
            name = info.serialization_alias or info.alias or python_name.rstrip("_")
            output[name] = _primitive(
                value,
                info.annotation,
                info.metadata,
                strip_null=strip_null,
                ip_format=ip_format,
                timestamp_format=timestamp_format,
            )
            if hidden_fields and isinstance(value, ClassificationValue):
                output.update(value.get_access_control_parts())
        return output

    def __getitem__(self, name: str) -> Any:
        value: Any = self
        for component in name.split("."):
            if isinstance(value, BaseModel):
                field_name = _python_field_name(type(value), component)
                value = getattr(value, field_name)
            else:
                value = value[component]
        return value

    def __setitem__(self, name: str, value: Any) -> None:
        """Assign a declared field by dotted storage path."""
        target: Any = self
        components = name.split(".")
        for component in components[:-1]:
            if isinstance(target, BaseModel):
                target = getattr(target, _python_field_name(type(target), component))
            else:
                target = target[component]
        final = components[-1]
        if isinstance(target, BaseModel):
            setattr(target, _python_field_name(type(target), final), value)
        else:
            target[final] = value

    def get(self, name: str, default: Any = None) -> Any:
        """Return a field by dotted path or a default when absent."""
        try:
            return self[name]
        except (AttributeError, KeyError):
            return default

    def __contains__(self, name: str) -> bool:
        """Return whether a declared field exists on this model."""
        try:
            _python_field_name(cast(type[BaseModel], type(self)), name.rstrip("_"))
            return True
        except KeyError:
            return False


class HowlerEmbeddedModel(HowlerModelMixin, BaseModel):
    """Base for object and nested structures embedded in ES documents."""


class HowlerESModel(HowlerModelMixin, BaseESModel, metaclass=HowlerESModelMetaclass):
    """Base for top-level Howler Elasticsearch documents."""


def _field_input_map(model_type: type[BaseModel]) -> dict[str, tuple[str, Any]]:
    fields: dict[str, tuple[str, Any]] = {}
    for python_name, info in model_type.model_fields.items():
        if python_name == "meta":
            continue
        for name in (python_name, info.alias, info.validation_alias, info.serialization_alias):
            if isinstance(name, str):
                fields[name] = (python_name, info)
    return fields


def _partial_value(annotation: Any, metadata: list[Any], value: Any) -> Any:
    full_annotation = _make_annotated(annotation, *metadata) if metadata else annotation
    unwrapped = unwrap_annotation(full_annotation)
    origin = get_origin(unwrapped)

    if origin is list:
        child_annotation = get_args(unwrapped)[0]
        child_model = model_annotation(child_annotation)
        if child_model is not None:
            if not isinstance(value, list):
                return TypeAdapter(full_annotation, config=ADAPTER_CONFIG).validate_python(value)
            return [construct_partial(child_model, item) for item in value]

    embedded = model_annotation(unwrapped)
    if embedded is not None:
        if isinstance(value, dict):
            return construct_partial(embedded, value)
        return TypeAdapter(full_annotation).validate_python(value)

    return TypeAdapter(full_annotation, config=ADAPTER_CONFIG).validate_python(value)


def _partial_values(
    model_type: type[BaseModel],
    nested: dict[str, Any],
    *,
    ignore_unknown: bool,
) -> dict[str, Any]:
    fields = _field_input_map(model_type)
    values: dict[str, Any] = {}
    for input_name, value in nested.items():
        entry = fields.get(input_name)
        if entry is None:
            if ignore_unknown:
                continue
            raise ValueError(f"Unknown field for {model_type.__name__}: {input_name}")
        python_name, info = entry
        values[python_name] = _partial_value(info.annotation, list(info.metadata), value)
    return values


def construct_partial(
    model_type: type[ModelType],
    data: dict[str, Any],
    *,
    meta: dict[str, Any] | None = None,
    ignore_unknown: bool = False,
) -> ModelType:
    """Validate only fields present in a projected or partial document.

    Elasticsearch projections and field-scoped updates can legitimately omit required
    siblings. Each supplied registry field is still validated and coerced, but absent fields
    don't receive defaults and aren't required.
    """
    fields = _field_input_map(model_type)
    normalized = cast(Any, model_type)._normalize_flat_input(copy.deepcopy(data))
    nested = normalized if isinstance(normalized, dict) else flat_to_nested(copy.deepcopy(data))
    for field in SYNTHETIC_SOURCE_FIELDS:
        if field not in fields:
            nested.pop(field, None)

    try:
        values = _partial_values(model_type, nested, ignore_unknown=ignore_unknown)
    except ValidationError as error:
        raise HowlerModelValidationError(error) from error

    if "meta" in model_type.model_fields:
        meta_info = model_type.model_fields["meta"]
        values["meta"] = TypeAdapter(meta_info.annotation).validate_python(meta or {})
    instance = model_type.model_construct(_fields_set=set(values), **values)
    instance_values = cast(dict[str, Any], object.__getattribute__(instance, "__dict__"))
    for python_name, info in model_type.model_fields.items():
        if python_name in values or info.default is None:
            continue
        instance_values.pop(python_name, None)
    return instance


def strip_unknown_fields(model_type: type[BaseModel], data: dict[str, Any]) -> dict[str, Any]:
    """Drop undeclared stored fields while preserving typed compounds and mappings."""
    normalized = cast(Any, model_type)._normalize_flat_input(copy.deepcopy(data))
    nested = normalized if isinstance(normalized, dict) else flat_to_nested(copy.deepcopy(data))
    fields = _field_input_map(model_type)
    output: dict[str, Any] = {}

    for input_name, value in nested.items():
        entry = fields.get(input_name)
        if entry is None:
            continue
        python_name, info = entry
        serialized_name = info.serialization_alias or info.alias or python_name.rstrip("_")
        full_annotation = _make_annotated(info.annotation, *info.metadata) if info.metadata else info.annotation
        metadata = field_metadata(info.annotation, info.metadata)
        unwrapped = unwrap_annotation(full_annotation)
        child_model = model_annotation(unwrapped)

        if metadata is not None and metadata.kind in {"Mapping", "FlattenedObject", "FlattenedListObject", "Json"}:
            output[serialized_name] = value
        elif child_model is not None and isinstance(value, dict):
            output[serialized_name] = strip_unknown_fields(child_model, value)
        elif child_model is not None and isinstance(value, list):
            output[serialized_name] = [
                strip_unknown_fields(child_model, item) if isinstance(item, dict) else item for item in value
            ]
        else:
            output[serialized_name] = value

    return output


def partial_primitives(model_type: type[ModelType], data: dict[str, Any]) -> dict[str, Any]:
    """Validate and serialize only the fields supplied by a partial document."""
    return cast(HowlerModelMixin, construct_partial(model_type, data)).as_primitives(hidden_fields=True)


def _mapping_value_annotation(annotation: Any, component: str, path: str) -> Any:
    unwrapped = unwrap_annotation(annotation)
    args = get_args(unwrapped)
    metadata = field_metadata(annotation)
    sanitizer = (
        NOT_INDEXED_SANITIZER
        if metadata is not None and metadata.index is False and metadata.store is False
        else FIELD_SANITIZER
    )
    if (
        get_origin(unwrapped) is not dict
        or len(args) != 2
        or metadata is None
        or metadata.kind != "Mapping"
        or not sanitizer.fullmatch(component)
    ):
        raise ValueError(f"Invalid field for model: {path}")
    return args[1]


def _field_annotation_for_path(model_type: type[BaseModel], path: str) -> Any:
    components = path.split(".")
    if not path or any(not component for component in components):
        raise ValueError(f"Invalid field for model: {path}")

    current: Any = model_type
    position = 0
    while position < len(components):
        full_annotation = current
        current = unwrap_annotation(full_annotation)
        if get_origin(current) is list:
            full_annotation = get_args(current)[0]
            current = unwrap_annotation(full_annotation)

        if isinstance(current, type) and issubclass(current, BaseModel):
            entry = _field_input_map(current).get(components[position])
            if entry is None:
                raise ValueError(f"Invalid field for model: {path}")
            _, info = entry
            current = _make_annotated(info.annotation, *info.metadata) if info.metadata else info.annotation
            position += 1
            if position == len(components):
                return current
            continue

        if get_origin(current) is dict:
            current = _mapping_value_annotation(full_annotation, components[position], path)
            position += 1
            if position == len(components):
                return current
            continue

        break

    raise ValueError(f"Invalid field for model: {path}")


def validate_field_value(
    model_type: type[BaseModel],
    path: str,
    value: Any,
    *,
    list_item: bool = False,
) -> Any:
    """Validate one registered dotted field and return its stored primitive value."""
    if isinstance(value, BaseModel):
        value = value.model_dump(by_alias=True)
    elif hasattr(value, "as_primitives"):
        value = value.as_primitives()

    full_annotation = _field_annotation_for_path(model_type, path)

    unwrapped = unwrap_annotation(full_annotation)
    if list_item and get_origin(unwrapped) is list:
        full_annotation = get_args(unwrapped)[0]

    resolved = unwrap_annotation(full_annotation)
    if isinstance(resolved, type) and issubclass(resolved, BaseModel):
        validated = resolved.model_validate(value)
    else:
        validated = TypeAdapter(full_annotation, config=ADAPTER_CONFIG).validate_python(value)
    if isinstance(validated, datetime):
        return validated.isoformat()
    return _primitive(
        validated,
        full_annotation,
        strip_null=True,
        ip_format=None,
        timestamp_format=None,
    )


def _python_field_name(model_type: type[BaseModel], serialized_name: str) -> str:
    for python_name, info in model_type.model_fields.items():
        if serialized_name in (python_name, info.alias, info.serialization_alias):
            return python_name
    raise KeyError(serialized_name)


def _primitive(
    value: Any,
    annotation: Any,
    extra_metadata: list[Any] | None = None,
    *,
    strip_null: bool,
    ip_format: IPFormat | None,
    timestamp_format: TimestampFormat | None,
) -> Any:
    metadata = field_metadata(annotation, extra_metadata)
    if value is None:
        return None
    if isinstance(value, ClassificationValue):
        return str(value)
    if isinstance(value, datetime):
        if timestamp_format == "iso":
            return value.isoformat()
        if timestamp_format == "posix":
            return int(value.timestamp())
        normalized = value.astimezone(timezone.utc) if value.tzinfo is not None else value
        return normalized.strftime(DATEFORMAT)
    if metadata is not None and metadata.kind == "IP":
        return ip_to_primitive(value, ip_format)
    if isinstance(value, HowlerModelMixin):
        return value.as_primitives(
            strip_null=strip_null,
            ip_format=ip_format,
            timestamp_format=timestamp_format,
        )

    unwrapped = unwrap_annotation(annotation)
    origin = get_origin(unwrapped)
    args = get_args(unwrapped)
    if isinstance(value, list):
        child = args[0] if origin is list and args else Any
        return [
            _primitive(
                item,
                child,
                strip_null=strip_null,
                ip_format=ip_format,
                timestamp_format=timestamp_format,
            )
            for item in value
        ]
    if isinstance(value, dict):
        child = args[1] if origin is dict and len(args) > 1 else Any
        return {
            key: _primitive(
                item,
                child,
                strip_null=strip_null,
                ip_format=ip_format,
                timestamp_format=timestamp_format,
            )
            for key, item in value.items()
            if not (strip_null and item is None)
        }
    return value


class HowlerDocumentAdapter:
    """Stable adapter around Elasticsearch's Technical Preview conversion API."""

    @staticmethod
    def to_doc(model: HowlerESModel, *, hidden_fields: bool = True) -> dsl.Document:
        """Convert a model to a DSL document without relying on preview serialization semantics."""
        data = model.as_primitives(hidden_fields=hidden_fields)
        metadata = {
            f"_{key}": value for key, value in model.meta.model_dump().items() if value not in ("", 0, 0.0, None)
        }
        return model._doc(**metadata, **data)

    @staticmethod
    def from_doc(model_type: type[ModelType], document: dsl.Document) -> ModelType:
        """Build a model and metadata from a DSL document."""
        source = document.to_dict()
        for field in SYNTHETIC_SOURCE_FIELDS:
            source.pop(field, None)
        try:
            return model_type.model_validate(
                {
                    "meta": document.meta.to_dict(),
                    **source,
                }
            )
        except ValidationError as error:
            raise HowlerModelValidationError(error) from error


document_adapter = HowlerDocumentAdapter()
