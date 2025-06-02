import os
import shlex
import subprocess
import sys

base_version = subprocess.check_output(shlex.split("poetry version -s")).decode().strip()

print(f"Current version: {base_version}")

git_branch = os.getenv("BRANCH", None)
if not git_branch:
    git_branch = subprocess.check_output(shlex.split("git branch --show-current")).decode().strip()

if not git_branch:
    print("ERROR: No git branch provided!")
    sys.exit(1)

git_branch = git_branch.replace("refs/heads/", "")

print(f"Current Branch: {git_branch}")

tag = os.getenv("BUILD_ID", "0")
if git_branch.startswith(("rc", "patch")):
    print("Current branch is an RC or patch, updating version")

    subprocess.check_call(shlex.split(f"poetry version {base_version}.rc{tag}"))

    sys.exit(0)

if git_branch != "main":
    print("Current branch is not main, marking as a development release")

    subprocess.check_call(shlex.split(f"poetry version {base_version}.dev{tag}"))

    sys.exit(0)
