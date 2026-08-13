from datetime import datetime, timezone
from typing import Literal, cast

from howler.common.exceptions import HowlerInvalidParameterException

ip_format_type = Literal["encoded_bytes", "int", "str"]


def parse_tz_datetime(value: str | None) -> datetime | None:
    """Parse a string into a timezone-aware datetime object.

    Non-tz-aware datetimes are assumed to be in UTC.

    Args:
        value (str | None): The string to parse.

    Returns:
        datetime | None: The parsed datetime object, or None if the input is None.

    Raises:
        HowlerInvalidParameterException: If the input string is not a valid ISO 8601 datetime.
    """
    if value is None:
        return None

    if value.endswith("Z"):
        value = value[:-1] + "+00:00"  # use '+00:00' for compatibility with py <= 3.10

    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        raise HowlerInvalidParameterException(f"Invalid datetime format: {value}")


def parse_ip_format(value: str | None) -> ip_format_type | None:
    """Parse the ip_format parameter.

    Args:
        value (str | None): The string to parse.

    Returns:
        ip_format_type | None: The parsed ip_format value, or None if the input is None.

    Raises:
        HowlerInvalidParameterException: If the input string is not one of the allowed values.
    """
    if value is None:
        return None

    value = value.lower()

    allowed_values = {"encoded_bytes", "int", "str"}
    if value not in allowed_values:
        raise HowlerInvalidParameterException(
            f"Invalid ip_format value: {value}. Allowed values are: {', '.join(allowed_values)}"
        )

    return cast(ip_format_type, value)
