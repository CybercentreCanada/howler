import json
from collections.abc import Callable, Iterable, Mapping
from typing import Annotated, Any, Literal, Optional

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
    create_model,
    field_validator,
    model_validator,
)
from pydantic.fields import FieldInfo

from howler.odm.models.action import VALID_TRIGGERS

# Supplied to every operation by the dispatcher, never by the user
DISPATCHER_ARGUMENTS = frozenset(
    {
        "query",
        "user",
        "request_id",
        "auth_token",
        "bearer_token",
        "trusted_auth_token",
        "action_id",
        "trigger",
        "operation_id",
    }
)
MAX_LISTED_VALUES = 20


def one_of(name: str, values: Iterable[str] | Callable[[], Iterable[str]]) -> AfterValidator:
    """Restrict an argument to a fixed, or lazily computed, set of values.

    Args:
        name (str): The human readable name of the argument, used in error messages.
        values (Iterable[str] | Callable[[], Iterable[str]]): The allowed values, or a function returning them.

    Returns:
        AfterValidator: A validator to use in an ``Annotated`` argument type.
    """
    static_allowed = None if callable(values) else dict.fromkeys(values)

    def _check(value: Any) -> Any:
        if value is None:
            return value

        allowed = dict.fromkeys(values()) if callable(values) else static_allowed
        assert allowed is not None  # noqa: S101
        if value not in allowed:
            hint = f" Must be one of: {', '.join(allowed)}." if len(allowed) <= MAX_LISTED_VALUES else ""
            raise ValueError(f"'{value}' is not a valid {name}.{hint}")

        return value

    return AfterValidator(_check)


EmptyToNone = BeforeValidator(lambda value: None if value == "" else value)
NonEmptyStr = Annotated[str, Field(min_length=1)]


def format_validation_error(error: ValidationError) -> str:
    """Convert a pydantic validation error into a single line message.

    Args:
        error (ValidationError): The error raised by pydantic.

    Returns:
        str: A message listing each invalid argument and why it is invalid.
    """
    messages: list[str] = []
    for details in error.errors(include_url=False):
        location = ".".join(str(part) for part in details["loc"])
        cause = details.get("ctx", {}).get("error")

        if isinstance(cause, Exception):
            message = str(cause)
        else:
            message = details["msg"]
            if isinstance(details.get("input"), (str, int, float, bool)):
                message += f" (received {details['input']!r})"

        messages.append(f"{location}: {message}" if location else message)

    return "; ".join(messages)


def parse_data_json(
    data_json: Any,
    *,
    allow_empty: bool = True,
    forbid_dispatcher_args: bool = False,
) -> dict[str, Any]:
    """Parse an operation's raw JSON argument string into an argument dictionary."""
    if data_json is None or (allow_empty and data_json == ""):
        return {}

    if not isinstance(data_json, str):
        raise ValueError("data_json must be a JSON string containing an object.")  # noqa: TRY004

    try:
        parsed = json.loads(data_json)
    except json.JSONDecodeError as e:
        raise ValueError(f"data_json must be valid JSON: {e.msg}.") from e

    if not isinstance(parsed, dict):
        raise ValueError("data_json must be a JSON object.")  # noqa: TRY004

    if forbid_dispatcher_args and (reserved := DISPATCHER_ARGUMENTS & set(parsed)):
        raise ValueError(
            "; ".join(f"{key}: Extra inputs are not permitted (received {parsed[key]!r})" for key in sorted(reserved))
        )

    return parsed


def invalid_arguments_report(query: str, error: ValidationError | str) -> dict[str, str]:
    """Build the report entry returned when an operation is executed with invalid arguments."""
    message = format_validation_error(error) if isinstance(error, ValidationError) else error
    return {
        "query": f"({query})",
        "outcome": "error",
        "title": "Invalid Arguments",
        "message": message,
    }


class ActionArguments(BaseModel):
    """Base class for the user-supplied arguments of an action operation."""

    model_config = ConfigDict(extra="forbid")


class ActionDescription(BaseModel):
    """The descriptions of an operation shown to users."""

    short: str = Field(description="A one line summary of the operation.")
    long: Optional[str] = Field(default=None, description="A detailed description of the operation.")


class StepValidationRule(BaseModel):
    """A query the UI runs to warn about or block an operation before executing it."""

    query: str = Field(description="The query to check. $<argument> is replaced by the value of that argument.")
    message: Optional[str] = Field(default=None, description="The message to show when the query matches.")


class ActionStep(BaseModel):
    """A group of arguments the UI asks for together."""

    model_config = ConfigDict(extra="allow")

    args: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Argument names, each mapped to the 'argument:value' conditions under which it is shown.",
    )
    optional_args: Optional[list[str]] = Field(
        default=None, description="Argument names that are displayed but not required by the UI."
    )
    options: dict[str, list[str] | dict[str, list[str]]] = Field(
        default_factory=dict,
        description="Allowed values per argument, either as a list or keyed by an 'argument:value' condition.",
    )
    validation: Optional[dict[Literal["warn", "error"], StepValidationRule]] = Field(
        default=None, description="Queries the UI uses to warn about or block execution."
    )

    @model_validator(mode="after")
    def _validate_options(self) -> "ActionStep":
        for name in self.options:
            if name not in self.args and name not in (self.optional_args or []):
                raise ValueError(f"Options are provided for '{name}', which is not an argument of the same step.")

        return self

    def validate_against(self, adapters: Mapping[str, TypeAdapter[Any]]) -> None:
        """Validate conditions and offered values against the specification's argument types."""
        for conditions in self.args.values():
            for condition in conditions:
                self._check_condition(condition, adapters)

        for name, options in self.options.items():
            if isinstance(options, dict):
                for condition, values in options.items():
                    self._check_condition(condition, adapters)
                    self._check_values(name, values, adapters[name])
            else:
                self._check_values(name, options, adapters[name])

    @staticmethod
    def _check_values(name: str, values: Iterable[str], adapter: TypeAdapter[Any]) -> None:
        for value in values:
            try:
                adapter.validate_python(value)
            except ValidationError as e:
                raise ValueError(
                    f"'{value}' is offered for '{name}' but is invalid: {format_validation_error(e)}"
                ) from e

    @classmethod
    def _check_condition(cls, condition: str, adapters: Mapping[str, TypeAdapter[Any]]) -> None:
        name, separator, value = condition.partition(":")
        if not separator or name not in adapters:
            raise ValueError(f"Condition '{condition}' must be in the form 'argument:value' for a known argument.")

        cls._check_values(name, [value], adapters[name])


def _field_adapter(field: FieldInfo) -> TypeAdapter[Any]:
    annotation = field.annotation
    if annotation is None:
        raise ValueError("Action argument field must have an annotation.")

    if not field.metadata:
        return TypeAdapter(annotation)

    return TypeAdapter(Annotated[(annotation, *field.metadata)])  # type: ignore


class ActionSpecification(BaseModel):
    """Describes an operation to the UI, and validates the arguments it is executed with."""

    # Unknown keys are passed through to the UI unchanged
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str = Field(min_length=1, description="The ID of the operation.")
    title: str = Field(min_length=1, description="The title to show when no localization is available.")
    priority: Optional[int] = Field(default=None, description="The ordering priority of the operation in the UI.")
    i18n_key: Optional[str] = Field(
        default=None,
        validation_alias="i18nKey",
        serialization_alias="i18nKey",
        description="The localization key used by the UI.",
    )
    description: ActionDescription = Field(description="The descriptions of the operation.")
    roles: list[str] = Field(min_length=1, description="The roles allowed to run the operation.")
    requires_auth_token: Optional[bool] = Field(
        default=None, description="Whether the operation receives the caller's bearer token."
    )
    steps: list[ActionStep] = Field(default_factory=list, description="The arguments to ask for, grouped in steps.")
    triggers: list[str] = Field(default_factory=list, description="The events that can trigger the operation.")
    arguments: Annotated[
        type[ActionArguments],
        BeforeValidator(lambda value: ActionArguments if value is None else value),
    ] = Field(
        default=ActionArguments,
        exclude=True,
        description="The model validating the arguments, if the operation accepts any.",
    )

    @field_validator("triggers")
    @classmethod
    def _validate_triggers(cls, value: list[str]) -> list[str]:
        if invalid := set(value) - set(VALID_TRIGGERS):
            raise ValueError(f"Invalid trigger(s) provided: {', '.join(sorted(invalid))}")

        return value

    @model_validator(mode="after")
    def _validate_arguments_model(self) -> "ActionSpecification":
        fields = self.arguments.model_fields

        if reserved := DISPATCHER_ARGUMENTS & set(fields):
            raise ValueError(f"The arguments model declares reserved argument(s): {', '.join(sorted(reserved))}.")

        step_args = {name for step in self.steps for name in (*step.args, *(step.optional_args or []))}
        if missing := step_args - set(fields):
            raise ValueError(f"Step argument(s) missing from the arguments model: {', '.join(sorted(missing))}.")

        if hidden := set(fields) - step_args:
            raise ValueError(f"Argument(s) not included in any step: {', '.join(sorted(hidden))}.")

        adapters = {name: _field_adapter(field) for name, field in fields.items()}
        for step in self.steps:
            step.validate_against(adapters)

        return self

    @classmethod
    def from_legacy(cls, specification: Mapping[str, Any]) -> "ActionSpecification":
        """Build a specification from the dict format, deriving allowed argument names from its steps."""
        steps = TypeAdapter(list[ActionStep]).validate_python(specification.get("steps", []))
        field_definitions: dict[str, Any] = {}
        for step in steps:
            for arg_name in (*step.args, *(step.optional_args or [])):
                if not arg_name.startswith("_"):
                    field_definitions[arg_name] = (Any, None)

        spec_id = specification.get("id")
        model_name = f"{spec_id}_Arguments" if isinstance(spec_id, str) and spec_id else "InferredActionArguments"
        arguments_model: type[ActionArguments] = create_model(
            model_name,
            __base__=ActionArguments,
            **field_definitions,
        )
        return cls.model_validate({**specification, "steps": steps, "arguments": arguments_model})

    def validate_arguments(self, data: Mapping[str, Any]) -> ActionArguments:
        """Validate the arguments an operation is executed with."""
        return self.arguments.model_validate(dict(data))

    def to_ui_dict(self) -> dict[str, Any]:
        """Serialize the specification in the format expected by the UI."""
        return self.model_dump(mode="json", by_alias=True, exclude_none=True)
