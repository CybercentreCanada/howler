"""Tests for the startup model extension registry (plugin/Clue field composition)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from howler.common.exceptions import HowlerValueError
from howler.models import (
    HowlerEmbeddedModel,
    HowlerESModel,
    ModelExtensionRegistry,
    compound,
    keyword,
    list_field,
    model_registry,
    optional,
    register_model,
)
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
    registry.declare(ExtensionTarget, "evidence", list_field(compound(ExtensionChild), default=[]), plugin="evidence")

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
    registry_a.declare(ExtensionTarget, "zeta", optional(keyword()), plugin="plugin_z")
    registry_a.declare(ExtensionTarget, "alpha", optional(keyword()), plugin="plugin_a")
    finalized_a = registry_a.finalize(ExtensionTarget)

    registry_b = ModelExtensionRegistry()
    registry_b.declare(ExtensionTarget, "alpha", optional(keyword()), plugin="plugin_a")
    registry_b.declare(ExtensionTarget, "zeta", optional(keyword()), plugin="plugin_z")
    finalized_b = registry_b.finalize(ExtensionTarget)

    # Field order is deterministic regardless of declaration order.
    assert list(finalized_a.model_fields.keys())[-2:] == list(finalized_b.model_fields.keys())[-2:]
    assert "alpha" in finalized_a.model_fields
    assert "zeta" in finalized_a.model_fields


def test_conflicting_extension_names_are_rejected() -> None:
    """Two plugins declaring the same field name against the same target conflict."""
    registry = ModelExtensionRegistry()
    registry.declare(ExtensionTarget, "shared", optional(keyword()), plugin="plugin_one")

    with pytest.raises(HowlerValueError, match="already declared"):
        registry.declare(ExtensionTarget, "shared", optional(keyword()), plugin="plugin_two")


def test_extension_colliding_with_existing_field_is_rejected() -> None:
    """An extension cannot reuse a field name that already exists on the target."""
    registry = ModelExtensionRegistry()
    with pytest.raises(HowlerValueError, match="conflicts with an existing field"):
        registry.declare(ExtensionTarget, "name", optional(keyword()), plugin="plugin_one")


def test_invalid_extension_field_name_is_rejected() -> None:
    """Extension field names must pass the same sanitizer as regular model fields."""
    registry = ModelExtensionRegistry()
    with pytest.raises(HowlerValueError, match="Illegal extension field name"):
        registry.declare(ExtensionTarget, "Bad-Name!", optional(keyword()), plugin="plugin_one")

    with pytest.raises(HowlerValueError, match="Illegal extension field name"):
        registry.declare(ExtensionTarget, "__access_lvl__", optional(keyword()), plugin="plugin_one")

    with pytest.raises(HowlerValueError, match="Illegal extension field name"):
        registry.declare(ExtensionTarget, "id", optional(keyword()), plugin="plugin_one")


def test_declaration_after_finalization_is_rejected() -> None:
    """Once a target has been finalized, no further extensions may be declared for it."""
    registry = ModelExtensionRegistry()
    registry.declare(ExtensionTarget, "evidence", optional(keyword()), plugin="evidence")
    registry.finalize(ExtensionTarget)

    with pytest.raises(HowlerValueError, match="already been finalized"):
        registry.declare(ExtensionTarget, "late", optional(keyword()), plugin="late_plugin")


def test_finalize_is_idempotent() -> None:
    """Calling finalize twice for the same target returns the same cached derived model."""
    registry = ModelExtensionRegistry()
    registry.declare(ExtensionTarget, "evidence", optional(keyword()), plugin="evidence")
    first = registry.finalize(ExtensionTarget)
    second = registry.finalize(ExtensionTarget)
    assert first is second


def test_registry_instances_are_isolated() -> None:
    """Separate registry instances do not share pending or finalized state (cache isolation)."""
    registry_one = ModelExtensionRegistry()
    registry_two = ModelExtensionRegistry()

    registry_one.declare(ExtensionTarget, "only_in_one", optional(keyword()), plugin="p1")

    assert "only_in_one" in registry_one.pending(ExtensionTarget)
    assert registry_two.pending(ExtensionTarget) == {}

    finalized_one = registry_one.finalize(ExtensionTarget)
    assert "only_in_one" in finalized_one.model_fields

    # The second registry, with nothing declared, finalizes to the unmodified target.
    finalized_two = registry_two.finalize(ExtensionTarget)
    assert finalized_two is ExtensionTarget
    assert "only_in_one" not in finalized_two.model_fields


def test_disabled_extension_leaves_target_unmodified() -> None:
    """An extension that is never declared (e.g. a disabled feature) has no effect."""
    registry = ModelExtensionRegistry()
    # Simulate a feature flag being off: nothing is declared.
    finalized = registry.finalize(ExtensionTarget)
    assert finalized is ExtensionTarget
    assert "clue" not in finalized.model_fields


def test_extension_field_still_forbids_unknown_input() -> None:
    """Extra/unknown fields remain rejected on the finalized model, matching legacy strictness."""
    registry = ModelExtensionRegistry()
    registry.declare(ExtensionTarget, "evidence", optional(keyword()), plugin="evidence")
    finalized = registry.finalize(ExtensionTarget)

    with pytest.raises(ValidationError):
        finalized.model_validate({"target_id": "t1", "name": "n", "unknown_field": "value"})


def test_mapping_only_reflects_finalized_extensions() -> None:
    """The unfinalized target's mapping never includes pending, un-finalized extension fields."""
    registry = ModelExtensionRegistry()
    registry.declare(ExtensionTarget, "pending_field", optional(keyword()), plugin="plugin_one")

    # Mapping generated from the original target must not see the pending declaration.
    original_mapping = model_registry.mapping(ExtensionTarget)
    assert "pending_field" not in original_mapping["properties"]

    finalized = registry.finalize(ExtensionTarget)
    finalized_mapping = model_registry.mapping(finalized)
    assert "pending_field" in finalized_mapping["properties"]


def test_extension_preserves_auto_derived_id_field() -> None:
    """Extending a model keeps an inherited auto-derived ID that is not a declared field."""
    registry = ModelExtensionRegistry()
    registry.declare(User, "plugin_data", optional(keyword()), plugin="plugin_one")

    finalized = registry.finalize(User)

    assert "plugin_data" in finalized.model_fields
    assert model_registry.metadata(finalized).id_field == model_registry.metadata(User).id_field == "user_id"
