"""Howler-owned Pydantic base models, partial projection helpers, and error translation."""

from __future__ import annotations

import copy
from collections.abc import Mapping
from datetime import datetime
from typing import Any, ClassVar, Literal, TypeVar, cast, get_args, get_origin

from pydantic import (
    AliasGenerator,
    BaseModel,
    ConfigDict,
    Field,
    SerializationInfo,
    SerializerFunctionWrapHandler,
    TypeAdapter,
    ValidationError,
    model_serializer,
    model_validator,
)
from typing_extensions import Self

from howler.common.exceptions import HowlerValueError
from howler.models.fields import (
    FIELD_SANITIZER,
    NOT_INDEXED_SANITIZER,
    ClassificationValue,
    _make_annotated,
    format_datetime,
)
from howler.models.registry import field_metadata, model_annotation, serialized_field_name, unwrap_annotation

ModelType = TypeVar("ModelType", bound=BaseModel)
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


def _list_item_annotation(annotation: Any) -> Any | None:
    unwrapped = unwrap_annotation(annotation)
    return get_args(unwrapped)[0] if get_origin(unwrapped) is list else None


def _finalize_primitives(
    value: Any,
    *,
    strip_null: bool,
    timestamp_format: TimestampFormat | None,
) -> Any:
    if isinstance(value, datetime):
        return format_datetime(value, timestamp_format)
    if isinstance(value, ClassificationValue):
        return str(value)
    if isinstance(value, dict):
        return {
            key: _finalize_primitives(item, strip_null=strip_null, timestamp_format=timestamp_format)
            for key, item in value.items()
            if not (strip_null and item is None)
        }
    if isinstance(value, list):
        return [_finalize_primitives(item, strip_null=strip_null, timestamp_format=timestamp_format) for item in value]
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
    """Stable Howler error wrapping Pydantic's implementation-specific error."""

    def __init__(self, error: ValidationError, model_type: type[BaseModel] | None = None):
        self.errors = error.errors(include_url=False)
        root_name = model_type.__name__ if model_type is not None else error.title
        messages: list[str] = []
        for item in self.errors:
            try:
                location = _public_error_location(model_type, root_name, item.get("loc", ()))
            except Exception:
                location = root_name.lower()
            try:
                detail = _public_error_message(item)
            except Exception:
                detail = "Invalid value"
            messages.append(f"[{location}] {detail}")
        message = "\n".join(messages)
        super().__init__(message, cause=error)


def _public_error_location(
    model_type: type[BaseModel] | None,
    root_name: str,
    location: tuple[Any, ...] | list[Any],
) -> str:
    """Translate Pydantic locations to stable Howler serialized field paths."""
    components = [root_name.lower()]
    current: Any = model_type
    position = 0

    while position < len(location):
        token = location[position]
        unwrapped = unwrap_annotation(current) if current is not None else None
        origin = get_origin(unwrapped)
        arguments = get_args(unwrapped)

        if isinstance(unwrapped, type) and issubclass(unwrapped, BaseModel) and isinstance(token, str):
            field_entry = _field_input_map(unwrapped).get(token)
            if field_entry is not None:
                python_name, info = field_entry
                components.append(serialized_field_name(python_name, info))
                current = info.annotation
                position += 1
                continue

        if origin is list and isinstance(token, int) and arguments:
            components.append(str(token))
            current = arguments[0]
            position += 1
            continue

        if origin is dict and len(arguments) == 2:
            components.append(str(token))
            current = arguments[1]
            position += 1
            continue

        components.append(str(token))
        position += 1

    return ".".join(components)


def _public_error_message(error: Mapping[str, Any]) -> str:
    """Return an input-free, stable explanation selected by Pydantic's error type."""
    error_type = error.get("type")
    if not isinstance(error_type, str):
        return "Invalid value"

    if error_type == "value_error":
        message = error.get("msg")
        static_domain_messages = {
            "Rule timeframe must be a positive integer or None",
            "Rule cannot expire after resolved when no timeframe is set",
            "Case items must be root-level (parent must be null)",
            "Group cannot be an empty string",
            'Data "group" should be a slash-separated string.',
            "A group must consist of a relative path with no empty segments (e.g. a/b/c)",
            "One of your pivots has duplicate keys set.",
        }
        for safe_message in static_domain_messages:
            if message == f"Value error, {safe_message}":
                return safe_message
        if message == "Value error, Empty strings are not allowed without defaults":
            return "Empty strings are not allowed without defaults"
        if isinstance(message, str) and message.startswith(
            "Value error, If no explanation provided, you must provide the following values: "
        ):
            return "An explanation or complete change details are required"
        return "Invalid value"

    messages: dict[str, str] = {
        "missing": "Field required",
        "extra_forbidden": "Extra inputs are not permitted",
        "int_type": "Input should be a valid integer",
        "int_parsing": "Input should be a valid integer",
        "int_from_float": "Input should be a valid integer",
        "float_type": "Input should be a valid number",
        "float_parsing": "Input should be a valid number",
        "finite_number": "Input should be a finite number",
        "string_type": "Input should be a valid string",
        "bool_type": "Input should be a valid boolean",
        "bool_parsing": "Input should be a valid boolean",
        "list_type": "Input should be a valid list",
        "tuple_type": "Input should be a valid tuple",
        "dict_type": "Input should be a valid dictionary",
        "set_type": "Input should be a valid set",
        "model_type": "Input should be a valid object",
        "model_attributes_type": "Input should be a valid object",
    }
    return messages.get(error_type, "Invalid value")


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
            if key is None or not isinstance(nested[key], dict):
                continue
            item_annotation = _list_item_annotation(info.annotation)
            if item_annotation is not None and model_annotation(item_annotation) is not None:
                nested[key] = _expand_compound_list(nested[key])
        return nested

    @model_serializer(mode="wrap")
    def _serialize_model(self, handler: SerializerFunctionWrapHandler, info: SerializationInfo):  # noqa: ANN202
        output: dict[str, Any] = handler(self)
        context = info.context or {}
        timestamp_format = context.get("timestamp_format")
        output = {
            key: _finalize_primitives(
                value,
                strip_null=info.exclude_none,
                timestamp_format=timestamp_format,
            )
            for key, value in output.items()
        }
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
            raise HowlerModelValidationError(error, cast(type[BaseModel], type(self))) from error

    # Keep Pydantic's native schema validation path for nested models; only translate errors at the outer boundary.
    __init__.__pydantic_base_init__ = True  # type: ignore[attr-defined]

    def __setattr__(self, name: str, value: Any) -> None:
        try:
            super().__setattr__(name, value)
        except ValidationError as error:
            raise HowlerModelValidationError(error, cast(type[BaseModel], type(self))) from error

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
        """Validate data while exposing the stable Howler exception hierarchy."""
        model_type = cast(type[BaseModel], cls)
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
            raise HowlerModelValidationError(error, model_type) from error

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
        """Validate JSON data while exposing the stable Howler exception hierarchy."""
        model_type = cast(type[BaseModel], cls)
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
            raise HowlerModelValidationError(error, model_type) from error

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
        """Validate string-encoded data while exposing the stable Howler exception hierarchy."""
        model_type = cast(type[BaseModel], cls)
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
            raise HowlerModelValidationError(error, model_type) from error

    def as_primitives(
        self,
        *,
        hidden_fields: bool = False,
        strip_null: bool = True,
        ip_format: IPFormat | None = None,
        timestamp_format: TimestampFormat | None = None,
    ) -> dict[str, Any]:
        """Return the legacy stored/API primitive representation."""
        return cast(BaseModel, self).model_dump(
            by_alias=True,
            exclude_none=strip_null,
            context={
                "hidden_fields": hidden_fields,
                "include_index": True,
                "ip_format": ip_format,
                "timestamp_format": timestamp_format,
            },
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
        values[python_name] = _partial_value(info.annotation, list(info.metadata), value, ignore_unknown=ignore_unknown)
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
        raise HowlerModelValidationError(error, model_type) from error

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

    full_annotation = _field_annotation_for_path(model_type, path)

    unwrapped = unwrap_annotation(full_annotation)
    if list_item and get_origin(unwrapped) is list:
        full_annotation = get_args(unwrapped)[0]

    resolved = unwrap_annotation(full_annotation)
    if isinstance(resolved, type) and issubclass(resolved, BaseModel):
        return resolved.model_validate(value).model_dump(by_alias=True, exclude_none=True)

    adapter = TypeAdapter(full_annotation, config=ADAPTER_CONFIG)
    try:
        validated = adapter.validate_python(value)
    except ValidationError as error:
        raise HowlerModelValidationError(error, model_type) from error
    if isinstance(validated, datetime):
        return validated.isoformat()
    return _finalize_primitives(
        adapter.dump_python(validated, by_alias=True, exclude_none=True),
        strip_null=True,
        timestamp_format=None,
    )


def _python_field_name(model_type: type[BaseModel], serialized_name: str) -> str:
    for python_name, info in model_type.model_fields.items():
        if serialized_name in (python_name, info.alias, info.serialization_alias):
            return python_name
    raise KeyError(serialized_name)
