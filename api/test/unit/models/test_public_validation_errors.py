"""Public formatting for Howler model validation errors."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel, Field, ValidationError

import howler.models.base as model_base
from howler.models import HowlerEmbeddedModel, HowlerModelValidationError
from howler.models.event import Event
from howler.models.hit import Hit
from howler.models.template import Template

VALID_HASH = "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bc"
VALID_UUID = "e1e5a200-d413-4c82-9b33-dc8fc232bcaf"


class AliasedValidationLeaf(HowlerEmbeddedModel):
    """A field model with input and serialized names that differ."""

    value_: int = Field(alias="wire_value", serialization_alias="value")
    metadata_: dict[str, int] = Field(default_factory=dict, alias="wire_metadata", serialization_alias="metadata")


class AliasedValidationRoot(HowlerEmbeddedModel):
    """A model used to verify alias and container error locations."""

    entries: list[AliasedValidationLeaf] = Field(alias="wire_entries", serialization_alias="records")


class DeepInputModel(BaseModel):
    """A small native model for deep-error-input formatter tests."""

    value: int


def test_hit_missing_analytic_keeps_structured_error_and_public_root_path() -> None:
    """The wrapper retains Pydantic details but exposes the stable Howler field path."""
    with pytest.raises(HowlerModelValidationError) as raised:
        Hit.validate_howler({"howler": {"hash": VALID_HASH}})

    public_error = raised.value
    assert str(public_error).startswith("[hit.howler.analytic] Field required")
    assert isinstance(public_error.cause, ValidationError)
    assert public_error.__cause__ is public_error.cause
    assert public_error.errors == public_error.cause.errors(include_url=False)


def test_hit_invalid_score_does_not_echo_original_input() -> None:
    """Invalid scalar messages stay meaningful without disclosing submitted values."""
    secret_input = "DO_NOT_LEAK_SCORE_VALUE"

    with pytest.raises(HowlerModelValidationError) as raised:
        Hit.validate_howler({"howler": {"analytic": "test", "hash": VALID_HASH, "score": secret_input}})

    message = str(raised.value)
    assert message.startswith("[hit.howler.score] ")
    assert message == "[hit.howler.score] Invalid value"
    assert secret_input not in message
    assert secret_input == raised.value.errors[0]["input"]


@pytest.mark.parametrize("secret_input", ["SECRET  TOKEN", f"{'3141592653' * 500}x"])
def test_value_errors_never_echo_whitespace_or_long_numeric_inputs(secret_input: str) -> None:
    """Validation messages do not render or normalize user-provided scalar data."""
    with pytest.raises(HowlerModelValidationError) as raised:
        Hit.validate_howler({"howler": {"analytic": "test", "hash": VALID_HASH, "score": secret_input}})

    message = str(raised.value)
    assert message == "[hit.howler.score] Invalid value"
    assert secret_input not in message
    assert secret_input.replace("  ", " ") not in message
    assert secret_input == raised.value.errors[0]["input"]


def test_hit_nested_destination_bytes_path_is_rooted_at_hit() -> None:
    """Nested ECS fields use the public root and dotted serialized path."""
    with pytest.raises(HowlerModelValidationError) as raised:
        Hit.validate_howler(
            {
                "howler": {"analytic": "test", "hash": VALID_HASH},
                "destination": {"bytes": "not-an-integer"},
            }
        )

    assert str(raised.value).startswith("[hit.destination.bytes] ")


def test_hit_empty_hash_uses_known_safe_static_rejection_message() -> None:
    """A whitelisted static validator message can retain its useful rejection reason."""
    with pytest.raises(HowlerModelValidationError) as raised:
        Hit.validate_howler({"howler": {"analytic": "test", "hash": ""}})

    assert str(raised.value) == "[hit.howler.hash] Empty strings are not allowed without defaults"


def test_event_model_validator_has_a_stable_container_path() -> None:
    """A nested before-model validator reports its enclosing event list location."""
    with pytest.raises(HowlerModelValidationError) as raised:
        Event.validate_howler({"howler": {"hash": VALID_HASH, "log": [{"user": "analyst", "key": "field"}]}})

    message = str(raised.value)
    assert message == "[event.howler.log.0] An explanation or complete change details are required"


def test_template_errors_use_the_template_root_not_the_validation_title_dump() -> None:
    """Non-Hit models use the same public formatter and root naming convention."""
    with pytest.raises(HowlerModelValidationError) as raised:
        Template.validate_howler({"template_id": VALID_UUID, "type": "global", "keys": []})

    assert str(raised.value).startswith("[template.analytic] Field required")
    assert "1 validation error for Template" not in str(raised.value)
    assert "errors.pydantic.dev" not in str(raised.value)


def test_validation_title_is_a_fallback_when_model_type_is_not_supplied() -> None:
    """Direct wrapper use still gets a safe root from Pydantic's model title."""
    with pytest.raises(ValidationError) as raised:
        Template.model_validate({"template_id": VALID_UUID, "type": "global", "keys": []})

    public_error = HowlerModelValidationError(raised.value)
    assert str(public_error).startswith("[template.analytic] Field required")


def test_aliases_list_indexes_and_mapping_keys_use_serialized_paths() -> None:
    """Container paths translate both field aliases and nested list/mapping locations."""
    with pytest.raises(HowlerModelValidationError) as raised:
        AliasedValidationRoot.validate_howler(
            {
                "wire_entries": [
                    {
                        "wire_value": "not-an-integer",
                        "wire_metadata": {"customer": "also-not-an-integer"},
                    }
                ]
            }
        )

    messages = str(raised.value).splitlines()
    assert messages[0].startswith("[aliasedvalidationroot.records.0.value] ")
    assert messages[1].startswith("[aliasedvalidationroot.records.0.metadata.customer] ")
    assert "not-an-integer" not in str(raised.value)


def test_unknown_field_remains_forbidden_with_a_public_path() -> None:
    """Stable formatting does not loosen Howler's strict extra-field rejection."""
    with pytest.raises(HowlerModelValidationError) as raised:
        Hit.validate_howler(
            {
                "howler": {"analytic": "test", "hash": VALID_HASH},
                "unexpected": "UNKNOWN_FIELD_VALUE",
            }
        )

    assert str(raised.value).startswith("[hit.unexpected] Extra inputs are not permitted")


def test_deep_error_input_is_never_traversed_or_stringified() -> None:
    """A deeply nested rejected value cannot break public exception construction."""
    deep_value: list[Any] = []
    cursor = deep_value
    for _ in range(1600):
        child: list[Any] = []
        cursor.append(child)
        cursor = child

    with pytest.raises(ValidationError) as raised:
        DeepInputModel.model_validate({"value": deep_value})

    public_error = HowlerModelValidationError(raised.value, DeepInputModel)
    assert str(public_error) == "[deepinputmodel.value] Input should be a valid integer"
    assert public_error.cause is raised.value


def test_formatter_failure_falls_back_without_losing_howler_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A broken path or message formatter still produces a safe wrapper."""

    def fail_formatter(*_args: Any, **_kwargs: Any) -> str:
        raise RuntimeError("formatter failure")

    monkeypatch.setattr(model_base, "_public_error_location", fail_formatter)
    monkeypatch.setattr(model_base, "_public_error_message", fail_formatter)

    with pytest.raises(HowlerModelValidationError) as raised:
        Hit.validate_howler({"howler": {"hash": VALID_HASH}})

    assert str(raised.value) == "[hit] Invalid value"
    assert isinstance(raised.value.cause, ValidationError)
