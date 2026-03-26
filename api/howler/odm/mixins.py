"""Datastore convenience mixins for Howler ODM Model classes.
Provides :class:`DatastoreMixin`, a generic mixin that adds a class-level
``store`` property (returning a typed :class:`ESCollection`) and instance-level
``ds`` / ``save`` helpers so that Model subclasses can interact with the
Elasticsearch datastore without boilerplate.
"""

from __future__ import annotations

from operator import attrgetter
from typing import Generic, TypeVar, overload

from howler.common.loader import datastore
from howler.datastore.collection import ESCollection
from howler.odm.base import Model

ModelType = TypeVar("ModelType", bound=Model)


class _ObjectsDescriptor(Generic[ModelType]):
    """Descriptor that provides class-level-only access to the model's ESCollection.
    Intended to be accessed exclusively via the class (e.g. ``Case.store``).
    Raises ``AttributeError`` if accessed from an instance to enforce
    class-only usage.
    """

    @overload
    def __get__(self, obj: None, objtype: type[ModelType]) -> ESCollection[ModelType]: ...

    @overload
    def __get__(self, obj: ModelType, objtype: type[ModelType]) -> ESCollection[ModelType]: ...

    def __get__(self, obj: ModelType | None, objtype: type[ModelType] | None = None) -> ESCollection[ModelType]:
        """Return the ESCollection for the owner class.
        Args:
            obj: The instance the descriptor was accessed from, or ``None``
                when accessed via the class.
            objtype: The owner class (e.g. ``Case``, ``Hit``).
        Returns:
            ESCollection[ModelType]: The datastore collection for *objtype*.
        Raises:
            AttributeError: If accessed from an instance (*obj* is not ``None``)
                or if *objtype* cannot be determined.
        """
        if obj is not None:
            raise AttributeError(
                f"'{type(obj).__name__}.store' is a class-level property and cannot be accessed from an instance. "
                f"Use '{type(obj).__name__}.store' instead."
            )
        if objtype is None:
            raise AttributeError("Cannot resolve owner class for 'store' descriptor.")
        index_name = objtype.__name__.lower()
        return datastore()[index_name]


class DatastoreMixin(Generic[ModelType]):
    """Mixin that provides convenience datastore access to Model instances.

    Generic over ``ModelType`` so that the ``store`` class property returns a
    correctly-typed ``ESCollection[ModelType]``.  Adds a ``ds`` property for
    retrieving the shared datastore connection, a ``store`` class-only property
    for retrieving the model's ESCollection (raises ``AttributeError`` if accessed
    from an instance), and a ``save`` method that persists the current model
    instance using its class name as the index and its configured ID field as the
    document key.
    """

    store = _ObjectsDescriptor()

    @property
    def ds(self):
        """Return the shared datastore instance.

        Returns:
            The singleton datastore connection used for all persistence operations.
        """
        return datastore()

    def save(self) -> bool:
        """Persist the current model instance to the datastore.

        Determines the target index from the lowercase class name, extracts the
        model's ID from the configured ID field, and saves the instance.
        Returns:
            bool: True if the save operation succeeded, False otherwise.
        """
        index_name = self.__class__.__name__.lower()
        id_field = self.__class__._Model__id_field
        current_id = attrgetter(id_field)(self)

        return self.ds[index_name].save(current_id, self)
