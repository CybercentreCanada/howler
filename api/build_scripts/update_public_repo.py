#!.venv/bin/python

import filecmp
import fnmatch
import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path

INTERNAL_FILES = [
    ".ruff_cache",
    "build_scripts/generate_classes.py",
    "doc/CONTRIBUTING_INTERNAL.md",
    "docker/Dockerfile",
    "generate_howler_conf.sh",
    "howler/actions/spellbook.py",
    "howler/api/v1/alfred.py",
    "howler/api/v1/borealis.py",
    "howler/api/v1/notebook.py",
    "howler/api/v1/spellbook.py",
    "howler/odm/models/alfred.py",
    "howler/odm/models/domains_by_subtype.py",
    "howler/odm/models/email_authentication.py",
    "howler/odm/models/hbs.py",
    "howler/odm/models/neighbourhood_watch.py",
    "howler/services/alfred_service.py",
    "howler/services/notebook_service.py",
    "howler/utils/alfred_auth.py",
    "howler/utils/spellbook.py",
    "poetry.lock",
    "README.md",
    "static/classification.yml",
    "static/mitre",
    "test/integration/api/test_assemblyline.py",
    "test/integration/api/test_nw.py",
    "test/unit/actions/test_spellbook_integration.py",
    "test/unit/endpoints/test_notebook.py",
    "test/unit/odm/test_hbs.py",
    "test/unit/odm/test_neighbourhood_watch.py",
    "test/unit/services/test_alfred_service.py",
    "test/unit/services/test_notebook_service.py",
    "test/utils/oauth_credentials.py",
    "utils/spellbook.py",
]
"""The list of files that should be exclusive to the internal repository."""

# We'll also not copy anything we have marked in the .gitignore
GITIGNORE_FILES = [
    line.strip()
    for line in open(Path(__file__).parent.parent / ".gitignore", "r").readlines()
    if not line.startswith("#") and line.strip() != ""
]

PUBLIC_FILES = [
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".git",
    os.pardir,
    os.curdir,
    "generate_howler_conf.sh",
    "docker/Dockerfile",
    "static/mitre",
    "env",
    "venv",
    "enterprise-attack.json",
    "build_scripts/generate_md_doc.py",
    "README.md",
    ".dockerignore",
    "test/utils/oauth_credentials.py",
    "test/integration/api/test_nw.py",
    "doc/CONTRIBUTING.fr.md",
    ".coverage.pytest",
    ".coverage.server",
    ".venv",
    "poetry.lock",
    "api/v1/borealis.py",
]
"""Used when performing directory comparison to check for any deleted files in the internal repo that aren't
deleted in the public repo"""


def _input(prompt: str):
    try:
        return input(prompt)
    except KeyboardInterrupt:
        exit(1)


current_folder = Path(__file__).parent.parent

# Check the current branch. We should only really be copying from main, not during active development
branch = subprocess.check_output(["git", "branch", "--show-current"]).decode("utf-8").strip()
if branch != "main":
    print(
        "WARNING: This script should only be run after a release, and only from the main branch!\nYou are "
        f"currently on the branch '{branch}'."
    )
    answer = _input("Continue? [y/N] ")
    if answer.lower() != "y":
        exit(0)

# Preamble, ensure the list is correct
print(
    (
        "This script will update the public howler repo with any changes made internally, "
        "while removing CCCS specific files.\nThese files are specified in this script, and "
        "should be updated as necessary. The current list:"
    )
)
print("\n".join(f"\t{f}" for f in INTERNAL_FILES))

answer = _input("Is this correct? [Y/n] ")
if answer.lower() == "n":
    print("Please update the list, then rerun this script.")
    exit(0)

# Get the path of the public repo. For compatibility reasons, we allow the internal folder to be howler-api and
# assume the public one is kept in howler-api-public. Can be overriden in the script, OR using an env variable.
repo_path = Path(
    os.getenv(
        "HOWLER_PUBLIC_PATH",
        (
            current_folder.parent / "howler-api"
            if current_folder.name == "howler-api-internal"
            else current_folder.parent / "howler-api-public"
        ),
    )
)
print(f"The script will copy the changes in this repo into {repo_path}.")

answer = _input("Is this the correct path? [Y/n] ")

if answer.lower() == "n":
    new_path = _input("What path should be used?\n> ")
    repo_path = Path(new_path)

if not repo_path.exists():
    print(f"Error: the public repository does not exist at {repo_path}. Please create it.")
    exit(1)

# Ignore some basic files
builtin_ignore = shutil.ignore_patterns(
    ".git",
    "update_public_repo.py",
    "azure-pipelines.yml",
)


def _handle_path(path, names):
    """Handle the ignore step for each path provided"""
    print(f"  Copying files in {path}")
    ignored = builtin_ignore(path, names)

    # Check against the .gitignore
    for entry in GITIGNORE_FILES:
        if str((current_folder / entry).parent) == path or str(Path(entry).parent) == ".":
            for match in fnmatch.filter(names, Path(entry).name):
                ignored.add(match)

    # Check our internal files
    matching_paths = [
        entry or "*"
        for entry in INTERNAL_FILES
        if str((current_folder / entry).parent) == path or str(Path(entry).parent) == "."
    ]

    for path in matching_paths:
        name = Path(path).name
        for match in fnmatch.filter(names, name):
            ignored.add(match)
            print(f"    Ignoring {name}")

    return ignored


print("Beginning copy process")
shutil.copytree(
    current_folder,
    repo_path,
    ignore=_handle_path,
    dirs_exist_ok=True,
)


def check_diff_files(dcmp: filecmp.dircmp):
    """Function for recursively checking the folders of the public repo for files deleted in the internal repo"""
    for name in dcmp.right_only:
        print(
            f"{dcmp.right}/{name} exists in the public repo, but not in the internal repo. If this is expected, "
            "add it to PUBLIC_FILES in this script."
        )
        answer = _input("Remove this file? [y/N] ")
        if answer.lower() == "y":
            Path(f"{dcmp.right}/{name}").unlink()

    for sub_dcmp in dcmp.subdirs.values():
        check_diff_files(sub_dcmp)


print("Checking for mismatched files")
check_diff_files(
    filecmp.dircmp(
        current_folder,
        repo_path,
        ignore=PUBLIC_FILES,
    )
)


def check_ignored_files():
    """Function for recursively checking the folders of the public repo for files deleted in the internal repo"""
    for f in INTERNAL_FILES:
        if f in PUBLIC_FILES:
            continue

        if (repo_path / f).exists():
            print(
                f"{f} exists in the public repo, but is listed as an internal file. If this is expected, add it to "
                "PUBLIC_FILES in this script."
            )
            answer = _input("Remove this file? [y/N] ")
            if answer.lower() == "y":
                os.remove(repo_path / f)


print("Checking for ignored files")
check_ignored_files()


def check_for_internal_code():
    matches = (
        subprocess.check_output(
            [
                "grep",
                "-r",
                "-l",
                "--color=never",
                "# *internal: begin",
                "dev",
                "doc",
                "docker",
                "howler",
                "test",
                "static",
                "pyproject.toml",
                *list([str(p) for p in repo_path.glob(r"*.[pty][yxm]*")]),
            ],
            cwd=repo_path,
        )
        .decode()
        .splitlines()
    )

    for match in matches:
        print(f"  Removing internal code from {match}")

        file_data = (repo_path / match).read_text()
        file_data = re.sub(
            r"( *# ?internal: ?begin[\s\S]+?# ?internal: ?end)\n?",
            "",
            file_data,
            flags=(re.MULTILINE | re.IGNORECASE),
        )
        (repo_path / match).write_text(file_data)


print("Checking for internal code")
check_for_internal_code()

answer = _input("Do you want to commit? [Y/n] ")
if answer.lower() == "n":
    print("Exiting script.")
    exit(0)

# Stage everything
subprocess.call(["git", "add", "."], cwd=repo_path)

# Check for changes
result = subprocess.check_output(["git", "status", "--porcelain"], cwd=repo_path).splitlines()

if len(result) == 0:
    print("There are no changes to commit!")
    exit(0)

# By default, we base the commit message on the current version.
commit_message = f"Propagating internal changes from Howler {open(current_folder / 'version.txt', 'r').readlines()[0]}"

print(f'Default commit message: "{commit_message}"')
answer = _input("Do you want to edit the commit message? [y/N] ")
if answer.lower() == "y":
    commit_message = _input("What commit message should be used?\n> ")

# Run the commit
git_commit_command = shlex.split(f'git commit -m "{commit_message}"')
subprocess.call(git_commit_command, cwd=repo_path)

print("Committed! You will need to manually push your changes.")
