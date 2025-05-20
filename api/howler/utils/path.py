from __future__ import annotations

import os
import sys
from typing import Optional


def modulepath(modulename: str) -> str:
    "Get the path to a given mdule"
    m = sys.modules[modulename]
    f = getattr(m, "__file__", None)

    if not f:
        return os.path.abspath(os.getcwd())

    return os.path.dirname(os.path.abspath(f))


def splitpath(path: str, sep: Optional[str] = None) -> list:
    """Split the path into a list of items"""
    return list(filter(len, path.split(sep or os.path.sep)))


ASCII_NUMBERS = list(range(48, 58))
ASCII_UPPER_CASE_LETTERS = list(range(65, 91))
ASCII_LOWER_CASE_LETTERS = list(range(97, 123))
ASCII_OTHER = [45, 46, 92]  # "-", ".", and "\"
