"""Substantive Pydantic metadata comparisons against the frozen ODM inventory."""

from __future__ import annotations

import importlib
import types
from typing import Annotated, Any, Union, get_args, get_origin

import pytest
from pydantic import TypeAdapter, ValidationError

from howler.models import model_registry
from howler.models.action import Action
from howler.models.ecs.agent import Agent
from test.unit.models._goldens import contract_golden
from test.unit.models.test_field_parity_differential import _flattened_cases

INVENTORY_MODELS = contract_golden()["models"]


def _nullable(annotation: Any) -> bool:
    origin = get_origin(annotation)
    if origin is Annotated:
        return _nullable(get_args(annotation)[0])
    if origin in (Union, types.UnionType):
        args = get_args(annotation)
        return type(None) in args or any(_nullable(argument) for argument in args if argument is not type(None))
    return False


def _definition(legacy_module: str, new_module: str, class_name: str):
    model_type = getattr(importlib.import_module(new_module), class_name)
    key = f"{legacy_module}.{class_name}"
    return model_type, key, INVENTORY_MODELS[key]


def _field_info(model_type: type, serialized_name: str):
    for python_name, field in model_type.model_fields.items():
        if (
            python_name == serialized_name
            or field.serialization_alias == serialized_name
            or field.alias == serialized_name
        ):
            return field
    raise AssertionError(f"No Pydantic field serializes as {serialized_name} on {model_type.__name__}")


@pytest.mark.parametrize(
    "legacy_module,new_module,class_name",
    _flattened_cases(),
    ids=[f"{new_module}.{name}" for _, new_module, name in _flattened_cases()],
)
def test_model_metadata_and_field_keys_match_frozen_contract(
    legacy_module: str, new_module: str, class_name: str
) -> None:
    model_type, _, expected = _definition(legacy_module, new_module, class_name)
    metadata = model_registry.metadata(model_type)
    fields = model_registry.fields(model_type)

    assert metadata.name == expected["name"]
    if expected["description"] is not None:
        assert metadata.description == expected["description"]
    else:
        # The legacy decorator stored no model description, while Pydantic falls back to the
        # class docstring for metadata when one exists.
        assert metadata.description in (None, model_type.__doc__)
    assert metadata.id_field == expected["id_field"]
    # Field and mapping dictionaries are objects, not an ordering contract.
    assert set(fields) == set(expected["fields"])

    # Compare datastore behavior metadata for every declared field. The complete defaults are
    # frozen in the Step 1 inventory; only fields with a legacy explicit default are asserted as
    # defaulted here, since the legacy ``default_set=False`` convention is distinct from Pydantic's
    # required/default-factory representation.
    for name, definition in fields.items():
        old_field = expected["fields"][name]
        field_metadata = definition.metadata
        assert field_metadata is not None, f"{legacy_module}.{class_name}.{name} lost field metadata"
        assert field_metadata.index == old_field["index"]
        assert field_metadata.store == old_field["store"]

        if old_field["default_set"]:
            assert not definition.required
            assert definition.default == old_field["default"]

        if old_field["type"].endswith(".Optional") or old_field["optional"]:
            assert _nullable(_field_info(model_type, name).annotation)


@pytest.mark.parametrize(
    "legacy_module,new_module,class_name",
    _flattened_cases(),
    ids=[f"{new_module}.{name}" for _, new_module, name in _flattened_cases()],
)
def test_every_declared_legacy_field_description_is_preserved(
    legacy_module: str, new_module: str, class_name: str
) -> None:
    model_type, _, expected = _definition(legacy_module, new_module, class_name)
    actual_fields = model_registry.flat_fields(model_type)

    # Descriptions reside on flattened leaf definitions for legacy Compound/Optional wrappers.
    # A typographic right quote is normalized because the migrated ECS texts use its ASCII form.
    for path, definition in actual_fields.items():
        old_field = expected["flat_fields"][path]
        field_metadata = definition.metadata
        assert field_metadata is not None
        assert list(field_metadata.copy_to) == old_field["copy_to"], path
        assert field_metadata.sync == old_field["sync"], path
        assert field_metadata.reference == old_field["reference"], path
        assert field_metadata.deprecated == old_field["deprecated"], path
        assert field_metadata.deprecated_description == old_field["deprecated_description"], path
        if old_field["description"] is not None:
            if isinstance(definition.description, str) and isinstance(old_field["description"], str):
                description = definition.description.replace("’", "'")
                expected_description = old_field["description"].replace("’", "'")
            else:
                description = definition.description
                expected_description = old_field["description"]
            assert description == expected_description, path


def test_nullable_and_required_fields_match_frozen_expectations_in_both_directions() -> None:
    agent_expected = INVENTORY_MODELS["howler.odm.models.ecs.agent.Agent"]["fields"]["id"]
    action_expected = INVENTORY_MODELS["howler.odm.models.action.Action"]["fields"]["name"]
    assert agent_expected["type"].endswith(".Optional")
    assert action_expected["type"].endswith(".Keyword")

    agent_id = model_registry.fields(Agent)["id"].annotation
    action_name = model_registry.fields(Action)["name"].annotation
    assert TypeAdapter(agent_id).validate_python(None) is None
    with pytest.raises(ValidationError):
        TypeAdapter(action_name).validate_python(None)
