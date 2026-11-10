"""Shared log model for hits and events."""

from __future__ import annotations

from typing import Any

from howler.common.exceptions import HowlerValueError
from howler.models import HowlerEmbeddedModel, date, enum, keyword, optional, register_model, text
from howler.models.constants import HowlerStrEnum


class LogOperationType(HowlerStrEnum):
    """Operation represented by a log entry."""

    APPENDED = "appended"
    REMOVED = "removed"
    SET = "set"


@register_model(index=True, store=True, description="Log definition.", embedded=True)
class Log(HowlerEmbeddedModel):
    """Log definition."""

    timestamp: date(description="Timestamp at which the Log event took place.")
    key: optional(keyword(), description="The key whose value changed.")
    explanation: optional(text(), description="A manual description of the changes made.")
    previous_version: optional(keyword(), description="The version this action was applied to.")
    new_value: optional(keyword(), description="The value the key is changing to.")
    type: optional(enum(values=LogOperationType), description="The operation performed on the value.")
    previous_value: optional(keyword(), description="The value the key is changing from.")
    user: keyword(description="User ID who created the log event.")

    def __init__(self, **data: Any) -> None:
        """Require complete change details without relying on Pydantic error wrapping."""
        if "explanation" not in data:
            required_keys = {"key", "new_value", "type", "previous_value"}
            if required_keys.intersection(data) != required_keys:
                raise HowlerValueError(
                    f"If no explanation provided, you must provide the following values: {','.join(required_keys)}"
                )
        super().__init__(**data)
