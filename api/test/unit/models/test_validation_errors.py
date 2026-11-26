"""Howler wrappers for Pydantic model validation errors."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel, Field, ValidationError

from howler.models import HowlerEmbeddedModel, HowlerModelValidationError
from howler.models.case import CaseItem, CaseRule
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


def test_hit_missing_analytic_keeps_structured_error_and_original_message() -> None:
    """The wrapper retains Pydantic details and its original message."""
    with pytest.raises(HowlerModelValidationError) as raised:
        Hit.model_validate({"howler": {"hash": VALID_HASH}})

    public_error = raised.value
    assert isinstance(public_error.cause, ValidationError)
    assert str(public_error) == str(public_error.cause)
    assert "howler.analytic" in str(public_error)
    assert "Field required" in str(public_error)
    assert public_error.__cause__ is public_error.cause
    assert public_error.errors == public_error.cause.errors(include_url=False)


@pytest.mark.parametrize(
    "invalid_input",
    ["INVALID_SCORE_VALUE", "INVALID  TOKEN"],
)
def test_hit_invalid_score_passes_through_original_input(invalid_input: str) -> None:
    """The original validator message and submitted value are preserved."""
    with pytest.raises(HowlerModelValidationError) as raised:
        Hit.model_validate({"howler": {"analytic": "test", "hash": VALID_HASH, "score": invalid_input}})

    message = str(raised.value)
    assert isinstance(raised.value.cause, ValidationError)
    assert message == str(raised.value.cause)
    assert "howler.score" in message
    assert invalid_input in message
    assert invalid_input == raised.value.errors[0]["input"]


def test_hit_nested_destination_bytes_path_is_preserved() -> None:
    """Nested ECS fields retain Pydantic's dotted validation path."""
    with pytest.raises(HowlerModelValidationError) as raised:
        Hit.model_validate(
            {
                "howler": {"analytic": "test", "hash": VALID_HASH},
                "destination": {"bytes": "not-an-integer"},
            }
        )

    assert "destination.bytes" in str(raised.value)


def test_hit_empty_hash_preserves_validator_message() -> None:
    """The original rejection reason remains available."""
    with pytest.raises(HowlerModelValidationError) as raised:
        Hit.model_validate({"howler": {"analytic": "test", "hash": ""}})

    assert "howler.hash" in str(raised.value)
    assert "Empty strings are not allowed without defaults" in str(raised.value)


def test_event_model_validator_has_a_container_path() -> None:
    """A nested before-model validator reports its enclosing event list location."""
    with pytest.raises(HowlerModelValidationError) as raised:
        Event.model_validate({"howler": {"hash": VALID_HASH, "log": [{"user": "analyst", "key": "field"}]}})

    message = str(raised.value)
    assert "howler.log.0" in message
    assert "If no explanation provided" in message


def test_template_errors_keep_the_validation_title() -> None:
    """Non-Hit models retain Pydantic's title and message."""
    with pytest.raises(HowlerModelValidationError) as raised:
        Template.model_validate({"template_id": VALID_UUID, "type": "global", "keys": []})

    assert "1 validation error for Template" in str(raised.value)
    assert "analytic" in str(raised.value)
    assert "Field required" in str(raised.value)


def test_direct_wrapper_preserves_pydantic_message() -> None:
    """Direct wrapper use preserves the original Pydantic error."""

    class Template(BaseModel):  # noqa: D106
        analytic: str

    with pytest.raises(ValidationError) as raised:
        Template.model_validate({})

    public_error = HowlerModelValidationError(raised.value)
    assert str(public_error) == str(raised.value)
    assert public_error.cause is raised.value


def test_aliases_list_indexes_and_mapping_keys_use_validation_paths() -> None:
    """Container paths retain Pydantic's input aliases and nested locations."""
    with pytest.raises(HowlerModelValidationError) as raised:
        AliasedValidationRoot.model_validate(
            {
                "wire_entries": [
                    {
                        "wire_value": "not-an-integer",
                        "wire_metadata": {"customer": "also-not-an-integer"},
                    }
                ]
            }
        )

    message = str(raised.value)
    assert "wire_entries.0.wire_value" in message
    assert "wire_entries.0.wire_metadata.customer" in message
    assert "not-an-integer" in message


def test_unknown_field_remains_forbidden() -> None:
    """Passing the original error through does not loosen extra-field rejection."""
    with pytest.raises(HowlerModelValidationError) as raised:
        Hit.model_validate(
            {
                "howler": {"analytic": "test", "hash": VALID_HASH},
                "unexpected": "UNKNOWN_FIELD_VALUE",
            }
        )

    assert "unexpected" in str(raised.value)
    assert "Extra inputs are not permitted" in str(raised.value)
    assert "UNKNOWN_FIELD_VALUE" in str(raised.value)


def test_deep_error_input_preserves_original_error() -> None:
    """A deeply nested rejected value retains the original error."""
    deep_value: list[Any] = []
    cursor = deep_value
    for _ in range(1600):
        child: list[Any] = []
        cursor.append(child)
        cursor = child

    with pytest.raises(ValidationError) as raised:
        DeepInputModel.model_validate({"value": deep_value})

    public_error = HowlerModelValidationError(raised.value)
    assert str(public_error) == str(raised.value)
    assert public_error.cause is raised.value


@pytest.mark.parametrize(
    ("model_type", "data", "message"),
    [
        (
            CaseRule,
            {
                "rule_id": "rule-1",
                "destination": "folder",
                "query": "howler.id:*",
                "author": "analyst",
                "timeframe": None,
                "expire_after_resolved": True,
            },
            "expire after resolved",
        ),
        (
            CaseRule,
            {"rule_id": "rule-1", "destination": "folder", "query": "q", "author": "a", "timeframe": -1},
            "positive integer",
        ),
        (CaseItem, {"type": "case", "parent": "folder", "value": "case-1"}, "root-level"),
    ],
)
def test_domain_validation_errors_preserve_messages(
    model_type: type[HowlerEmbeddedModel], data: dict[str, Any], message: str
) -> None:
    with pytest.raises(HowlerModelValidationError, match=message) as raised:
        model_type.model_validate(data)

    assert isinstance(raised.value.cause, ValidationError)
    assert str(raised.value) == str(raised.value.cause)
    assert raised.value.errors and raised.value.cause is not None
