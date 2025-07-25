import os
import re
from copy import copy
from typing import Any, Optional, Union

import chardet

from howler.common.exceptions import HowlerAttributeError, HowlerTypeError


def remove_bidir_unicode_controls(in_str):
    """Remove UBA characters"""
    try:
        no_controls_str = "".join(
            c
            for c in in_str
            if c
            not in [
                "\u202e",
                "\u202b",
                "\u202d",
                "\u202a",
                "\u200e",
                "\u200f",
            ]
        )
    except Exception:
        no_controls_str = in_str

    return no_controls_str


def wrap_bidir_unicode_string(uni_str):
    """Wraps str in a LRE (Left-to-Right Embed) unicode control.

    Guarantees that str can be concatenated to other strings without
    affecting their left-to-right direction
    """
    if len(uni_str) == 0 or isinstance(uni_str, bytes):  # Not str, return it unchanged
        return uni_str

    re_obj = re.search(r"[\u202E\u202B\u202D\u202A\u200E\u200F]", uni_str)
    if re_obj is None or len(re_obj.group()) == 0:  # No unicode bidir controls found, return string unchanged
        return uni_str

    # Parse str for unclosed bidir blocks
    count = 0
    for letter in uni_str:
        if letter in ["\u202a", "\u202b", "\u202d", "\u202e"]:  # bidir block open?
            count += 1
        elif letter == "\u202c":
            if count > 0:
                count -= 1

    # close all bidir blocks
    if count > 0:
        uni_str += "\u202c" * count

        # Final wrapper (LTR block) to neutralize any Marks (u+200E and u+200F)
    uni_str = "\u202a" + uni_str + "\u202c"

    return uni_str


# According to wikipedia, RFC 3629 restricted UTF-8 to end at U+10FFFF.
# This removed the 6, 5 and (irritatingly) half of the 4 byte sequences.
#
# The start byte for 2-byte sequences should be a value between 0xc0 and
# 0xdf but the values 0xc0 and 0xc1 are invalid as they could only be
# the result of an overlong encoding of basic ASCII characters. There
# are similar restrictions on the valid values for 3 and 4-byte sequences.
_valid_utf8 = re.compile(
    rb"""((?:
    [\x09\x0a\x20-\x7e]|             # 1-byte (ASCII excluding control chars).
    [\xc2-\xdf][\x80-\xbf]|          # 2-bytes (excluding overlong sequences).
    [\xe0][\xa0-\xbf][\x80-\xbf]|    # 3-bytes (excluding overlong sequences).

    [\xe1-\xec][\x80-\xbf]{2}|       # 3-bytes.
    [\xed][\x80-\x9f][\x80-\xbf]|    # 3-bytes (up to invalid code points).
    [\xee-\xef][\x80-\xbf]{2}|       # 3-bytes (after invalid code points).

    [\xf0][\x90-\xbf][\x80-\xbf]{2}| # 4-bytes (excluding overlong sequences).
    [\xf1-\xf3][\x80-\xbf]{3}|       # 4-bytes.
    [\xf4][\x80-\x8f][\x80-\xbf]{2}  # 4-bytes (up to U+10FFFF).
    )+)""",
    re.VERBOSE,
)


def _escape(t, reversible=True):
    if t[0] % 2:
        return t[1].replace(b"\\", b"\\\\") if reversible else t[1]
    else:
        return b"".join((b"\\x%02x" % x) for x in t[1])


def dotdump(s: Union[bytes, str, list[int]]):
    """Remove any non-ascii characters and replace them with periods

    https://www.cs.cmu.edu/~pattis/15-1XX/common/handouts/ascii.html
    """
    if isinstance(s, str):
        s = s.encode()

    return "".join(["." if x < 32 or x > 126 else chr(x) for x in s])


def escape_str(s, reversible=True, force_str=False):
    """Escape a string"""
    if isinstance(s, bytes):
        return escape_str_strict(s, reversible)
    elif not isinstance(s, str):
        if force_str:
            return str(s)
        return s

    try:
        return escape_str_strict(
            s.encode("utf-16", "surrogatepass").decode("utf-16").encode("utf-8"),
            reversible,
        )
    except Exception:
        return escape_str_strict(s.encode("utf-8", errors="backslashreplace"), reversible)


# Returns a string (str) with only valid UTF-8 byte sequences.
def escape_str_strict(s: bytes, reversible: bool = True) -> str:
    """Strictly escape a string"""
    escaped = b"".join([_escape(t, reversible) for t in enumerate(_valid_utf8.split(s))])
    return escaped.decode("utf-8")


def safe_str(s, force_str=False):
    """Create a safe, escaped string"""
    return escape_str(s, reversible=False, force_str=force_str)


def is_safe_str(s: str) -> bool:
    """Check if a given string is safe"""
    return escape_str(copy(s), reversible=False) == s


def translate_str(s: Union[str, bytes], min_confidence: float = 0.7) -> dict:
    """Translate a string from an arbitrary encoding to a python str"""
    if not isinstance(s, (str, bytes)):
        raise HowlerTypeError(f"Expected str or bytes got {type(s)}")

    if isinstance(s, str):
        s = s.encode("utf-8")

    try:
        r: Any = chardet.detect(s)
    except Exception:
        r = {"confidence": 0.0, "encoding": None, "language": None}

    if r["confidence"] > 0 and r["confidence"] >= min_confidence:
        try:
            t: Union[str, bytes] = s.decode(r["encoding"] or "utf-8")
        except Exception:
            t = s
    else:
        t = s

    r["converted"] = safe_str(t)
    r["encoding"] = r["encoding"] or "unknown"
    r["language"] = r["language"] or "unknown"

    return r  # type: ignore


# This method not really necessary. More to stop people from rolling their own.
def unescape_str(s):
    """unescape a string"""
    return s.decode("string_escape")


def truncate(data: Union[bytes, str], length: int = 100) -> str:
    """This method is a helper used to avoid cluttering output

    :param data: The buffer that will be determined if it needs to be sliced
    :param length: The limit of characters to the buffer
    :return str: The potentially truncated buffer
    """
    string = safe_str(data)
    if len(string) > length:
        return string[:length] + "..."
    return string


def default_string_value(
    *values: Optional[str], env_name: Optional[str] = None, default: Optional[str] = None
) -> Optional[str]:
    """Return a string value based on a list of potential values, an environmnet variable, or a default string"""
    return next(
        (val for val in values if val), (os.getenv(env_name, default or "") or default) if env_name else default
    )


def get_parent_key(key: str) -> str:
    """Get a parent key of a key in the format a.b.c"""
    return re.sub(r"^(.+)\..+?$", r"\1", key)


def sanitize_lucene_query(query: str):
    """Take in a given string, and escape it to ensure it is safe to search on via lucene"""
    query = re.sub(r'([\^"~*?:\\/()[\]{}\-!])', r"\\\1", query)

    return query.replace("&&", "\\&&").replace("||", "\\||")


class NamedConstants(object):
    """A class containing a list of named constants, as well as a reverse map for those constants to their name"""

    def __init__(self, name: str, string_value_list: list[tuple[str, Union[str, int]]]):
        self._name = name
        self._value_map = dict(string_value_list)
        self._reverse_map = dict([(s[1], s[0]) for s in string_value_list])

        # we also import the list as attributes so things like
        # tab completion and introspection still work.
        for s, v in self._value_map.items():
            setattr(self, s, v)

    def name_for_value(self, v):
        """Get the name of a given value"""
        return self._reverse_map[v]

    def contains_value(self, v):
        """Chgeck if this instance contains the given value"""
        return v in self._reverse_map

    def __getitem__(self, s):
        return self._value_map[s]

    def __getattr__(self, s):
        # We implement our own getattr mainly to provide the better exception.
        return self._value_map[s]


class StringTable(NamedConstants):
    """A subclass of NamedConstants that throws an attribute error if the value does not exist in the table"""

    def contains_string(self, s):
        """Chgeck if this instance contains the given value"""
        return s in self._reverse_map

    def __getitem__(self, s):
        if s in self._value_map:
            return s
        raise HowlerAttributeError("Invalid value for %s (%s)" % (self._name, s))

    def __getattr__(self, s):
        # We implement our own getattr mainly to provide the better exception.
        if s in self._value_map:
            return s
        raise HowlerAttributeError("Invalid value for %s (%s)" % (self._name, s))
