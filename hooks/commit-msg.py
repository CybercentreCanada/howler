#!/usr/bin/env python
# mypy: disable-error-code="import-untyped"
import re
import subprocess
import sys
from pathlib import Path

from conventional_pre_commit.format import ConventionalCommit
from conventional_pre_commit.output import fail
from rich.console import Console

console = Console()
commit_file = Path(sys.argv[1])
commit_msg = commit_file.read_text()

commit = ConventionalCommit(
    commit_msg=commit_msg,
    types=ConventionalCommit.DEFAULT_TYPES,
    scope_optional=True,
    scopes=["api", "client", "ui"],
)


current_branch = subprocess.run(
    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
    capture_output=True,
    text=True,
    check=True,
).stdout.strip()

issue = ""
if any(
    current_branch.startswith(prefix)
    for prefix in ["feature", "bugfix", "improvement", "task"]
):
    issue = re.sub(r".+/(.+)", r"\1", current_branch)

if not issue:
    console.print(
        "Could not link commit to issue.",
        style="yellow bold",
    )
if issue not in commit_msg:
    if str.isdigit(issue):
        commit_msg += f"\nRelated Issue: #{issue}\n"
    else:
        commit_msg += f"\nRelated Issue: {issue}\n"


if not commit.is_valid():
    if (
        current_branch in ["main", "develop"]
        or current_branch.startswith("patch")
        or current_branch.startswith("rc")
    ):
        print(fail(commit))
        sys.exit(1)

    console.print(
        "Your commit message does not follow Conventional Commits formatting. Allowing as branch is not main, develop, "
        "patch/* or rc/*",
        style="yellow bold",
    )

subject = commit_msg.splitlines()[0]
if subject != subject.lower():
    console.print(
        "Your summary should be lowercase, converting",
        style="yellow bold",
    )

commit_msg = commit_msg.replace(subject, subject.lower())

if commit_msg != commit_file.read_text():
    commit_file.write_text(commit_msg)
