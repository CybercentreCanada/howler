"""Howler-owned Pydantic base models, partial projection helpers, and error translation."""

from __future__ import annotations

import copy
import types
from datetime import datetime
from typing import Annotated, Any, ClassVar, Literal, TypeVar, Union, cast, get_args, get_origin

from pydantic import (
    AliasGenerator,
    BaseModel,
    ConfigDict,
    Field,
    SerializationInfo,
    SerializerFunctionWrapHandler,
    TypeAdapter,
    ValidationError,
    ValidationInfo,
    field_validator,
    model_serializer,
    model_validator,
)
from pydantic_core import PydanticUndefined
from typing_extensions import Self

from howler.common.exceptions import HowlerValueError
from howler.models.fields import (
    DEFAULT_WHEN_BY_KIND,
    FIELD_SANITIZER,
    NOT_INDEXED_SANITIZER,
    NULL_EMPTY_KEYWORD_KINDS,
    ClassificationValue,
    _make_annotated,
    format_datetime,
)
from howler.models.registry import field_metadata, model_annotation, unwrap_annotation

ModelType = TypeVar("ModelType", bound=BaseModel)
ADAPTER_CONFIG = ConfigDict(arbitrary_types_allowed=True)
ACCESS_FIELDS = {
    "__access_lvl__",
    "__access_req__",
    "__access_grp1__",
    "__access_grp2__",
}
SYNTHETIC_SOURCE_FIELDS = {*ACCESS_FIELDS, "id", "__index"}


class ESMeta(BaseModel):
    """Metadata items associated with Elasticsearch documents."""

    id: str = ""
    index: str = ""
    primary_term: int = 0
    seq_no: int = 0
    version: int = 0
    score: float = 0.0


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


def _is_nullable_annotation(annotation: Any) -> bool:
    metadata = field_metadata(annotation)
    if metadata is not None and metadata.optional:
        return True
    return _annotation_includes_none(annotation)


def _annotation_includes_none(annotation: Any) -> bool:
    current = annotation
    while get_origin(current) is Annotated:
        current = get_args(current)[0]
    origin = get_origin(current)
    return origin in (Union, types.UnionType) and type(None) in get_args(current)


def _contains_list_container(annotation: Any) -> bool:
    unwrapped = unwrap_annotation(annotation)
    origin = get_origin(unwrapped)
    if origin is list:
        return True
    if origin is dict:
        args = get_args(unwrapped)
        return len(args) == 2 and _contains_list_container(args[1])
    return False


def _normalize_list_inputs(annotation: Any, value: Any) -> Any:
    unwrapped = unwrap_annotation(annotation)
    origin = get_origin(unwrapped)
    if value is None:
        # Optional list fields without None in their annotation treat null input as empty.
        return [] if origin is list and not _annotation_includes_none(annotation) else None
    if origin is list:
        child_annotation = get_args(unwrapped)[0]
        if isinstance(value, dict) and model_annotation(child_annotation) is not None:
            value = _expand_compound_list(value)
        if isinstance(value, list) and _contains_list_container(child_annotation):
            return [_normalize_list_inputs(child_annotation, item) for item in value]
        return value
    if origin is dict and isinstance(value, dict):
        args = get_args(unwrapped)
        if len(args) == 2 and _contains_list_container(args[1]):
            return {k: _normalize_list_inputs(args[1], item) for k, item in value.items()}
    return value


def _normalize_scalar_input(
    annotation: Any,
    value: Any,
    *,
    default: Any = PydanticUndefined,
    default_factory: Any = None,
) -> Any:
    metadata = field_metadata(annotation)
    kind = metadata.kind if metadata else None
    is_nullable = _is_nullable_annotation(annotation)
    has_non_null_default = default_factory is not None or (default is not PydanticUndefined and default is not None)

    if is_nullable:
        if value is None:
            return None
        if not has_non_null_default and kind in NULL_EMPTY_KEYWORD_KINDS and value == "":
            return None

    if has_non_null_default and kind in DEFAULT_WHEN_BY_KIND and DEFAULT_WHEN_BY_KIND[kind](value):
        return default_factory() if default_factory is not None else copy.deepcopy(default)

    return value


def _normalize_field_input(
    annotation: Any,
    value: Any,
    *,
    default: Any = PydanticUndefined,
    default_factory: Any = None,
) -> Any:
    value = _normalize_list_inputs(annotation, value)
    return _normalize_scalar_input(annotation, value, default=default, default_factory=default_factory)


def _finalize_primitives(value: Any, *, strip_null: bool) -> Any:
    if isinstance(value, datetime):
        return format_datetime(value)
    if isinstance(value, ClassificationValue):
        return str(value)
    if isinstance(value, dict):
        return {
            key: _finalize_primitives(item, strip_null=strip_null)
            for key, item in value.items()
            if not (strip_null and item is None)
        }
    if isinstance(value, list):
        return [_finalize_primitives(item, strip_null=strip_null) for item in value]
    return value


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
    """Howler error wrapping a Pydantic validation error."""

    def __init__(self, error: ValidationError):
        self.errors = error.errors(include_url=False)
        super().__init__(str(error), cause=error)


class HowlerModelMixin:
    """Shared strict input and primitive serialization behavior."""

    model_config = ConfigDict(
        alias_generator=AliasGenerator(serialization_alias=lambda name: name.rstrip("_")),
        arbitrary_types_allowed=True,
        extra="forbid",
        populate_by_name=True,
        use_attribute_docstrings=True,
        validate_assignment=True,
        validate_by_alias=True,
        validate_default=True,
        validate_by_name=True,
    )
    _include_index: ClassVar[bool] = False

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
            if key is None:
                continue
            full_annotation = _make_annotated(info.annotation, *info.metadata) if info.metadata else info.annotation
            nested[key] = _normalize_list_inputs(full_annotation, nested[key])
        return nested

    @field_validator("*", mode="before")
    @classmethod
    def _normalize_scalar_fields(cls, value: Any, info: ValidationInfo) -> Any:
        if not info.field_name or info.field_name == "meta":
            return value
        model_type = cast(type[BaseModel], cls)
        field_info = model_type.model_fields.get(info.field_name)
        if field_info is None:
            return value
        full_annotation = (
            _make_annotated(field_info.annotation, *field_info.metadata)
            if field_info.metadata
            else field_info.annotation
        )
        return _normalize_scalar_input(
            full_annotation,
            value,
            default=field_info.default,
            default_factory=field_info.default_factory,
        )

    @model_serializer(mode="wrap")
    def _serialize_model(self, handler: SerializerFunctionWrapHandler, info: SerializationInfo):  # noqa: ANN202
        output: dict[str, Any] = handler(self)
        context = info.context or {}
        output = {key: _finalize_primitives(value, strip_null=info.exclude_none) for key, value in output.items()}
        if context.get("hidden_fields") and isinstance(self, HowlerESModel):
            for python_name in type(self).model_fields:
                if python_name == "meta":
                    continue
                value = self.__dict__.get(python_name)
                if isinstance(value, ClassificationValue):
                    output.update(value.get_access_control_parts())
        if context.get("include_index") and type(self)._include_index:
            output["__index"] = type(self).__name__.lower()
        return output

    def __init__(self, /, **data: Any) -> None:
        try:
            super().__init__(**data)
        except ValidationError as error:
            raise HowlerModelValidationError(error) from error

    # Keep Pydantic's native schema validation path for nested models; only translate errors at the outer boundary.
    __init__.__pydantic_base_init__ = True  # type: ignore[attr-defined]

    def __setattr__(self, name: str, value: Any) -> None:
        try:
            super().__setattr__(name, value)
        except ValidationError as error:
            raise HowlerModelValidationError(error) from error

    @classmethod
    def model_validate(
        cls,
        obj: Any,
        *,
        strict: bool | None = None,
        extra: Literal["allow", "ignore", "forbid"] | None = None,
        from_attributes: bool | None = None,
        context: Any | None = None,
        by_alias: bool | None = None,
        by_name: bool | None = None,
    ) -> Self:
        """Validate data while exposing the Howler exception hierarchy."""
        try:
            validated = cast(Any, super()).model_validate(
                obj,
                strict=strict,
                extra=extra,
                from_attributes=from_attributes,
                context=context,
                by_alias=by_alias,
                by_name=by_name,
            )
            return cast(Self, validated)
        except ValidationError as error:
            raise HowlerModelValidationError(error) from error

    @classmethod
    def model_validate_json(
        cls,
        json_data: str | bytes | bytearray,
        *,
        strict: bool | None = None,
        extra: Literal["allow", "ignore", "forbid"] | None = None,
        context: Any | None = None,
        by_alias: bool | None = None,
        by_name: bool | None = None,
    ) -> Self:
        """Validate JSON data while exposing the Howler exception hierarchy."""
        try:
            validated = cast(Any, super()).model_validate_json(
                json_data,
                strict=strict,
                extra=extra,
                context=context,
                by_alias=by_alias,
                by_name=by_name,
            )
            return cast(Self, validated)
        except ValidationError as error:
            raise HowlerModelValidationError(error) from error

    @classmethod
    def model_validate_strings(
        cls,
        obj: Any,
        *,
        strict: bool | None = None,
        extra: Literal["allow", "ignore", "forbid"] | None = None,
        context: Any | None = None,
        by_alias: bool | None = None,
        by_name: bool | None = None,
    ) -> Self:
        """Validate string-encoded data while exposing the Howler exception hierarchy."""
        try:
            validated = cast(Any, super()).model_validate_strings(
                obj,
                strict=strict,
                extra=extra,
                context=context,
                by_alias=by_alias,
                by_name=by_name,
            )
            return cast(Self, validated)
        except ValidationError as error:
            raise HowlerModelValidationError(error) from error

    def as_primitives(self, *, hidden_fields: bool = False) -> dict[str, Any]:
        """Return the legacy stored/API primitive representation."""
        return cast(BaseModel, self).model_dump(
            by_alias=True,
            exclude_none=True,
            context={"hidden_fields": hidden_fields, "include_index": True},
        )

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


class HowlerESModel(HowlerModelMixin, BaseModel):
    """Base for top-level Howler Elasticsearch documents."""

    meta: ESMeta = Field(default_factory=ESMeta, exclude=True)


def _field_input_map(model_type: type[BaseModel]) -> dict[str, tuple[str, Any]]:
    fields: dict[str, tuple[str, Any]] = {}
    for python_name, info in model_type.model_fields.items():
        if python_name == "meta":
            continue
        for name in (python_name, info.alias, info.validation_alias, info.serialization_alias):
            if isinstance(name, str):
                fields[name] = (python_name, info)
    return fields


def _partial_value(
    annotation: Any,
    metadata: list[Any],
    value: Any,
    *,
    ignore_unknown: bool = False,
) -> Any:
    full_annotation = _make_annotated(annotation, *metadata) if metadata else annotation
    unwrapped = unwrap_annotation(full_annotation)
    origin = get_origin(unwrapped)

    extra_mode: Literal["ignore"] | None = "ignore" if ignore_unknown else None
    if origin is list:
        child_annotation = get_args(unwrapped)[0]
        child_model = model_annotation(child_annotation)
        if child_model is not None:
            if not isinstance(value, list):
                return TypeAdapter(full_annotation, config=ADAPTER_CONFIG).validate_python(value, extra=extra_mode)
            return [construct_partial(child_model, item, ignore_unknown=ignore_unknown) for item in value]

    embedded = model_annotation(unwrapped)
    if embedded is not None:
        if isinstance(value, dict):
            return construct_partial(embedded, value, ignore_unknown=ignore_unknown)
        return TypeAdapter(full_annotation).validate_python(value, extra=extra_mode)

    return TypeAdapter(full_annotation, config=ADAPTER_CONFIG).validate_python(value, extra=extra_mode)


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
        full_annotation = _make_annotated(info.annotation, *info.metadata) if info.metadata else info.annotation
        normalized = _normalize_scalar_input(
            full_annotation,
            value,
            default=info.default,
            default_factory=info.default_factory,
        )
        values[python_name] = _partial_value(
            info.annotation, list(info.metadata), normalized, ignore_unknown=ignore_unknown
        )
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
    nested = cast(dict[str, Any], cast(Any, model_type)._normalize_flat_input(data))
    for field in SYNTHETIC_SOURCE_FIELDS:
        if field not in fields:
            nested.pop(field, None)

    try:
        values = _partial_values(model_type, nested, ignore_unknown=ignore_unknown)
    except ValidationError as error:
        raise HowlerModelValidationError(error) from error

    if "meta" in model_type.model_fields:
        meta_info = model_type.model_fields["meta"]
        values["meta"] = TypeAdapter(cast(Any, meta_info.annotation)).validate_python(meta or {})
    # Supply placeholders so omitted defaults and factories are never evaluated.
    instance = model_type.model_construct(
        _fields_set=set(values), **{**dict.fromkeys(model_type.model_fields), **values}
    )
    instance_values = cast(dict[str, Any], object.__getattribute__(instance, "__dict__"))
    for python_name, info in model_type.model_fields.items():
        if python_name in values or info.default is None:
            continue
        instance_values.pop(python_name, None)
    return instance


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


def _field_annotation_for_path(model_type: type[BaseModel], path: str) -> tuple[Any, Any]:
    components = path.split(".")
    if not path or any(not component for component in components):
        raise ValueError(f"Invalid field for model: {path}")

    current: Any = model_type
    current_info: Any = None
    position = 0
    while position < len(components):
        full_annotation = current
        current = unwrap_annotation(full_annotation)
        if get_origin(current) is list:
            full_annotation = get_args(current)[0]
            current = unwrap_annotation(full_annotation)
            current_info = None

        if isinstance(current, type) and issubclass(current, BaseModel):
            entry = _field_input_map(current).get(components[position])
            if entry is None:
                raise ValueError(f"Invalid field for model: {path}")
            _, info = entry
            current = _make_annotated(info.annotation, *info.metadata) if info.metadata else info.annotation
            current_info = info
            position += 1
            if position == len(components):
                return current, current_info
            continue

        if get_origin(current) is dict:
            current = _mapping_value_annotation(full_annotation, components[position], path)
            current_info = None
            position += 1
            if position == len(components):
                return current, current_info
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

    full_annotation, field_info = _field_annotation_for_path(model_type, path)

    unwrapped = unwrap_annotation(full_annotation)
    if list_item and get_origin(unwrapped) is list:
        full_annotation = get_args(unwrapped)[0]
        field_info = None

    resolved = unwrap_annotation(full_annotation)
    if isinstance(resolved, type) and issubclass(resolved, BaseModel):
        return resolved.model_validate(value).model_dump(by_alias=True, exclude_none=True)

    value = _normalize_field_input(
        full_annotation,
        value,
        default=field_info.default if field_info is not None else PydanticUndefined,
        default_factory=field_info.default_factory if field_info is not None else None,
    )
    adapter = TypeAdapter(full_annotation, config=ADAPTER_CONFIG)
    try:
        validated = adapter.validate_python(value)
    except ValidationError as error:
        raise HowlerModelValidationError(error) from error
    if isinstance(validated, datetime):
        return validated.isoformat()
    return _finalize_primitives(adapter.dump_python(validated, by_alias=True, exclude_none=True), strip_null=True)


def _python_field_name(model_type: type[BaseModel], serialized_name: str) -> str:
    for python_name, info in model_type.model_fields.items():
        if serialized_name in (python_name, info.alias, info.serialization_alias):
            return python_name
    raise KeyError(serialized_name)
