#!/usr/bin/python3

import glob
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
    )
]

root = Path(__file__).parent.parent

lib_dir = root / "src"

print("Ensuring no banned imports are used in the lib directory: ", end="")

for filename in glob.glob(str(lib_dir / "**/*.ts*"), recursive=True):
    _file = Path(filename)
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
            sys.exit(1)

print("passed")
