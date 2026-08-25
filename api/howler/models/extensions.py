"""Startup model extension registry for plugin- and Clue-declared fields.

Pydantic models cannot safely support the legacy ``add_namespace``/``remove_namespace``
post-definition descriptor mutation pattern. Plugins instead declare typed extension fields
against a target model before finalization. At startup, the registry finalizes one derived
model per target using ordinary Python subclassing through the target's own metaclass (the
same mechanism ``class Derived(Target): ...`` uses), and Elasticsearch mappings are only ever
generated from the finalized model, never the pre-extension target.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from howler.common.exceptions import HowlerValueError
from howler.models.fields import FIELD_SANITIZER
from howler.models.registry import BANNED_FIELDS, model_registry


@dataclass(frozen=True)
class ModelExtension:
    """A single plugin-declared field extension for a target model."""

    plugin: str
    name: str
    annotation: Any


class ModelExtensionRegistry:
    """Registry of pending model extensions, finalized once per target at startup."""

    def __init__(self) -> None:
        self._pending: dict[type[BaseModel], dict[str, ModelExtension]] = {}
        self._finalized: dict[type[BaseModel], type[BaseModel]] = {}

    def declare(self, target: type[BaseModel], name: str, annotation: Any, *, plugin: str) -> None:
        """Declare a typed extension field for a target model, before finalization.

        Raises on illegal field names, fields that already exist on the target, fields
        already declared by a different plugin, or declarations made after the target has
        already been finalized.
        """
        if target in self._finalized:
            raise HowlerValueError(f"{target.__name__} has already been finalized; cannot declare {name!r}")
        if not FIELD_SANITIZER.match(name) or name in BANNED_FIELDS:
            raise HowlerValueError(f"Illegal extension field name: {name}")
        if name in target.model_fields:
            raise HowlerValueError(f"Extension field {name!r} conflicts with an existing field on {target.__name__}")

        existing = self._pending.setdefault(target, {})
        if name in existing:
            raise HowlerValueError(
                f"Extension field {name!r} on {target.__name__} was already declared by plugin "
                f"{existing[name].plugin!r} (attempted redeclaration by {plugin!r})"
            )
        existing[name] = ModelExtension(plugin=plugin, name=name, annotation=annotation)

    def pending(self, target: type[BaseModel]) -> dict[str, ModelExtension]:
        """Return the extensions declared for a target, keyed by field name."""
        return dict(self._pending.get(target, {}))

    def is_finalized(self, target: type[BaseModel]) -> bool:
        """Return whether a target has already been finalized."""
        return target in self._finalized

    def finalize(
        self,
        target: type[BaseModel],
        *,
        description: str | None = None,
        id_field: str | None = None,
        index: bool | None = None,
        store: bool | None = None,
    ) -> type[BaseModel]:
        """Finalize one derived model combining the target with all declared extensions.

        Deterministic: extensions are applied in ``(plugin, field name)`` sorted order
        regardless of declaration order, so field order never depends on plugin load order.
        Idempotent: repeated calls for the same target return the same cached derived model
        instead of finalizing again. When metadata keyword arguments are omitted, the target's
        own registered metadata is reused so the mapping/id semantics do not change purely
        because of an extension.
        """
        if target in self._finalized:
            return self._finalized[target]

        extensions = sorted(self._pending.get(target, {}).values(), key=lambda item: (item.plugin, item.name))
        if not extensions:
            derived = target
        else:
            namespace = {
                "__annotations__": {extension.name: extension.annotation for extension in extensions},
                "__module__": target.__module__,
                "__qualname__": target.__qualname__,
            }
            # Ordinary Python subclassing through the target's own metaclass. Not descriptor
            # mutation: this creates a brand-new class, it never modifies `target` itself.
            derived = type(target)(target.__name__, (target,), namespace)  # type: ignore[misc]

        base_metadata = model_registry.metadata(target)
        model_registry.register(
            derived,
            description=description if description is not None else base_metadata.description,
            id_field=id_field if id_field is not None else base_metadata.id_field,
            index=index if index is not None else base_metadata.index,
            store=store if store is not None else base_metadata.store,
            embedded=base_metadata.embedded,
        )
        self._finalized[target] = derived
        return derived

    def clear(self) -> None:
        """Clear all pending and finalized state, primarily for isolated tests."""
        self._pending.clear()
        self._finalized.clear()


model_extensions = ModelExtensionRegistry()
