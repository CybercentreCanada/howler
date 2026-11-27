"""Howler wrappers for Pydantic model validation errors."""

from __future__ import annotations

import pytest
from pydantic import Field, ValidationError

from howler.models import HowlerEmbeddedModel, HowlerModelValidationError
from howler.models.event import Event
from howler.models.hit import Hit

VALID_HASH = "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bc"


class AliasedValidationLeaf(HowlerEmbeddedModel):
    value_: int = Field(alias="wire_value", serialization_alias="value")
    metadata_: dict[str, int] = Field(default_factory=dict, alias="wire_metadata", serialization_alias="metadata")


class AliasedValidationRoot(HowlerEmbeddedModel):
    entries: list[AliasedValidationLeaf] = Field(alias="wire_entries", serialization_alias="records")


def test_hit_missing_analytic_keeps_structured_error_and_original_message() -> None:
    with pytest.raises(HowlerModelValidationError) as raised:
        Hit.model_validate({"howler": {"hash": VALID_HASH}})

    public_error = raised.value
    assert isinstance(public_error.cause, ValidationError)
    assert str(public_error) == str(public_error.cause)
    assert "howler.analytic" in str(public_error)
    assert "Field required" in str(public_error)
    assert public_error.__cause__ is public_error.cause
    assert public_error.errors == public_error.cause.errors(include_url=False)


def test_hit_invalid_score_passes_through_original_input() -> None:
    invalid_input = "INVALID_SCORE_VALUE"
    with pytest.raises(HowlerModelValidationError) as raised:
        Hit.model_validate({"howler": {"analytic": "test", "hash": VALID_HASH, "score": invalid_input}})

    message = str(raised.value)
    assert isinstance(raised.value.cause, ValidationError)
    assert message == str(raised.value.cause)
    assert "howler.score" in message
    assert invalid_input in message
    assert invalid_input == raised.value.errors[0]["input"]


def test_event_model_validator_has_a_container_path() -> None:
    with pytest.raises(HowlerModelValidationError) as raised:
        Event.model_validate({"howler": {"hash": VALID_HASH, "log": [{"user": "analyst", "key": "field"}]}})

    message = str(raised.value)
    assert "howler.log.0" in message
    assert "If no explanation provided" in message


def test_aliases_list_indexes_and_mapping_keys_use_validation_paths() -> None:
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
