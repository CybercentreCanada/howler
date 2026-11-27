"""Startup model extension registry for plugin- and Clue-declared fields.

Pydantic models cannot safely support the legacy ``add_namespace``/``remove_namespace``
post-definition descriptor mutation pattern. Plugins instead declare typed extension fields
against a target model before finalization. At startup, the registry finalizes one derived
model per target using ordinary Python subclassing through the target's own metaclass (the
same mechanism ``class Derived(Target): ...`` uses), and Elasticsearch mappings are only ever
generated from the finalized model, never the pre-extension target.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel
from pydantic.fields import FieldInfo

from howler.common.exceptions import HowlerValueError
from howler.models.fields import FIELD_SANITIZER
from howler.models.registry import BANNED_FIELDS, model_registry, serialized_field_name


@dataclass(frozen=True)
class ModelExtension:
    """A single plugin-declared field extension for a target model."""

    plugin: str
    name: str
    annotation: Any

    @property
    def serialized_name(self) -> str:
        """Return the Pydantic serialization name, including aliases on Annotated fields."""
        return serialized_field_name(self.name, FieldInfo.from_annotation(self.annotation))


class _ExtensionState:
    """The declarations and finalized classes from one composition."""

    def __init__(self) -> None:
        self._pending: dict[type[BaseModel], dict[str, ModelExtension]] = {}
        self._finalized: dict[type[BaseModel], type[BaseModel]] = {}


class ModelExtensionRegistry(_ExtensionState):
    """Registry of pending model extensions, finalized once per target at startup."""

    def __init__(self) -> None:
        super().__init__()
        self._scope: ContextVar[_ExtensionState] = ContextVar("howler_model_extensions")

    @contextmanager
    def isolated(self) -> Iterator[None]:
        """Compose fresh models in this context, including hooks holding this registry by reference."""
        token = self._scope.set(_ExtensionState())
        try:
            yield
        finally:
            self._scope.reset(token)

    def declare(self, target: type[BaseModel], name: str, annotation: Any, *, plugin: str) -> None:
        """Declare a typed extension field for a target model, before finalization.

        Raises on illegal field names, fields that already exist on the target, fields
        already declared by a different plugin, or declarations made after the target has
        already been finalized.
        """
        state = self._scope.get(self)
        if target in state._finalized:
            raise HowlerValueError(f"{target.__name__} has already been finalized; cannot declare {name!r}")
        extension = ModelExtension(plugin=plugin, name=name, annotation=annotation)
        serialized = extension.serialized_name
        names = {name, serialized}
        for candidate in names:
            if (
                not FIELD_SANITIZER.fullmatch(candidate)
                or candidate in BANNED_FIELDS
                or (candidate == "id" and not model_registry.metadata(target).embedded)
            ):
                raise HowlerValueError(f"Illegal extension field name: {candidate}")
        if not names.isdisjoint(target.model_fields) or not names.isdisjoint(model_registry.fields(target)):
            raise HowlerValueError(f"Extension field {name!r} conflicts with an existing field on {target.__name__}")

        existing = state._pending.setdefault(target, {})
        if name in existing:
            raise HowlerValueError(
                f"Extension field {name!r} on {target.__name__} was already declared by plugin "
                f"{existing[name].plugin!r} (attempted redeclaration by {plugin!r})"
            )
        for other in existing.values():
            if other.serialized_name == serialized:
                raise HowlerValueError(f"Duplicate serialized field name {serialized!r} on {target.__name__}")
            if not names.isdisjoint((other.name, other.serialized_name)):
                raise HowlerValueError(f"Extension field {name!r} conflicts with {other.name!r} from {other.plugin!r}")
        existing[name] = extension

    def pending(self, target: type[BaseModel]) -> dict[str, ModelExtension]:
        """Return the extensions declared for a target, keyed by field name."""
        return dict(self._scope.get(self)._pending.get(target, {}))

    def is_finalized(self, target: type[BaseModel]) -> bool:
        """Return whether a target has already been finalized."""
        return target in self._scope.get(self)._finalized

    def finalize(self, target: type[BaseModel]) -> type[BaseModel]:
        """Finalize one derived model combining the target with all declared extensions.

        Deterministic: extensions are applied in ``(plugin, field name)`` sorted order
        regardless of declaration order, so field order never depends on plugin load order.
        Idempotent: repeated calls for the same target return the same cached derived model
        instead of finalizing again. The target's own registered metadata is reused so the
        mapping/id semantics do not change purely because of an extension.
        """
        state = self._scope.get(self)
        if target in state._finalized:
            return state._finalized[target]

        extensions = sorted(state._pending.get(target, {}).values(), key=lambda item: (item.plugin, item.name))
        if not extensions:
            # Nothing to add: return the target
            # completely unmodified, without re-registering it. Re-registering unconditionally
            # here would resubmit the target's own *auto-derived* id_field (always a non-None
            # string) to ``model_registry.register``, which only validates an id_field against
            # the model's declared fields when it is not ``None`` - so a target that was
            # originally decorated without an explicit ``id_field`` (and therefore never had its
            # auto-derived guess validated) could suddenly fail finalization even though nothing
            # about it actually changed.
            state._finalized[target] = target
            return target

        namespace = {
            "__annotations__": {extension.name: extension.annotation for extension in extensions},
            "__module__": target.__module__,
            "__qualname__": target.__qualname__,
        }
        # Ordinary Python subclassing through the target's own metaclass. Not descriptor
        # mutation: this creates a brand-new class, it never modifies `target` itself.
        derived = type(target)(target.__name__, (target,), namespace)  # type: ignore[misc]

        model_registry.register_derived(derived, target)
        state._finalized[target] = derived
        return derived

    def clear(self) -> None:
        """Clear the active composition's pending declarations and finalized classes."""
        state = self._scope.get(self)
        state._pending.clear()
        state._finalized.clear()


model_extensions = ModelExtensionRegistry()
