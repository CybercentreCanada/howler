"""Validate native metadata and release refs for component publication workflows.

This read-only gate authorizes the channel, version, and tag outputs consumed by
the existing build and publish jobs. It does not build artifacts, mutate native
versions, or publish anything. The reusable workflow also verifies the GitHub
Release API for explicit dispatches.

Required environment: COMPONENT, COMPONENT_DIR, TAG_PREFIX, GITHUB_EVENT_NAME,
GITHUB_REF, GITHUB_SHA, and GITHUB_OUTPUT. GITHUB_EVENT_DELETED and
PUBLISH_RELEASE are optional and default to false; ALLOW_MAIN_PREVIEW is
optional and defaults to false (workflows pass it explicitly).

Outputs appended to GITHUB_OUTPUT after validation: channel (none, preview, or
stable), version (the native version for preview/stable, otherwise empty), and
tag (the stable tag, otherwise empty).
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
from importlib import import_module
from pathlib import Path
from typing import cast

# The workflow uses Python 3.12; load tomllib dynamically for Ruff's py310 target.
tomllib = import_module("tomllib")

REPO_ROOT = Path(__file__).resolve().parents[1]
VERSION_PATTERN = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)")


def required_env(name: str) -> str:
    """Read a required Actions environment value with a useful error."""
    value = os.environ.get(name)
    if value is None:
        raise ValueError(f"required environment variable {name} is missing")
    return value


def read_native_version(component: str, component_dir: Path) -> str:
    """Read, but never rewrite, the component's checked-in version metadata."""
    # UI is the one JSON package; the Python packages use a literal TOML
    # project.version or legacy tool.poetry.version value.
    if component == "ui":
        metadata_path = component_dir / "package.json"
        with metadata_path.open(encoding="utf-8") as package_file:
            metadata = json.load(package_file)

        native_version = (
            cast(dict[str, object], metadata).get("version")
            if isinstance(metadata, dict)
            else None
        )
    else:
        metadata_path = component_dir / "pyproject.toml"
        with metadata_path.open("rb") as project_file:
            project = tomllib.load(project_file)

        project_table = project.get("project", {})
        tool_table = project.get("tool", {})
        poetry_table: object = {}
        if isinstance(tool_table, dict):
            poetry_table = cast(dict[str, object], tool_table).get("poetry", {})

        native_version = (
            cast(dict[str, object], project_table).get("version")
            if isinstance(project_table, dict)
            else None
        )
        if not native_version and isinstance(poetry_table, dict):
            native_version = cast(dict[str, object], poetry_table).get("version")

    # Requiring plain X.Y.Z prevents prereleases, build metadata, and leading
    # zeroes from becoming ambiguous stable tag or artifact versions.
    if not isinstance(native_version, str) or not VERSION_PATTERN.fullmatch(
        native_version
    ):
        raise ValueError(
            f"{component} native version must be canonical stable X.Y.Z: {native_version!r}"
        )
    return native_version


def git_text(*args: str) -> str:
    """Run a read-only git query from the repository root."""
    return run_git(*args).stdout.strip()


def run_git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run git by its resolved executable path from the repository root."""
    git = shutil.which("git")
    if git is None:
        raise FileNotFoundError("git executable was not found on PATH")
    return subprocess.run(
        [git, *args],
        cwd=REPO_ROOT,
        check=check,
        capture_output=True,
        text=True,
    )


def validate_release() -> tuple[str, str, str, str, str]:
    """Resolve and verify the publication channel without changing metadata."""
    component = required_env("COMPONENT")
    component_dir_value = Path(required_env("COMPONENT_DIR"))
    component_dir = (REPO_ROOT / component_dir_value).resolve()
    # COMPONENT_DIR is a static workflow value; also ensure a bad edit cannot
    # make the metadata reader follow a path outside the checked-out repository.
    try:
        component_dir.relative_to(REPO_ROOT)
    except ValueError as error:
        raise ValueError(
            "COMPONENT_DIR must stay inside the checked-out repository"
        ) from error
    if not component_dir.is_dir():
        raise ValueError(f"component directory does not exist: {component_dir_value}")

    tag_prefix = required_env("TAG_PREFIX")
    if not tag_prefix:
        raise ValueError("TAG_PREFIX must not be empty")
    event = required_env("GITHUB_EVENT_NAME")
    ref = required_env("GITHUB_REF")
    run_sha = required_env("GITHUB_SHA")
    output_path = required_env("GITHUB_OUTPUT")
    publish_requested = os.environ.get("PUBLISH_RELEASE", "false").lower() == "true"
    deleted = os.environ.get("GITHUB_EVENT_DELETED", "false").lower() == "true"
    allow_main_preview = os.environ.get("ALLOW_MAIN_PREVIEW", "false").lower() == "true"

    # Read native package metadata before resolving refs, so malformed component
    # versions fail closed even when the current event resolves to no channel.
    native_version = read_native_version(component, component_dir)

    # An explicit dispatch opts into stable publication only on this component's
    # tag. Main-branch previews are separately opt-in, for images/npm only; the
    # Python package workflows never enable that path to PyPI.
    channel = "none"
    release_tag = ""
    if event == "workflow_dispatch":
        if publish_requested:
            if not ref.startswith("refs/tags/"):
                raise ValueError(
                    "publish_release=true is allowed only for a native component tag"
                )
            release_tag = ref.removeprefix("refs/tags/")
            if not release_tag.startswith(tag_prefix):
                raise ValueError(
                    f"dispatch tag must start with {tag_prefix!r}: {release_tag}"
                )
            channel = "stable"
    elif event == "push" and not deleted:
        if ref == "refs/heads/main" and allow_main_preview:
            channel = "preview"
        elif ref.startswith("refs/tags/"):
            candidate = ref.removeprefix("refs/tags/")
            if candidate.startswith(tag_prefix):
                release_tag = candidate
                channel = "stable"

    if channel == "stable":
        tag_version = release_tag.removeprefix(tag_prefix)
        if not VERSION_PATTERN.fullmatch(tag_version):
            raise ValueError(
                f"native release tag is not canonical X.Y.Z: {release_tag}"
            )
        if tag_version != native_version:
            raise ValueError(
                f"{component} native version {native_version} does not match tag {release_tag}"
            )

        # The checkout, event SHA, and peeled tag must identify one commit; this
        # catches a workflow publishing from an unintended checkout or tag target.
        head = git_text("rev-parse", "HEAD")
        if head != run_sha:
            raise ValueError(
                f"checked-out HEAD {head} does not match run SHA {run_sha}"
            )
        tag_commit = git_text("rev-parse", f"refs/tags/{release_tag}^{{commit}}")
        if head != tag_commit:
            raise ValueError(
                f"tag {release_tag} peels to {tag_commit}, not checked-out HEAD {head}"
            )

        # Refresh main before checking ancestry. This accepts older legitimate
        # releases while rejecting tags on commits that never reached main.
        run_git(
            "fetch",
            "origin",
            "+refs/heads/main:refs/remotes/origin/main",
            "--no-tags",
        )
        ancestry = run_git(
            "merge-base",
            "--is-ancestor",
            tag_commit,
            "refs/remotes/origin/main",
            check=False,
        )
        if ancestry.returncode != 0:
            raise ValueError(f"tag {release_tag} is not an ancestor of origin/main")

    output_version = native_version if channel in {"preview", "stable"} else ""
    return component, channel, output_version, release_tag, output_path


def main() -> int:
    """Validate first, then expose only the verified outputs to downstream jobs."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger = logging.getLogger(__name__)
    try:
        component, channel, version, release_tag, output_path = validate_release()
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        logger.error("Release validation failed: %s", error)
        return 1

    # Do not publish a channel output until every applicable metadata, tag, SHA,
    # and ancestry check has passed; downstream privileged jobs key off these.
    try:
        with Path(output_path).open("a", encoding="utf-8") as output:
            output.write(f"channel={channel}\nversion={version}\ntag={release_tag}\n")
    except OSError as error:
        logger.error(
            "Release validation failed while writing Actions outputs: %s", error
        )
        return 1
    logger.info(
        "Validated %s: channel=%s, version=%s", component, channel, version or "(none)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
