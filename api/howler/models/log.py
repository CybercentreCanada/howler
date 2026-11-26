"""Shared log model for hits and events."""

from __future__ import annotations

from typing import Any

from pydantic import model_validator

from howler.models import HowlerEmbeddedModel, date, enum, keyword, register_model, text
from howler.models.constants import HowlerStrEnum


class LogOperationType(HowlerStrEnum):
    """Operation represented by a log entry."""

    APPENDED = "appended"
    REMOVED = "removed"
    SET = "set"


@register_model(index=True, store=True, description="Log definition.", embedded=True)
class Log(HowlerEmbeddedModel):
    """Log definition."""

    timestamp: date()
    """Timestamp at which the Log event took place."""
    key: keyword(optional=True)
    """The key whose value changed."""
    explanation: text(optional=True)
    """A manual description of the changes made."""
    previous_version: keyword(optional=True)
    """The version this action was applied to."""
    new_value: keyword(optional=True)
    """The value the key is changing to."""
    type: enum(values=LogOperationType, optional=True)
    """The operation performed on the value."""
    previous_value: keyword(optional=True)
    """The value the key is changing from."""
    user: keyword()
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
