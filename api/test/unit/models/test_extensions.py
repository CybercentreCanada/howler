"""Tests for the startup model extension registry (plugin/Clue field composition)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextvars import Context
from typing import Annotated

import pytest

from howler.common.exceptions import HowlerValueError
from howler.models import (
    HowlerEmbeddedModel,
    HowlerESModel,
    HowlerModelValidationError,
    ModelExtensionRegistry,
    keyword,
    metadata,
    model_extensions,
    model_registry,
    register_model,
)
from howler.models.clue import declare_hit_extension
from howler.models.hit import Hit
from howler.models.user import User


@register_model(index=True, store=True, embedded=True)
class ExtensionChild(HowlerEmbeddedModel):
    """Embedded model used as a plugin extension payload."""

    value: keyword()


@register_model(index=True, store=True, id_field="target_id")
class ExtensionTarget(HowlerESModel):
    """Top-level document used as an extension target in tests."""

    target_id: keyword()
    name: keyword()


def test_finalize_without_extensions_returns_original_model() -> None:
    """A target with no declared extensions finalizes to itself, unchanged."""
    registry = ModelExtensionRegistry()
    finalized = registry.finalize(ExtensionTarget)
    assert finalized is ExtensionTarget


def test_single_plugin_extension_is_applied_and_mapped() -> None:
    """A declared extension field appears on the finalized model and its mapping."""
    registry = ModelExtensionRegistry()
    registry.declare(
        ExtensionTarget, "evidence", Annotated[list[ExtensionChild], metadata(default=[])], plugin="evidence"
    )

    finalized = registry.finalize(ExtensionTarget)
    assert finalized is not ExtensionTarget
    assert issubclass(finalized, ExtensionTarget)

    instance = finalized.model_validate({"target_id": "t1", "name": "n", "evidence": [{"value": "v"}]})
    assert instance.evidence[0].value == "v"

    mapping = model_registry.mapping(finalized)
    assert mapping["properties"]["evidence"]["type"] == "object"
    assert mapping["properties"]["name"]["type"] == "keyword"


def test_multiple_plugin_extensions_apply_deterministically() -> None:
    """Multiple plugin extensions apply in a deterministic (plugin, name) order."""
    registry_a = ModelExtensionRegistry()
    registry_a.declare(ExtensionTarget, "zeta", keyword(optional=True), plugin="plugin_z")
    registry_a.declare(ExtensionTarget, "alpha", keyword(optional=True), plugin="plugin_a")
    finalized_a = registry_a.finalize(ExtensionTarget)

    registry_b = ModelExtensionRegistry()
    registry_b.declare(ExtensionTarget, "alpha", keyword(optional=True), plugin="plugin_a")
    registry_b.declare(ExtensionTarget, "zeta", keyword(optional=True), plugin="plugin_z")
    finalized_b = registry_b.finalize(ExtensionTarget)

    # Field order is deterministic regardless of declaration order.
    assert list(finalized_a.model_fields.keys())[-2:] == list(finalized_b.model_fields.keys())[-2:]
    assert "alpha" in finalized_a.model_fields
    assert "zeta" in finalized_a.model_fields


def test_conflicting_extension_names_are_rejected() -> None:
    """Two plugins declaring the same field name against the same target conflict."""
    registry = ModelExtensionRegistry()
    registry.declare(ExtensionTarget, "shared", keyword(optional=True), plugin="plugin_one")

    with pytest.raises(HowlerValueError, match="already declared"):
        registry.declare(ExtensionTarget, "shared", keyword(optional=True), plugin="plugin_two")


def test_extension_colliding_with_existing_field_is_rejected() -> None:
    """An extension cannot reuse a field name that already exists on the target."""
    registry = ModelExtensionRegistry()
    with pytest.raises(HowlerValueError, match="conflicts with an existing field"):
        registry.declare(ExtensionTarget, "name", keyword(optional=True), plugin="plugin_one")


def test_extension_alias_cannot_shadow_serialized_base_or_pending_field() -> None:
    class AliasedTarget(ExtensionTarget):
        internal_name: keyword(alias="public_name")

    registry = ModelExtensionRegistry()
    with pytest.raises(HowlerValueError, match="conflicts with an existing field"):
        registry.declare(AliasedTarget, "plugin_name", keyword(alias="public_name"), plugin="one")
    registry.declare(AliasedTarget, "first", keyword(alias="shared"), plugin="one")
    with pytest.raises(HowlerValueError, match="Duplicate serialized field name 'shared'"):
        registry.declare(AliasedTarget, "second", keyword(alias="shared"), plugin="two")
    with pytest.raises(HowlerValueError, match="Illegal extension field name: id"):
        registry.declare(ExtensionTarget, "looks_valid", keyword(alias="id"), plugin="two")

    assert list(registry.pending(AliasedTarget)) == ["first"]
    assert not registry.is_finalized(AliasedTarget)


def test_registration_rejects_duplicate_final_serialization_names() -> None:
    class DuplicateTarget(ExtensionTarget):
        different_name: keyword(alias="name")

    with pytest.raises(HowlerValueError, match="Duplicate serialized field name 'name'"):
        model_registry.register_derived(DuplicateTarget, ExtensionTarget)


@pytest.mark.parametrize("name,storage", [("public_name", "other_storage"), ("other_name", "internal_name")])
def test_python_and_storage_names_cannot_cross_between_fields(name, storage):
    class BaseTarget(ExtensionTarget):
        internal_name: keyword(alias="public_name")

    registry = ModelExtensionRegistry()
    with pytest.raises(HowlerValueError, match="conflicts"):
        registry.declare(BaseTarget, name, keyword(alias=storage), plugin="second")
    registry.declare(ExtensionTarget, "internal_name", keyword(alias="public_name"), plugin="first")
    with pytest.raises(HowlerValueError, match="conflicts"):
        registry.declare(ExtensionTarget, name, keyword(alias=storage), plugin="second")
    assert set(registry.pending(ExtensionTarget)) == {"internal_name"}


def test_invalid_extension_field_name_is_rejected() -> None:
    """Extension field names must pass the same sanitizer as regular model fields."""
    registry = ModelExtensionRegistry()
    with pytest.raises(HowlerValueError, match="Illegal extension field name"):
        registry.declare(ExtensionTarget, "Bad-Name!", keyword(optional=True), plugin="plugin_one")

    with pytest.raises(HowlerValueError, match="Illegal extension field name"):
        registry.declare(ExtensionTarget, "__access_lvl__", keyword(optional=True), plugin="plugin_one")

    with pytest.raises(HowlerValueError, match="Illegal extension field name"):
        registry.declare(ExtensionTarget, "id", keyword(optional=True), plugin="plugin_one")


def test_declaration_after_finalization_is_rejected() -> None:
    """Once a target has been finalized, no further extensions may be declared for it."""
    registry = ModelExtensionRegistry()
    registry.declare(ExtensionTarget, "evidence", keyword(optional=True), plugin="evidence")
    registry.finalize(ExtensionTarget)

    with pytest.raises(HowlerValueError, match="already been finalized"):
        registry.declare(ExtensionTarget, "late", keyword(optional=True), plugin="late_plugin")


def test_finalize_is_idempotent() -> None:
    """Calling finalize twice for the same target returns the same cached derived model."""
    registry = ModelExtensionRegistry()
    registry.declare(ExtensionTarget, "evidence", keyword(optional=True), plugin="evidence")
    first = registry.finalize(ExtensionTarget)
    second = registry.finalize(ExtensionTarget)
    assert first is second


def test_registry_instances_are_isolated() -> None:
    """Separate registry instances do not share pending or finalized state (cache isolation)."""
    registry_one = ModelExtensionRegistry()
    registry_two = ModelExtensionRegistry()

    registry_one.declare(ExtensionTarget, "only_in_one", keyword(optional=True), plugin="p1")

    assert "only_in_one" in registry_one.pending(ExtensionTarget)
    assert registry_two.pending(ExtensionTarget) == {}

    finalized_one = registry_one.finalize(ExtensionTarget)
    assert "only_in_one" in finalized_one.model_fields

    # The second registry, with nothing declared, finalizes to the unmodified target.
    finalized_two = registry_two.finalize(ExtensionTarget)
    assert finalized_two is ExtensionTarget
    assert "only_in_one" not in finalized_two.model_fields


def test_imported_hook_uses_nested_scope_and_restores_outer_model_on_error() -> None:
    previous_pending = model_extensions.pending(Hit)
    previously_finalized = model_extensions.is_finalized(Hit)
    with model_extensions.isolated():
        model_extensions.declare(Hit, "outer_only", keyword(), plugin="outer")
        outer_model = model_extensions.finalize(Hit)
        with pytest.raises(HowlerValueError, match="already been finalized"), model_extensions.isolated():
            assert model_extensions.pending(Hit) == {}
            assert not model_extensions.is_finalized(Hit)
            # The Clue hook imported the singleton before either scope was entered.
            declare_hit_extension()
            assert set(model_extensions.pending(Hit)) == {"clue"}
            inner_model = model_extensions.finalize(Hit)
            assert "clue" in inner_model.model_fields and "outer_only" not in inner_model.model_fields
            declare_hit_extension()

        assert model_extensions.finalize(Hit) is outer_model
        assert set(model_extensions.pending(Hit)) == {"outer_only"}

    assert model_extensions.pending(Hit) == previous_pending
    assert model_extensions.is_finalized(Hit) == previously_finalized


def test_concurrent_scopes_preserve_unscoped_startup_changes() -> None:
    registry = ModelExtensionRegistry()
    registry.declare(ExtensionTarget, "startup", keyword(), plugin="startup")
    original = registry.finalize(ExtensionTarget)

    def recompose_in_worker():
        assert registry.finalize(ExtensionTarget) is original
        with registry.isolated():
            assert not registry.is_finalized(ExtensionTarget)
            registry.declare(ExtensionTarget, "worker", keyword(), plugin="worker")
            assert "worker" in registry.finalize(ExtensionTarget).model_fields
        assert registry.finalize(ExtensionTarget) is original
        registry.clear()
        registry.declare(ExtensionTarget, "replacement", keyword(), plugin="startup")
        return registry.finalize(ExtensionTarget)

    with ThreadPoolExecutor(max_workers=1) as pool:
        # Start the worker in the unscoped context, as a running startup thread would be.
        assert pool.submit(registry.finalize, ExtensionTarget).result(timeout=10) is original
        with registry.isolated():
            registry.clear()
            registry.declare(ExtensionTarget, "local", keyword(), plugin="local")
            local = registry.finalize(ExtensionTarget)
            assert Context().run(registry.finalize, ExtensionTarget) is original
            replacement = pool.submit(recompose_in_worker).result(timeout=10)
            assert registry.finalize(ExtensionTarget) is local
            assert set(registry.pending(ExtensionTarget)) == {"local"}

    assert registry.finalize(ExtensionTarget) is replacement
    assert set(registry.pending(ExtensionTarget)) == {"replacement"}


def test_disabled_extension_leaves_target_unmodified() -> None:
    """An extension that is never declared (e.g. a disabled feature) has no effect."""
    registry = ModelExtensionRegistry()
    # Simulate a feature flag being off: nothing is declared.
    finalized = registry.finalize(ExtensionTarget)
    assert finalized is ExtensionTarget
    assert "clue" not in finalized.model_fields


def test_extension_field_still_forbids_unknown_input() -> None:
    """Extra and unknown fields remain rejected on the finalized model."""
    registry = ModelExtensionRegistry()
    registry.declare(ExtensionTarget, "evidence", keyword(optional=True), plugin="evidence")
    finalized = registry.finalize(ExtensionTarget)

    with pytest.raises(HowlerModelValidationError):
        finalized.model_validate({"target_id": "t1", "name": "n", "unknown_field": "value"})


def test_mapping_only_reflects_finalized_extensions() -> None:
    """The unfinalized target's mapping never includes pending, un-finalized extension fields."""
    registry = ModelExtensionRegistry()
    registry.declare(ExtensionTarget, "pending_field", keyword(optional=True), plugin="plugin_one")

    # Mapping generated from the original target must not see the pending declaration.
    original_mapping = model_registry.mapping(ExtensionTarget)
    assert "pending_field" not in original_mapping["properties"]

    finalized = registry.finalize(ExtensionTarget)
    finalized_mapping = model_registry.mapping(finalized)
    assert "pending_field" in finalized_mapping["properties"]


def test_extension_preserves_auto_derived_id_field() -> None:
    """Extending a model keeps an inherited auto-derived ID that is not a declared field."""
    registry = ModelExtensionRegistry()
    registry.declare(User, "plugin_data", keyword(optional=True), plugin="plugin_one")

    finalized = registry.finalize(User)

    assert "plugin_data" in finalized.model_fields
    assert model_registry.metadata(finalized).id_field == model_registry.metadata(User).id_field == "user_id"
