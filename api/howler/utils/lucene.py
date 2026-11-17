import ipaddress
import math
import re
import sys
from datetime import datetime
from typing import Any, Callable, Literal, Optional

from howler.api import Union


def try_parse_date(date: str) -> Optional[datetime]:
    "Try and parse an ISO-formatted string into a date. Returns None if string is invalid."
    try:
        # Check if the value is a ISO-formatted date
        if sys.version_info.major < 11:
            return datetime.strptime(date, "%Y-%m-%dT%H:%M:%S.%f%z")
        else:
            return datetime.fromisoformat(date)
    except (ValueError, TypeError):
        return None


def try_parse_number(number: str | int | float | None) -> int | float | None:
    "Try and parse a number string into an integer or float type, or infinity. Returns None if string is invalid."
    if number is None or isinstance(number, bool):
        return None

    if isinstance(number, (int, float)):
        return number

    lowered = number.lower()
    if lowered in ("infinity", "+infinity"):
        return math.inf
    if lowered == "-infinity":
        return -math.inf

    try:
        # Check if the value is an integer
        return int(number)
    except ValueError:
        try:
            # Check if the value is a float
            return float(number)
        except ValueError:
            return None


def try_parse_ip(ip: str) -> Optional[Union[ipaddress.IPv4Address, ipaddress.IPv6Address]]:
    "Try and parse an ipv4/ipv6 string into a date. Returns None if string is invalid."
    try:
        # Check if the value is an IP address
        return ipaddress.ip_address(ip)
    except ValueError:
        return None


def coerce(value: Union[list[Any], Any], fn: Callable[[Any], Any]) -> Any:
    """Coerce a value of list of values using a given function or class.

    Will return an empty list if all results are None.
    """
    if value is None:
        return None

    if isinstance(value, list):
        result: list = []
        for _value in value:
            if (fn_result := fn(_value)) is not None:
                result.append(fn_result)
        return result
    else:
        return fn(value)


def normalize_phrase(
    value: str,
    type: Union[Literal["phrase"], Literal["word"]],
    *,
    case_insensitive: bool = False,
) -> list[str]:
    "Normalize a phrase or word for validation"
    target_value = value.lower() if case_insensitive else value

    if re.match(r"^[a-zA-Z0-9]+$", target_value):
        # probably an ID, no normalization
        return [target_value]

    candidates: list[str] = []
    if type == "word":
        candidates.append(re.sub(r"[^A-Za-z0-9.,@_:/;()\-]", "", target_value))
        # For values that contain spaces (e.g. process.command_line), also include a
        # space-preserved candidate so that wildcard patterns with escaped spaces can match.
        if " " in target_value:
            candidates.append(re.sub(r"[^A-Za-z0-9.,@_:/;()\- ]", "", target_value))
    else:
        candidates.append(re.sub(r"[^A-Za-z0-9.,@_:/;()\- ]", "", target_value))

    candidates.append(target_value)
    return list(dict.fromkeys(candidates))
