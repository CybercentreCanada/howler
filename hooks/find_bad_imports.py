#!/usr/bin/python3

import glob
import re
import sys
import textwrap
from pathlib import Path

BANNED_STRINGS = [
    (
        "@mui/icons-material/",
        [
            "Using @mui/icons-material/SomeIcon in exported components leads to issues when extending howler's "
            "functionality: https://stackoverflow.com/questions/78815858/mui-icons-material-vitest-es-module-issue ",
            "Instead, use import { SomeIcon } from '@mui/icons-material'",
        ],
    ),
    (
        "@iconify/react/dist/iconify.js",
        [
            "Instead of using the import '@iconify/react/dist/iconify.js', you should use '@iconify/react'.",
        ],
    ),
]

# Matches: import { type A, type B } from '...' (all named imports are type-only)
# These should instead use: import type { A, B } from '...'
_TYPE_ONLY_NAMED_IMPORT_RE = re.compile(
    r"\bimport\s*\{((?:\s*type\s+\w+(?:\s+as\s+\w+)?\s*,?\s*)*)\}\s*from\s*[\'\"]\s*",
    re.MULTILINE,
)

root = Path(__file__).parent.parent / "ui"

src_dir = root / "src"

print("Ensuring no banned imports are used in the src directory: ", end="")

error = False

for filename in glob.glob(str(src_dir / "**/*.ts*"), recursive=True):
    _file = Path(filename)

    if str(_file.relative_to(src_dir)).startswith("commons"):
        continue

    data = _file.read_text()

    for banned_string, explanations in BANNED_STRINGS:
        if banned_string in data:
            print("failed")

            wrapped_explanation = []
            for explanation in explanations:
                wrapped_explanation += textwrap.wrap(explanation, width=120)

            margin = "\n" + (len(banned_string) + 4) * " "

            print(f"ERROR: {_file.relative_to(root)} contains a banned string:")
            print(f"> {banned_string}: {margin.join(wrapped_explanation)}")

            error = True

    for match in _TYPE_ONLY_NAMED_IMPORT_RE.finditer(data):
        members = [m.strip() for m in match.group(1).split(",") if m.strip()]
        if members and all(m.startswith("type ") for m in members):
            print("failed")
            print(
                f"ERROR: {_file.relative_to(root)} has a type-only named import that should use 'import type' syntax:"
            )
            print(f"> {match.group(0)!r}")
            print(
                ">   Use: import type {{ X, Y }} from '...' instead of import {{ type X, type Y }} from '...'"
            )
            error = True

if error:
    sys.exit(1)

print("passed")
