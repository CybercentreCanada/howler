"""Clue models and their optional Hit model extension."""

from __future__ import annotations

from typing import Annotated

import pytest

from howler.models import HowlerModelValidationError, ModelExtensionRegistry, metadata, model_registry
from howler.models.clue import Clue, TypeMap
from howler.models.hit import Hit


class TestClue:
    """Tests for clue type mappings and serialization."""

    def test_clue_defaults_to_an_independent_empty_list(self) -> None:
        first = Clue.model_validate({})
        second = Clue.model_validate({})

        assert first.types == []
        assert second.types == []
        first.types.append(TypeMap.model_validate({"field": "source.ip", "type": "ip"}))
        assert len(second.types) == 0

    def test_clue_validates_nested_type_mappings(self) -> None:
        clue = Clue.model_validate(
            {
                "types": [
                    {"field": "source.ip", "type": "ip"},
                    {"field": "file.hash.sha256", "type": "hash"},
                    {"field": "process.parent.name", "type": "process_name"},
                    {"field": "custom.field", "type": "type-with-dashes"},
                ]
            }
        )

        assert len(clue.types) == 4
        assert isinstance(clue.types[0], TypeMap)
        assert clue.types[0].field == "source.ip"
        assert clue.types[0].type == "ip"
        assert clue.types[1].field == "file.hash.sha256"
        assert clue.types[3].type == "type-with-dashes"
        assert clue.as_primitives() == {
            "types": [
                {"field": "source.ip", "type": "ip"},
                {"field": "file.hash.sha256", "type": "hash"},
                {"field": "process.parent.name", "type": "process_name"},
                {"field": "custom.field", "type": "type-with-dashes"},
            ]
        }

    def test_clue_fields_can_be_replaced_and_updated(self) -> None:
        clue = Clue.model_validate({})
        clue.types = [{"field": "source.ip", "type": "ip"}]
        assert isinstance(clue.types[0], TypeMap)

        clue.types[0].type = "ipv4"
        assert clue.types[0].type == "ipv4"

    def test_clue_rejects_missing_or_empty_type_values(self) -> None:
        with pytest.raises(HowlerModelValidationError):
            TypeMap.model_validate({"field": "source.ip"})
        with pytest.raises(HowlerModelValidationError):
            Clue.model_validate({"types": [{"field": "source.ip", "type": ""}]})

    def test_clue_json_round_trip_and_equality(self) -> None:
        clue = Clue.model_validate(
            {"types": [{"field": "source.ip", "type": "ip"}, {"field": "destination.port", "type": "port"}]}
        )
        restored = Clue.model_validate_json(clue.model_dump_json(by_alias=True))

        assert restored == clue
        assert restored.types[0].field == "source.ip"
        assert restored.types[1].type == "port"

    def test_registry_exposes_clue_paths(self) -> None:
        fields = model_registry.fields(Clue)
        flat_fields = model_registry.flat_fields(Clue)

        assert "types" in fields
        assert "types.field" in flat_fields
        assert "types.type" in flat_fields


class TestHitClueExtension:
    """Tests for optional clue composition into a Hit model."""

    def test_optional_extension_validates_serializes_and_maps(self) -> None:
        registry = ModelExtensionRegistry()
        registry.declare(Hit, "clue", Annotated[Clue | None, metadata(default=None)], plugin="clue")
        hit_model = registry.finalize(Hit)
        hit_data = {"howler": {"id": "hit-1", "analytic": "test", "hash": "a"}}

        without_clue = hit_model.model_validate(hit_data)
        assert without_clue.clue is None

        with_clue = hit_model.model_validate(
            {
                **hit_data,
                "clue": {"types": [{"field": "source.ip", "type": "ip"}]},
            }
        )
        primitives = with_clue.as_primitives()
        assert primitives["clue"]["types"] == [{"field": "source.ip", "type": "ip"}]
        primitives.pop("__index", None)
        restored = hit_model.model_validate(primitives)
        assert restored.clue is not None
        assert restored.clue.types[0].field == "source.ip"

        properties = model_registry.mapping(hit_model)["properties"]
        assert properties["clue"]["type"] == "object"
        flat_fields = model_registry.flat_fields(hit_model)
        assert "clue.types.field" in flat_fields
        assert "clue.types.type" in flat_fields

        with pytest.raises(HowlerModelValidationError):
            hit_model.model_validate({**hit_data, "clue": {"unknown": True}})
