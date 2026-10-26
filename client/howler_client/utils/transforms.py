import json
import math
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from howler_client.common.exceptions import MappingError


def timestamp(value: str, assume_utc: bool = False) -> str:
    """Normalize an ISO-8601 timestamp to a UTC string with microseconds.

    Args:
        value: The ISO-8601 timestamp to normalize.
        assume_utc: Whether to treat a timezone-naive timestamp as UTC.
    """
    if not isinstance(value, str):
        raise MappingError("timestamp requires an ISO-8601 string")

    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    except (ValueError, OverflowError):
        raise MappingError("invalid ISO-8601 timestamp") from None

    if parsed.tzinfo is None:
        if not assume_utc:
            raise MappingError("timestamp has no timezone; explicitly set assume_timezone: UTC")
        parsed = parsed.replace(tzinfo=timezone.utc)

    normalized = parsed.astimezone(timezone.utc)
    return normalized.isoformat(timespec="microseconds").replace("+00:00", "Z")


def text(value: str) -> str:
    """Return a string value unchanged, rejecting non-string values.

    Args:
        value: The value to validate as text.
    """
    if not isinstance(value, str):
        raise MappingError("text transform requires a string")

    return value


def to_string(value: Any) -> str:
    """Convert a scalar JSON value to its canonical string representation.

    Args:
        value: The scalar value to convert.
    """
    if isinstance(value, (Mapping, list)):
        raise MappingError("use the json transform for structured values")

    return value if isinstance(value, str) else canonical_json(value)


def _template_parts(template: str) -> list[str | None]:
    """Split a literal template into text and ``{value}`` slots."""
    if not isinstance(template, str):
        raise MappingError("template transform requires a string template")

    parts: list[str | None] = []
    literal: list[str] = []
    index = 0
    while index < len(template):
        if template.startswith("{{", index):
            literal.append("{")
            index += 2
        elif template.startswith("}}", index):
            literal.append("}")
            index += 2
        elif template.startswith("{value}", index):
            if literal:
                parts.append("".join(literal))
                literal.clear()
            parts.append(None)
            index += len("{value}")
        elif template[index] in "{}":
            raise MappingError("invalid template syntax")
        else:
            literal.append(template[index])
            index += 1

    if literal:
        parts.append("".join(literal))
    return parts


def validate_template(template: str) -> None:
    """Validate template syntax without rendering or accessing a row value."""
    _template_parts(template)


def render_template(value: Any, template: str) -> str:
    """Render a scalar value into a safe, literal template."""
    parts = _template_parts(template)
    rendered_value = to_string(value)
    return "".join(rendered_value if part is None else part for part in parts)


def to_integer(value: Any) -> int:
    """Convert an integer-like number or string to an integer.

    Args:
        value: The value to convert.
    """
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, (int, str)) and not isinstance(value, bool):
        try:
            return int(value)
        except ValueError:
            pass
    raise MappingError("invalid integer conversion")


def to_number(value: Any) -> float:
    """Convert a finite numeric value or string to a floating-point number.

    Args:
        value: The value to convert.
    """
    try:
        result = float(value) if isinstance(value, (int, float, str)) and not isinstance(value, bool) else math.nan
    except (ValueError, OverflowError):
        result = math.nan
    if not math.isfinite(result):
        raise MappingError("invalid numeric conversion")
    return result


def to_boolean(value: Any) -> bool:
    """Convert a boolean or lowercase boolean string to a boolean.

    Args:
        value: The value to convert.
    """
    if isinstance(value, bool):
        return value

    if isinstance(value, str) and value in ("true", "false"):
        return value == "true"

    raise MappingError("boolean accepts only booleans or the strings true/false")


def dumps(value: Any, what: str = "value", **kwargs: Any) -> str:
    """Serialize a value as strict JSON without exposing invalid source values.

    Args:
        value: The value to serialize.
        what: The safe name to use when reporting a serialization error.
        **kwargs: Additional keyword arguments for ``json.dumps``.
    """
    try:
        return json.dumps(value, allow_nan=False, **kwargs)
    except (TypeError, ValueError, RecursionError):
        # Serializer messages can include source values; never echo them.
        raise MappingError(f"{what} is not valid JSON") from None


def normalize(value: Any, what: str = "value") -> Any:
    """Return a detached JSON copy of ``value``, rejecting invalid values.

    Args:
        value: The value to copy through JSON serialization.
        what: The safe name to use when reporting a serialization error.
    """
    return json.loads(dumps(value, what))


def canonical_json(value: Any) -> str:
    """Serialize a value to deterministic compact JSON.

    Args:
        value: The value to serialize.
    """
    return dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
