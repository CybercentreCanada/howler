import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

with open(Path(__file__).parent.parent / "package.json") as package_json:
    version = json.load(package_json)["version"]
    base_version = re.sub(r"-dev.+", "", version)
    print(f"Current version: {base_version}")

    git_branch = os.getenv("BRANCH", None)
    if not git_branch:
        git_branch = (
            subprocess.check_output(shlex.split("git branch --show-current"))
            .decode()
            .strip()
        )

    if not git_branch:
        print("ERROR: No git branch provided!")
        sys.exit(1)

    git_branch = git_branch.replace("refs/heads/", "")

    print(f"Current Branch: {git_branch}")

    tag = os.getenv("BUILD_ID", "0")
    if git_branch.startswith("rc"):
        print("Current branch is an RC, updating version")

        subprocess.check_call(
            shlex.split(f"npm version --no-git-tag-version {base_version}-rc.{tag}")
        )

        sys.exit(0)
    if git_branch.startswith("patch"):
        print("Current branch is a patch, updating version")

        subprocess.check_call(
            shlex.split(f"npm version --no-git-tag-version {base_version}-patch.{tag}")
        )

        sys.exit(0)

    if git_branch != "main":
        print("Current branch is not main, marking as a development release")

        subprocess.check_call(
            shlex.split(f"npm version --no-git-tag-version {base_version}-dev.{tag}")
        )

        sys.exit(0)
