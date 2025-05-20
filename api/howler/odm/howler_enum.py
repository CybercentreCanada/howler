from enum import Enum, EnumMeta
from typing import Any


class HowlerEnumMeta(EnumMeta):
    "Meta class for Howler Enum Implementation"

    def __contains__(cls, obj: Any) -> bool:
        """Check if either the name or value contains the object"""
        lowercase = str(obj)
        uppercase = lowercase.upper().replace("-", "_")

        return uppercase in [e.name for e in cls] or lowercase in [e.value for e in cls]  # type: ignore

    def __getitem__(cls, name):
        return super().__getitem__(str(name).upper().replace("-", "_"))


class HowlerEnum(Enum, metaclass=HowlerEnumMeta):
    "Custom Enum Implementation for Howler"

    @classmethod
    def list(cls):
        "Convert the enum into a list"
        return list(map(lambda c: c.value, cls))
