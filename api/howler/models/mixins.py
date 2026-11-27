"""Datastore convenience mixins for Howler models.

Provides :class:`DatastoreMixin`, a generic mixin that adds a class-level
``store`` property (returning a typed :class:`ESCollection`) and instance-level
``ds`` / ``save`` helpers so that model subclasses can interact with the
Elasticsearch datastore without boilerplate.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Generic, Literal, TypeVar, overload

from pydantic import BaseModel

from howler.common.exceptions import HowlerRuntimeError
from howler.common.loader import datastore
from howler.models.registry import model_registry
from howler.utils.compat import Self

if TYPE_CHECKING:
    from howler.datastore.collection import ESCollection

ModelType = TypeVar("ModelType", bound=BaseModel)


class _ObjectsDescriptor(Generic[ModelType]):
    """Descriptor that provides class-level-only access to the model's ESCollection.

    Intended to be accessed exclusively via the class (e.g. ``Case.store``).
    Raises ``HowlerRuntimeError`` if accessed from an instance to enforce
    class-level usage.
    """

    @overload
    def __get__(
        self: Self, obj: None, objtype: type[ModelType]
    ) -> ESCollection[ModelType]: ...  # codeql[py/ineffectual-statement]

    @overload
    def __get__(
        self: Self, obj: ModelType, objtype: type[ModelType]
    ) -> ESCollection[ModelType]: ...  # codeql[py/ineffectual-statement]

    def __get__(self, obj: ModelType | None, objtype: type[ModelType] | None = None) -> ESCollection[ModelType]:
        """Return the ESCollection for the owner class.

        Args:
            obj: The instance the descriptor was accessed from, or ``None``
                when accessed via the class.
            objtype: The owner class (e.g. ``Case``, ``Hit``).
        Returns:
            ESCollection[ModelType]: The datastore collection for *objtype*.
        Raises:
            HowlerRuntimeError: If accessed from an instance (*obj* is not ``None``)
                or if *objtype* cannot be determined.
        """
        if obj is not None:
            raise HowlerRuntimeError(
                f"'{type(obj).__name__}.store' is a class-level property and cannot be accessed from an instance. "
                f"Use '{type(obj).__name__}.store' instead."
            )

        if objtype is None:  # pragma: no cover
            raise HowlerRuntimeError("Cannot resolve owner class for 'store' descriptor.")

        index_name = objtype.__name__.lower()
        return datastore()[index_name]


class DatastoreMixin(Generic[ModelType]):
    """Mixin that provides convenience datastore access to model instances.

    Generic over ``ModelType`` so that the ``store`` class property returns a
    correctly-typed ``ESCollection[ModelType]``.  Adds a ``ds`` property for
    retrieving the shared datastore connection, a ``store`` class-only property
    for retrieving the model's ESCollection (raises ``HowlerRuntimeError`` if accessed
    from an instance), and a ``save`` method that persists the current model
    instance using its class name as the index and its registered ID field as the
    document key.
    """

    store: ClassVar[_ObjectsDescriptor] = _ObjectsDescriptor()

    @property
    def ds(self):
        """Return the shared datastore instance.

        Returns:
            The singleton datastore connection used for all persistence operations.
        """
        return datastore()

    def save(
        self: Self,
        refresh: Literal["true", "false", "wait_for"] | None = None,
        version: str | None = None,
    ) -> bool:
        """Persist the current model instance to the datastore.

        Determines the target index from the lowercase class name, extracts the
        model's ID from its registered ID field, and saves the instance.
        Returns:
            bool: True if the save operation succeeded, False otherwise.
        """
        if refresh is None:
            refresh = "wait_for"

        index_name = type(self).__name__.lower()
        id_field = model_registry.metadata(type(self)).id_field  # type: ignore[arg-type]
        current_id = self[id_field]  # type: ignore[index]
        collection = self.ds[index_name]  # type: ignore[attr-defined]

        return collection.save(current_id, self, version=version, refresh=refresh)
