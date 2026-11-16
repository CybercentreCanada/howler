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
RESERVED_ARGUMENTS = frozenset({"query", "user", "request_id", "auth_token"})
DISPATCHER_ARGUMENTS = RESERVED_ARGUMENTS | {"operation_id"}
MAX_LISTED_VALUES = 20


def one_of(name: str, values: Iterable[str] | Callable[[], Iterable[str]]) -> AfterValidator:
    """Restrict an argument to a fixed, or lazily computed, set of values.

    Args:
        name (str): The human readable name of the argument, used in error messages.
        values (Iterable[str] | Callable[[], Iterable[str]]): The allowed values, or a function returning them.

    Returns:
        AfterValidator: A validator to use in an ``Annotated`` argument type.
    """

    def _check(value: Any) -> Any:
        if value is None:
            return value

        allowed = list(values() if callable(values) else values)
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


def format_action_validation_error(error: ValidationError) -> str:
    """Preserve legacy action API messages while using model validation."""
    messages: dict[tuple[tuple[int | str, ...], str], str] = {
        ((), "model_type"): "Incorrect data structure!",
        (("name",), "missing"): "You must specify a name.",
        (("query",), "missing"): "You must specify a query.",
        (("operations",), "missing"): "You must specify a list of operations.",
        (("operations",), "list_type"): "'operations' must be a list of operations.",
        (("operations",), "too_short"): "You must specify at least one operation.",
        (("triggers",), "value_error"): "Invalid trigger provided.",
    }
    for details in error.errors(include_url=False):
        location = details["loc"]
        if location in (("name",), ("query",)) and details["type"] != "missing" and not details.get("input"):
            return f"{str(location[0]).capitalize()} cannot be empty."

        if location == ("operations",) and details.get("input") is None:
            return "You must specify a list of operations."

        if message := messages.get((location, details["type"])):
            return message

    return format_validation_error(error)


def invalid_arguments_report(query: str, error: ValidationError) -> dict[str, str]:
    """Build the report entry returned when an operation is executed with invalid arguments."""
    return {
        "query": query,
        "outcome": "error",
        "title": "Invalid Arguments",
        "message": format_validation_error(error),
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
            if name not in self.args:
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
    steps: list[ActionStep] = Field(default_factory=list, description="The arguments to ask for, grouped in steps.")
    triggers: list[str] = Field(default_factory=list, description="The events that can trigger the operation.")
    arguments: Optional[type[ActionArguments]] = Field(
        default=None, exclude=True, description="The model validating the arguments, if the operation accepts any."
    )

    @field_validator("triggers")
    @classmethod
    def _validate_triggers(cls, value: list[str]) -> list[str]:
        if invalid := set(value) - set(VALID_TRIGGERS):
            raise ValueError(f"Invalid trigger(s) provided: {', '.join(sorted(invalid))}")

        return value

    @model_validator(mode="after")
    def _validate_arguments_model(self) -> "ActionSpecification":
        fields = (self.arguments or ActionArguments).model_fields

        if reserved := DISPATCHER_ARGUMENTS & set(fields):
            raise ValueError(f"The arguments model declares reserved argument(s): {', '.join(sorted(reserved))}.")

        step_args = {name for step in self.steps for name in step.args}
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
        """Build a specification from the dict format, deriving allowed argument names from its steps.

        Args:
            specification (Mapping[str, Any]): The dict specification returned by an operation.

        Returns:
            ActionSpecification: The specification, accepting only arguments declared in ``steps``.
        """
        field_definitions: dict[str, Any] = {}
        raw_steps = specification.get("steps")
        if isinstance(raw_steps, list):
            for raw_step in raw_steps:
                if isinstance(raw_step, ActionStep):
                    step_args: Any = raw_step.args
                elif isinstance(raw_step, Mapping):
                    step_args = raw_step.get("args")
                else:
                    step_args = None

                if not isinstance(step_args, Mapping):
                    continue

                for arg_name in step_args:
                    if isinstance(arg_name, str) and not arg_name.startswith("_") and arg_name not in field_definitions:
                        field_definitions[arg_name] = (Any, None)

        spec_id = specification.get("id")
        model_name = f"{spec_id}_Arguments" if isinstance(spec_id, str) and spec_id else "InferredActionArguments"
        arguments_model: type[ActionArguments] = create_model(
            model_name,
            __base__=ActionArguments,
            **field_definitions,
        )
        return cls.model_validate({**specification, "arguments": arguments_model})

    def validate_arguments(self, data: Mapping[str, Any]) -> ActionArguments:
        """Validate the arguments an operation is executed with.

        Args:
            data (Mapping[str, Any]): The arguments to validate.

        Raises:
            ValidationError: The arguments are invalid.

        Returns:
            ActionArguments: The validated arguments.
        """
        return (self.arguments or ActionArguments).model_validate(dict(data))

    def to_ui_dict(self) -> dict[str, Any]:
        """Serialize the specification in the format expected by the UI."""
        return self.model_dump(mode="json", by_alias=True, exclude_none=True)


class OperationModel(BaseModel):
    """Pydantic counterpart of the ``Operation`` ODM model."""

    operation_id: str = Field(min_length=1, description="The ID of the action.")
    data_json: Optional[str] = Field(
        default=None, description="The data necessary to execute the action, in raw JSON format."
    )

    @field_validator("data_json")
    @classmethod
    def _validate_data_json(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value

        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as e:
            raise ValueError(f"data_json must be valid JSON: {e.msg}") from e

        if not isinstance(parsed, dict):
            raise ValueError("data_json must be a JSON object.")  # noqa: TRY004

        return value

    @property
    def data(self) -> dict[str, Any]:
        """The parsed operation arguments."""
        return json.loads(self.data_json) if self.data_json else {}


class ActionModel(BaseModel):
    """Pydantic counterpart of the ``Action`` ODM model."""

    action_id: Optional[str] = Field(default=None, description="A UUID for this action")
    name: str = Field(min_length=1, description="The name of the action.")
    query: str = Field(min_length=1, description="The query this action is run against.")
    triggers: list[str] = Field(default_factory=list, description="A list of events for which trigger this action")
    operations: list[OperationModel] = Field(
        min_length=1, description="A list of the operations this action consists of."
    )
    owner: Optional[str] = Field(default=None, description="The person owning the object.")
    admins: list[str] = Field(default_factory=list, description="The group administrator for this object.")
    members: list[str] = Field(default_factory=list, description="The group who can modify the object.")

    @field_validator("triggers")
    @classmethod
    def _validate_triggers(cls, value: list[str]) -> list[str]:
        if invalid := set(value) - set(VALID_TRIGGERS):
            raise ValueError(f"Invalid trigger(s) provided: {', '.join(sorted(invalid))}")

        return value

    @model_validator(mode="after")
    def _validate_unique_operations(self) -> "ActionModel":
        operation_ids = [operation.operation_id for operation in self.operations]
        if len(operation_ids) != len(set(operation_ids)):
            raise ValueError("You must have a maximum of one operation of each type in the action.")

        return self
