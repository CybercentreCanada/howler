"""Shared log model for hits and events."""

from __future__ import annotations

from typing import Any

from pydantic import model_validator

from howler.models import Date, HowlerEmbeddedModel, Keyword, Text, enum, register_model
from howler.models.constants import HowlerStrEnum


class LogOperationType(HowlerStrEnum):
    """Operation represented by a log entry."""

    APPENDED = "appended"
    REMOVED = "removed"
    SET = "set"


@register_model(index=True, store=True, description="Log definition.", embedded=True)
class Log(HowlerEmbeddedModel):
    """Log definition."""

    timestamp: Date
    """Timestamp at which the Log event took place."""
    key: Keyword | None = None
    """The key whose value changed."""
    explanation: Text | None = None
    """A manual description of the changes made."""
    previous_version: Keyword | None = None
    """The version this action was applied to."""
    new_value: Keyword | None = None
    """The value the key is changing to."""
    type: enum(values=LogOperationType, optional=True)
    """The operation performed on the value."""
    previous_value: Keyword | None = None
    """The value the key is changing from."""
    user: Keyword
    """User ID who created the log event."""

    @model_validator(mode="before")
    @classmethod
    def _require_explanation_or_details(cls, data: Any) -> Any:
        """Require complete change details when no explanation is provided."""
        if isinstance(data, dict) and "explanation" not in data:
            required_keys = {"key", "new_value", "type", "previous_value"}
            if required_keys.intersection(data) != required_keys:
                raise ValueError(
                    f"If no explanation provided, you must provide the following values: {','.join(required_keys)}"
                )
        return data
