"""Compatibility shims for symbols added in Python 3.11.

Import from this module instead of using `if sys.version_info` guards inline.
"""

import sys

if sys.version_info >= (3, 11):
    from enum import StrEnum
    from typing import NotRequired, TypedDict
else:
    from enum import Enum as _Enum

    class StrEnum(str, _Enum):  # type: ignore[no-redef]
        """str + Enum backport for Python < 3.11."""

    # typing_extensions.TypedDict supports Generic[T] mixing on Python < 3.11;
    # the stdlib version does not gain that until 3.11.
    from typing_extensions import NotRequired, TypedDict  # noqa: F401

__all__ = ["NotRequired", "StrEnum", "TypedDict"]
