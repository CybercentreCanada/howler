from datetime import datetime

from howler.common.exceptions import HowlerInvalidParameterException


def parse_datetime(value: str | None) -> datetime | None:
    """Parse a string into a datetime object.

    Args:
        value (str | None): The string to parse.

    Returns:
        datetime | None: The parsed datetime object, or None if the input is None.

    Raises:
        HowlerInvalidParameterException: If the input string is not a valid ISO 8601 datetime.
    """
    if value is None:
        return None

    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise HowlerInvalidParameterException(f"Invalid datetime format: {value}")
