from typing import Annotated

import pytest

from howler.models import HowlerModelValidationError, ModelExtensionRegistry, metadata, model_registry
from howler.models.clue import Clue, TypeMap
from howler.models.hit import Hit


def test_clue_nested_types_and_assignment():
    first, second = Clue.model_validate({}), Clue.model_validate({})
    first.types = [{"field": "source.ip", "type": "ip"}]
    assert isinstance(first.types[0], TypeMap) and second.types == []
    first.types[0].type = "ipv4"
    assert first.as_primitives() == {"types": [{"field": "source.ip", "type": "ipv4"}]}
    assert Clue.model_validate_json(first.model_dump_json()) == first
    for data in ({"field": "source.ip"}, {"field": "source.ip", "type": ""}):
        with pytest.raises(HowlerModelValidationError):
            TypeMap.model_validate(data)


def test_optional_clue_extension():
    registry = ModelExtensionRegistry()
    registry.declare(Hit, "clue", Annotated[Clue | None, metadata(default=None)], plugin="clue")
    model = registry.finalize(Hit)
    data = {"howler": {"id": "hit-1", "analytic": "test", "hash": "a"}}
    assert model.model_validate(data).clue is None
    hit = model.model_validate({**data, "clue": {"types": [{"field": "source.ip", "type": "ip"}]}})
    primitives = hit.as_primitives()
    assert primitives["clue"]["types"] == [{"field": "source.ip", "type": "ip"}]
    primitives.pop("__index", None)
    assert model.model_validate(primitives).clue.types[0].field == "source.ip"
    assert model_registry.mapping(model)["properties"]["clue"]["type"] == "object"
    assert {"clue.types.field", "clue.types.type"} <= set(model_registry.flat_fields(model))
    with pytest.raises(HowlerModelValidationError):
        model.model_validate({**data, "clue": {"unknown": True}})
