import ipaddress
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


def try_parse_ip(ip: str) -> Optional[Union[ipaddress.IPv4Address, ipaddress.IPv6Address]]:
    "Try and parse an ipv4/ipv6 string into a date. Returns None if string is invalid."
    try:
        # Check if the value is an IP address
        return ipaddress.ip_address(ip)
    except ValueError:
        return None


def coerce(value: Union[list[str], str], fn: Callable[[str], Any]) -> Any:
    """Coerce a value of list of values using a given function or class.

    Will return an empty list if all results are None.
    """
    if isinstance(value, list):
        result: list = []
        for _value in value:
            if fn_result := fn(_value):
                result.append(fn_result)
        return result
    else:
        return fn(value)


def normalize_phrase(value: str, type: Union[Literal["phrase"], Literal["word"]]) -> list[str]:
    "Normalize a phrase or word for validation"
    if re.match(r"^[a-zA-Z0-9]+$", value):
        # probably an ID, no normalization
        return [value, value.lower()]

    if type == "word":
        value = re.sub(r"[^a-z0-9.,@_:/;()]", "", value.lower())
    else:
        value = re.sub(r"[^a-z0-9.,@_:/;() ]", "", value, flags=re.IGNORECASE)

    return [value]
