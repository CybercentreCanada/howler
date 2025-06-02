#!env/bin/python

import filecmp
import fnmatch
import glob
import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path

current_folder = Path(__file__).parent.parent

BLACK_LIST = [
    "pom.xml",
    "setup.py",
    "generate_classes.py",
    "azure_pipelines.yml",
    "test/test_server.Dockerfile",
    "test/integration/test_nw.py",
]
"""The list of files that should be exclusive to the internal repository."""

# We'll also not copy anything we have marked in the .gitignore
GITIGNORE_FILES = [
    line.strip()
    for line in (current_folder / ".gitignore").open("r").readlines()
    if not line.startswith("#") and line.strip() != ""
]

PUBLIC_FILES = [
    "__pycache__",
    ".mypy_cache",
    ".git",
    os.pardir,
    os.curdir,
    "target",
    "LICENSE",
    "azure_pipelines.yml",
    "README.fr.md",
    ".venv",
]
"""
Used when performing directory comparison to check for any deleted files in the
internal repo that aren't deleted in the public repo.
"""


def _input(prompt: str):
    try:
        return input(prompt)
    except KeyboardInterrupt:
        exit(1)


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
print("\n".join(f"\t{f}" for f in BLACK_LIST))

_BLACK_LIST = [glob.glob(entry, recursive=True) for entry in BLACK_LIST]
BLACK_LIST = []
for entry in _BLACK_LIST:
    BLACK_LIST.extend(entry)

answer = _input("Is this correct? [Y/n] ")
if answer.lower() == "n":
    print("Please update the list, then rerun this script.")
    exit(0)

# Get the path of the public repo. For compatibility reasons, we allow the internal folder to be howler-client and
# assume the public one is kept in howler-client-public. Can be overriden in the script, OR using an env variable.
repo_path = Path(
    os.getenv(
        "HOWLER_PUBLIC_PATH",
        (
            current_folder.parent / "howler-client"
            if current_folder.name == "howler-client-python-internal"
            else current_folder.parent / "howler-client-public"
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
        for entry in BLACK_LIST
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
        if str((Path(dcmp.right) / name).relative_to(repo_path)) in PUBLIC_FILES:
            continue

        print(
            f"{dcmp.right}/{name} exists in the public repo, but not in the internal repo. If this is expected, add "
            "it to PUBLIC_FILES in this script."
        )
        answer = _input("Remove this file? [y/N] ")
        if answer.lower() == "y":
            try:
                os.remove(f"{dcmp.right}/{name}")
            except IsADirectoryError:
                shutil.rmtree(f"{dcmp.right}/{name}")

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
    for f in BLACK_LIST:
        if f in PUBLIC_FILES:
            continue

        file_path = repo_path / f
        if file_path.exists():
            print(
                f"{f} exists in the public repo, but is listed as an internal file. If this is expected, add it to "
                "PUBLIC_FILES in this script."
            )
            answer = _input("Remove this file? [y/N] ")
            if answer.lower() == "y":
                if file_path.is_file():
                    file_path.unlink()
                else:
                    shutil.rmtree(str(file_path))


print("Checking for ignored files")
check_ignored_files()


def check_for_internal_code():
    try:
        matches = (
            subprocess.check_output(
                [
                    "grep",
                    "-r",
                    "-l",
                    "--color=never",
                    "internal: begin",
                    "howler_client",
                    "test",
                    *list([str(p) for p in repo_path.glob(r"*.[pts][yxh]*")]),
                    *list([str(p) for p in repo_path.glob(r"*.[pts][yxh]*")]),
                ],
                cwd=repo_path,
            )
            .decode()
            .splitlines()
        )
    except subprocess.CalledProcessError as e:
        if e.returncode == 1:
            print("  No internal code found!")
            return
        else:
            raise e

    for match in matches:
        print(f"  Removing internal code from {match}")

        file_data = (repo_path / match).read_text()
        file_data = re.sub(
            r"( *# ?internal: ?begin[\s\S]+?# ?internal: ?end)\n?",
            "",
            file_data,
            flags=(re.MULTILINE | re.IGNORECASE),
        )
        file_data = re.sub(
            r"( *// ?internal: ?begin[\s\S]+?// ?internal: ?end)\n?",
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
commit_message = (
    "Propagating internal changes from " f"Howler {(current_folder / 'version.txt').read_text().splitlines()[0]}"
)

print(f'Default commit message: "{commit_message}"')
answer = _input("Do you want to edit the commit message? [y/N] ")
if answer.lower() == "y":
    commit_message = _input("What commit message should be used?\n> ")

# Run the commit
git_commit_command = shlex.split(f'git commit -m "{commit_message}"')
subprocess.call(git_commit_command, cwd=repo_path)

print("Committed! You will need to manually push your changes.")
