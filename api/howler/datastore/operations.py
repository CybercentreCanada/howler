from typing import Any, Iterator, Optional, Type

from howler.common.exceptions import HowlerTypeError, HowlerValueError
from howler.datastore.collection import ESCollection
from howler.odm.base import Model


class OdmHelper:
    def __init__(self, obj: Optional[Type[Model]] = None) -> None:
        self.model_name = obj.__name__ if obj else None
        self.valid_fields = list(obj.flat_fields().keys()) if obj else None
        self.fields = obj.flat_fields() if obj else {}

    def list_add(
        self,
        key: str,
        value: Any,
        explanation: Optional[str] = None,
        silent: bool = False,
        if_missing: bool = False,
    ):
        if self.valid_fields and not any(
            field for field in self.valid_fields if field.startswith(key) and self.fields[field].multivalued
        ):
            raise HowlerValueError(f"Key {key} not found in {self.model_name}")

        return OdmUpdateOperation(
            ESCollection.UPDATE_APPEND_IF_MISSING if if_missing else ESCollection.UPDATE_APPEND,
            key,
            value,
            explanation,
            silent,
        )

    def list_remove(
        self,
        key: str,
        value: Any,
        explanation: Optional[str] = None,
        silent: bool = False,
    ):
        if self.valid_fields and not any(
            field for field in self.valid_fields if field.startswith(key) and self.fields[field].multivalued
        ):
            raise HowlerValueError(f"Key {key} not found in {self.model_name}")

        return OdmUpdateOperation(
            ESCollection.UPDATE_REMOVE,
            key,
            value,
            explanation,
            silent,
        )

    def update(
        self,
        key: str,
        value: Any,
        explanation: Optional[str] = None,
        silent: bool = False,
    ):
        if self.valid_fields and key not in self.valid_fields:
            raise HowlerValueError(f"Key {key} not found in {self.model_name}")

        return OdmUpdateOperation(
            ESCollection.UPDATE_SET,
            key,
            value,
            explanation,
            silent,
        )


class OdmUpdateOperation:
    """Provide typing for ODM update operations.

    Attributes:
        operation: A string defining which operation to perform.
        key: A string defining which value on the ODM to update.
        value: The new value to set.
    """

    __slots__ = ["operation", "key", "value", "explanation", "silent"]

    operation: str
    key: str
    value: Any
    explanation: Optional[str]
    silent: bool

    def __init__(
        self,
        operation: str,
        key: str,
        value: Any,
        explanation: Optional[str] = None,
        silent: bool = False,
    ) -> None:
        if operation not in ESCollection.UPDATE_OPERATIONS:
            raise HowlerValueError(f"Operation {operation} not found in ESCollection.UPDATE_OPERATIONS")

        self.operation = operation

        if key is not None and not isinstance(key, str):
            raise HowlerTypeError("Key must be of type str")
        self.key = key
        self.value = value

        if explanation is not None and not isinstance(explanation, str):
            raise HowlerTypeError("Explanation must be of type str")
        self.explanation = explanation
        self.silent = silent

    def __iter__(self) -> Iterator[Any]:
        """Returns generator function for iterating over slots.

        Enables object destructuring:
        operation, key, value = odmOperation
        """
        for slot in self.__slots__:
            if slot in ["explanation", "silent"]:
                continue

            yield self.__getattribute__(slot)

    def __repr__(self) -> str:
        return (
            f"OdmUpdateOperation: operation={self.operation}, key={self.key}, "
            + f"value={self.value}, explanation={self.explanation}"
        )
