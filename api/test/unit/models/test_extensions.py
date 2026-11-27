from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextvars import Context
from typing import Annotated

import pytest

from howler.common.exceptions import HowlerValueError
from howler.models import (
    HowlerESModel,
    Keyword,
    ModelExtensionRegistry,
    metadata,
    model_extensions,
    model_registry,
    register_model,
)
from howler.models.clue import declare_hit_extension
from howler.models.hit import Hit
from howler.models.user import User


@register_model(index=True, store=True, id_field="target_id")
class Target(HowlerESModel):
    target_id: Keyword
    name: Keyword


def test_composition_is_ordered_cached_and_preserves_id():
    registry = ModelExtensionRegistry()
    assert ModelExtensionRegistry().finalize(Target) is Target
    registry.declare(Target, "zeta", Keyword | None, plugin="z")
    registry.declare(Target, "alpha", Keyword | None, plugin="a")
    assert "alpha" not in model_registry.mapping(Target)["properties"]
    model = registry.finalize(Target)
    assert list(model.model_fields)[-2:] == ["alpha", "zeta"]
    assert model_registry.mapping(model)["properties"]["alpha"]["type"] == "keyword"
    assert registry.finalize(Target) is model
    with pytest.raises(HowlerValueError, match="already been finalized"):
        registry.declare(Target, "late", Keyword, plugin="late")
    registry.declare(User, "plugin_data", Keyword | None, plugin="plugin")
    assert model_registry.metadata(registry.finalize(User)).id_field == "user_id"


def test_duplicate_serialized_names_and_illegal_fields():
    class Aliased(Target):
        internal_name: Annotated[Keyword, metadata(alias="public_name")]

    class Duplicate(Target):
        different_name: Annotated[Keyword, metadata(alias="name")]

    registry = ModelExtensionRegistry()
    with pytest.raises(HowlerValueError, match="Duplicate serialized field name"):
        model_registry.register_derived(Duplicate, Target)
    with pytest.raises(HowlerValueError, match="conflicts"):
        registry.declare(Aliased, "plugin_name", Annotated[Keyword, metadata(alias="public_name")], plugin="one")
    registry.declare(Aliased, "first", Annotated[Keyword, metadata(alias="shared")], plugin="one")
    with pytest.raises(HowlerValueError, match="Duplicate serialized field name"):
        registry.declare(Aliased, "second", Annotated[Keyword, metadata(alias="shared")], plugin="two")
    with pytest.raises(HowlerValueError, match="already declared"):
        registry.declare(Aliased, "first", Keyword, plugin="two")
    for name in ("Bad-Name!", "__access_lvl__", "id"):
        with pytest.raises(HowlerValueError, match="Illegal extension field name"):
            registry.declare(Target, name, Keyword, plugin="one")
    with pytest.raises(HowlerValueError, match="Illegal extension field name"):
        registry.declare(Target, "looks_valid", Annotated[Keyword, metadata(alias="id")], plugin="two")


@pytest.mark.parametrize("name,storage", [("public_name", "other_storage"), ("other_name", "internal_name")])
def test_python_and_storage_names_cannot_cross_between_fields(name, storage):
    class BaseTarget(Target):
        internal_name: Annotated[Keyword, metadata(alias="public_name")]

    registry = ModelExtensionRegistry()
    with pytest.raises(HowlerValueError, match="conflicts"):
        registry.declare(BaseTarget, name, Annotated[Keyword, metadata(alias=storage)], plugin="second")
    registry.declare(Target, "internal_name", Annotated[Keyword, metadata(alias="public_name")], plugin="first")
    with pytest.raises(HowlerValueError, match="conflicts"):
        registry.declare(Target, name, Annotated[Keyword, metadata(alias=storage)], plugin="second")


def test_imported_hook_restores_nested_scopes_on_error():
    previous = model_extensions.pending(Hit), model_extensions.is_finalized(Hit)
    with model_extensions.isolated():
        model_extensions.declare(Hit, "outer_only", Keyword, plugin="outer")
        outer = model_extensions.finalize(Hit)
        with pytest.raises(HowlerValueError, match="already been finalized"), model_extensions.isolated():
            declare_hit_extension()
            assert "clue" in model_extensions.finalize(Hit).model_fields
            declare_hit_extension()
        assert model_extensions.finalize(Hit) is outer
    assert (model_extensions.pending(Hit), model_extensions.is_finalized(Hit)) == previous


def test_concurrent_scopes_preserve_unscoped_startup_changes():
    registry = ModelExtensionRegistry()
    registry.declare(Target, "startup", Keyword, plugin="startup")
    original = registry.finalize(Target)

    def worker():
        with registry.isolated():
            registry.declare(Target, "worker", Keyword, plugin="worker")
            assert "worker" in registry.finalize(Target).model_fields
        assert registry.finalize(Target) is original
        registry.clear()
        registry.declare(Target, "replacement", Keyword, plugin="startup")
        return registry.finalize(Target)

    with ThreadPoolExecutor(max_workers=1) as pool, registry.isolated():
        registry.declare(Target, "local", Keyword, plugin="local")
        local = registry.finalize(Target)
        assert Context().run(registry.finalize, Target) is original
        replacement = pool.submit(worker).result(timeout=10)
        assert registry.finalize(Target) is local
    assert registry.finalize(Target) is replacement
