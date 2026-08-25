"""Shared enums used across multiple Howler Pydantic models.

Mirrors ``howler.odm.constants`` and ``howler.odm.howler_enum``. Values are preserved exactly
since they surface in stored documents and public API responses. The stdlib ``Enum``/``str``
mixin does not stringify to the plain value by default, so ``HowlerStrEnum`` restores that
legacy behavior for the ``enum()`` field validator and any other ``str(member)`` use.
"""

from __future__ import annotations

from enum import Enum


class HowlerStrEnum(str, Enum):
    """A ``str`` enum whose ``str()`` representation is the member's value."""

    def __str__(self) -> str:
        return self.value

    @classmethod
    def list(cls) -> list[str]:
        """Return all member values."""
        return [member.value for member in cls]


class Status(HowlerStrEnum):
    """Status of a record in howler."""

    OPEN = "open"
    IN_PROGRESS = "in-progress"
    ON_HOLD = "on-hold"
    RESOLVED = "resolved"


class CaseEscalation(HowlerStrEnum):
    """Escalation of a case in Howler."""

    NORMAL = "normal"
    FOCUS = "focus"
    CRISIS = "crisis"
