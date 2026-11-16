#!/usr/bin/env python3
"""Summarize changes between a base Git reference and HEAD/working tree by category."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

GROUPS_ORDER: tuple[str, ...] = ("Code", "Tests", "Configs", "Non-Code")

SUBCATEGORIES_ORDER: dict[str, tuple[str, ...]] = {
    "Code": (
        "API",
        "UI",
        "Client",
        "MCP",
        "Plugin: Evidence",
        "Plugin: Sentinel",
        "Plugin: Sync",
        "Scripts & Hooks",
        "Other",
    ),
    "Tests": (
        "Unit",
        "Integration & Network",
        "Fixtures & Test Infra",
    ),
    "Configs": (
        "Package & Tooling",
        "CI & GitHub",
        "Deploy, Infra & Containers",
        "App & Schema Configs",
    ),
    "Non-Code": (
        "Docs & Changelogs",
        "Agent & Skill Guides",
        "Lockfiles",
        "Generated Code",
        "Translations & Static Assets",
    ),
}

PACKAGES_ORDER: tuple[str, ...] = (
    "api",
    "ui",
    "client",
    "mcp",
    "evidence",
    "sentinel",
    "sync",
    "helm/infra",
    "docs",
    "root",
)

LOCKFILE_NAMES: frozenset[str] = frozenset(
    {
        "poetry.lock",
        "pnpm-lock.yaml",
        "package-lock.json",
        "yarn.lock",
        "skills-lock.json",
        "Cargo.lock",
        "Gemfile.lock",
    }
)

TOOLING_CONFIG_NAMES: frozenset[str] = frozenset(
    {
        "pyproject.toml",
        "poetry.toml",
        "setup.cfg",
        "setup.py",
        "MANIFEST.in",
        "pytest.ini",
        "tox.ini",
        ".flake8",
        "package.json",
        "pnpm-workspace.yaml",
        "tsconfig.json",
        ".oxlintrc.json",
        ".oxfmtrc.json",
        ".pre-commit-config.yaml",
        ".release-please-config.json",
        ".release-please-manifest.json",
        ".python-version",
        ".nvmrc",
        ".gitignore",
        ".eslintignore",
        ".gitattributes",
        ".editorconfig",
        ".gitkeep",
    }
)

SCRIPT_EXTENSIONS: frozenset[str] = frozenset(
    {".py", ".pyi", ".sh", ".bash", ".zsh", ".js", ".mjs", ".cjs", ".ts"}
)

CODE_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".py",
        ".pyi",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".mjs",
        ".cjs",
        ".sh",
        ".bash",
        ".zsh",
        ".go",
        ".rs",
        ".java",
        ".c",
        ".cc",
        ".cpp",
        ".h",
        ".sql",
        ".css",
        ".scss",
        ".html",
    }
)

CONFIG_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".yml",
        ".yaml",
        ".toml",
        ".json",
        ".jsonc",
        ".ini",
        ".cfg",
        ".conf",
        ".properties",
        ".gql",
        ".graphql",
        ".tpl",
    }
)

DOC_EXTENSIONS: frozenset[str] = frozenset({".md", ".mdx", ".rst", ".txt", ".adoc"})

ASSET_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".svg",
        ".ico",
        ".webp",
        ".woff",
        ".woff2",
        ".ttf",
        ".eot",
        ".pdf",
    }
)

UI_TEST_SUFFIXES: tuple[str, ...] = (
    ".test.ts",
    ".test.tsx",
    ".test.js",
    ".test.jsx",
    ".spec.ts",
    ".spec.tsx",
    ".spec.js",
    ".spec.jsx",
)

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


class DiffSummaryError(RuntimeError):
    """Expected Git or CLI resolution error for diff summary generation."""


@dataclass
class FileChange:
    """Line-level change record for a single repository path."""

    path: str
    group: str
    subcategory: str
    package: str
    added: int = 0
    deleted: int = 0
    is_binary: bool = False
    is_untracked: bool = False
    renamed_from: str | None = None

    @property
    def net(self: FileChange) -> int:
        """Return net added minus deleted lines."""
        return self.added - self.deleted

    @property
    def churn(self: FileChange) -> int:
        """Return total changed lines (added plus deleted)."""
        return self.added + self.deleted


@dataclass
class BucketStats:
    """Aggregated file and line metrics for a category or package."""

    files: int = 0
    binary_files: int = 0
    added: int = 0
    deleted: int = 0

    @property
    def net(self: BucketStats) -> int:
        """Return net line delta."""
        return self.added - self.deleted

    @property
    def churn(self: BucketStats) -> int:
        """Return total line churn."""
        return self.added + self.deleted

    def add_file(self: BucketStats, change: FileChange) -> None:
        """Accumulate a single file change into this bucket."""
        self.files += 1
        if change.is_binary:
            self.binary_files += 1
        self.added += change.added
        self.deleted += change.deleted


@dataclass
class PackageStats:
    """Aggregated metrics for a package/area, split by Code/Tests/Other."""

    total: BucketStats = field(default_factory=BucketStats)
    code_churn: int = 0
    tests_churn: int = 0
    other_churn: int = 0

    def add_file(self: PackageStats, change: FileChange) -> None:
        """Accumulate a single file change into this package's totals."""
        self.total.add_file(change)
        if change.group == "Code":
            self.code_churn += change.churn
        elif change.group == "Tests":
            self.tests_churn += change.churn
        else:
            self.other_churn += change.churn


@dataclass
class SummaryReport:
    """Complete computed diff report ready for text, Markdown, or JSON rendering."""

    branch: str
    base_ref: str
    base_sha: str
    compare_sha: str
    head_sha: str
    two_dot: bool
    commit_count: int
    include_worktree: bool
    include_untracked: bool
    dirty_tracked_count: int
    untracked_count: int
    notes: list[str]
    files: list[FileChange]
    totals: BucketStats
    groups: dict[str, BucketStats]
    subcategories: dict[str, dict[str, BucketStats]]
    packages: dict[str, PackageStats]
    core_code_churn: int
    scripts_churn: int
    noise_files: int
    noise_churn: int


class Styler:
    """Optional ANSI terminal styling helper."""

    def __init__(self: Styler, enabled: bool) -> None:
        self.enabled = enabled

    def _wrap(self: Styler, text: str, code: str) -> str:
        """Wrap text in an ANSI escape code when styling is active."""
        if not self.enabled:
            return text
        return f"\x1b[{code}m{text}\x1b[0m"

    def bold(self: Styler, text: str) -> str:
        """Format bold text."""
        return self._wrap(text, "1")

    def dim(self: Styler, text: str) -> str:
        """Format dim text."""
        return self._wrap(text, "2")

    def green(self: Styler, text: str) -> str:
        """Format green text for additions."""
        return self._wrap(text, "32")

    def red(self: Styler, text: str) -> str:
        """Format red text for deletions."""
        return self._wrap(text, "31")

    def cyan(self: Styler, text: str) -> str:
        """Format cyan accent text."""
        return self._wrap(text, "36")

    def yellow(self: Styler, text: str) -> str:
        """Format yellow notice text."""
        return self._wrap(text, "33")


def resolve_git_executable() -> str:
    """Locate the git executable on PATH."""
    git_exe = shutil.which("git")
    if git_exe is None:
        raise DiffSummaryError("git executable was not found on PATH")
    return git_exe


def run_git_bytes(
    repo_root: Path, *args: str, check: bool = True
) -> subprocess.CompletedProcess[bytes]:
    """Execute a read-only git command returning raw stdout/stderr bytes."""
    git_exe = resolve_git_executable()
    result = subprocess.run(
        [git_exe, *args],
        cwd=repo_root,
        check=False,
        capture_output=True,
    )
    if check and result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise DiffSummaryError(stderr or f"git {' '.join(args)} failed")
    return result


def run_git_text(repo_root: Path, *args: str, check: bool = True) -> str:
    """Execute a read-only git command returning stripped UTF-8 stdout."""
    result = run_git_bytes(repo_root, *args, check=check)
    if result.returncode != 0:
        return ""
    return result.stdout.decode("utf-8", errors="replace").strip()


def resolve_repo_root(explicit_repo: str | None) -> Path:
    """Resolve the active Git working tree root."""
    candidate = Path(explicit_repo).resolve() if explicit_repo else Path.cwd()
    if candidate.is_dir():
        top = run_git_text(candidate, "rev-parse", "--show-toplevel", check=False)
        if top:
            return Path(top).resolve()

    fallback = Path(__file__).resolve().parents[1]
    top = run_git_text(fallback, "rev-parse", "--show-toplevel", check=False)
    if top:
        return Path(top).resolve()
    raise DiffSummaryError(f"not inside a Git repository: {candidate}")


def verify_commit(repo_root: Path, ref: str) -> str | None:
    """Resolve a Git ref to a commit SHA, or return None when absent."""
    result = run_git_bytes(
        repo_root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", check=False
    )
    if result.returncode != 0:
        return None
    return result.stdout.decode("utf-8", errors="replace").strip()


def resolve_base_ref(
    repo_root: Path, requested_base: str, base_was_explicit: bool
) -> tuple[str, str, list[str]]:
    """Resolve the comparison base reference and record any divergence notes."""
    notes: list[str] = []
    if base_was_explicit or requested_base != "main":
        sha = verify_commit(repo_root, requested_base)
        if sha is None:
            raise DiffSummaryError(f"could not resolve base ref {requested_base!r}")
        return requested_base, sha, notes

    local_main = verify_commit(repo_root, "main")
    origin_main = verify_commit(repo_root, "origin/main")
    if local_main is not None:
        if origin_main is not None and origin_main != local_main:
            notes.append(
                f"local 'main' ({local_main[:8]}) differs from 'origin/main' ({origin_main[:8]})"
            )
        return "main", local_main, notes

    if origin_main is not None:
        notes.append("local 'main' ref not found; fell back to 'origin/main'")
        return "origin/main", origin_main, notes

    raise DiffSummaryError("could not resolve base ref 'main' or 'origin/main'")


def classify_package(path: str) -> str:
    """Map a repository-relative path to its Howler package or area."""
    prefix_map: tuple[tuple[str, str], ...] = (
        ("api/", "api"),
        ("ui/", "ui"),
        ("client/", "client"),
        ("mcp/", "mcp"),
        ("plugins/evidence/", "evidence"),
        ("plugins/sentinel/", "sentinel"),
        ("plugins/sync/", "sync"),
        ("howler-helm/", "helm/infra"),
        ("helm/", "helm/infra"),
        ("ansible/", "helm/infra"),
        ("demo/", "helm/infra"),
        ("docs/", "docs"),
        ("documentation/", "docs"),
    )
    for prefix, package in prefix_map:
        if path.startswith(prefix):
            return package
    return "root"


def _is_lockfile(name: str) -> bool:
    """Check whether a filename is a dependency lockfile."""
    return name in LOCKFILE_NAMES or (
        name.startswith("requirements") and name.endswith(".txt")
    )


def _classify_agent_or_doc(
    path: str, parts: tuple[str, ...], name: str, suffix: str
) -> tuple[str, str] | None:
    """Classify agent/skill guides and repository documentation."""
    if (parts[0] in {".agents", "skills"}) and "scripts" in parts[1:]:
        if suffix in SCRIPT_EXTENSIONS:
            return ("Code", "Scripts & Hooks")
    if name in {"AGENTS.md", "CLAUDE.md"} or path.startswith(".github/agents/"):
        return ("Non-Code", "Agent & Skill Guides")
    if parts[0] in {".agents", "skills"}:
        return ("Non-Code", "Agent & Skill Guides")

    upper = name.upper()
    is_named_doc = (
        upper.startswith(("README", "CHANGELOG", "CONTRIBUTING", "LICENSE"))
        or path == "demo/overview.md"
    )
    if is_named_doc:
        return ("Non-Code", "Docs & Changelogs")
    if parts[0] in {"docs", "documentation"} and not name.startswith("."):
        if name != "mkdocs.yml":
            return ("Non-Code", "Docs & Changelogs")
    return None


def _classify_test(
    path: str, parts: tuple[str, ...], name: str
) -> tuple[str, str] | None:
    """Classify unit tests, integration/network tests, and test fixtures."""
    if "/test/integration/" in f"/{path}" or "/tests/integration/" in f"/{path}":
        return ("Tests", "Integration & Network")
    if path == "mcp/test/test_network.py" or name.endswith(
        (
            ".integration.test.ts",
            ".integration.test.tsx",
            ".e2e.test.ts",
            ".e2e.test.tsx",
        )
    ):
        return ("Tests", "Integration & Network")

    if "/test/unit/" in f"/{path}" or "/tests/unit/" in f"/{path}":
        return ("Tests", "Unit")
    if path.startswith("ui/") and name.endswith(UI_TEST_SUFFIXES):
        return ("Tests", "Unit")
    if path in {
        "plugins/evidence/dummy.py",
        "plugins/sentinel/dummy.py",
        "plugins/sync/dummy.py",
        "ui/src/setupTests.ts",
    } or path.startswith("ui/src/tests/"):
        return ("Tests", "Fixtures & Test Infra")

    in_test_dir = "test" in parts[:-1] or "tests" in parts[:-1]
    if not in_test_dir:
        return None
    is_py_or_yaml_test = (
        (name.startswith("test_") or name.endswith("_test.py")) and name.endswith(".py")
    ) or name.endswith(("_test.yaml", "_test.yml"))
    if is_py_or_yaml_test:
        return ("Tests", "Unit")
    return ("Tests", "Fixtures & Test Infra")


def _classify_asset(path: str, name: str, suffix: str) -> tuple[str, str] | None:
    """Classify localization files, static assets, and sample data blobs."""
    if path.startswith("ui/src/locales/"):
        return ("Non-Code", "Translations & Static Assets")
    if path.startswith("ui/public/"):
        if path in {"ui/public/manifest.json", "ui/public/serve.json"}:
            return ("Configs", "App & Schema Configs")
        if path.startswith("ui/public/scripts/"):
            return ("Code", "UI")
        return ("Non-Code", "Translations & Static Assets")
    if path in {
        "ui/src/utils/hit.json",
        "mcp/diag_auth_check.json",
        "api/howler/odm/charter.txt",
    }:
        return ("Non-Code", "Translations & Static Assets")
    if suffix in ASSET_EXTENSIONS and not path.startswith(("howler-helm/", "helm/")):
        return ("Non-Code", "Translations & Static Assets")
    return None


def _classify_config(
    path: str, parts: tuple[str, ...], name: str
) -> tuple[str, str] | None:
    """Classify CI, deployment/infrastructure, app schema, and tooling configs."""
    if parts[0] == ".github":
        return ("Configs", "CI & GitHub")
    if parts[0] in {"howler-helm", "helm", "ansible"} or path.startswith("api/dev/"):
        return ("Configs", "Deploy, Infra & Containers")
    if name in {
        "Dockerfile",
        ".dockerignore",
        ".helmignore",
        "nginx.conf",
    } or name.startswith(("Dockerfile.", "docker-compose")):
        return ("Configs", "Deploy, Infra & Containers")
    if (
        path
        in {
            "api/build_scripts/classification.yml",
            "api/build_scripts/mappings.yml",
            "documentation/mkdocs.yml",
        }
        or (path.startswith("plugins/") and name == "manifest.yml")
        or name == ".env"
        or name.startswith(".env.")
    ):
        return ("Configs", "App & Schema Configs")
    if (
        parts[0] in {".vscode", ".opencode"}
        or name in TOOLING_CONFIG_NAMES
        or name.startswith(
            (
                "tsconfig.",
                "vite.config.",
                "vitest.config.",
                ".eslintrc",
                ".prettierrc",
                ".coveragerc",
            )
        )
        or name.endswith("ignore")
    ):
        return ("Configs", "Package & Tooling")
    return None


def _classify_code(
    path: str, parts: tuple[str, ...], suffix: str
) -> tuple[str, str] | None:
    """Classify application/package code and helper/build scripts."""
    is_helper_script = (
        parts[0] in {"scripts", "hooks"}
        or "build_scripts" in parts[:-1]
        or path.startswith(("ui/scripts/", "mcp/dev/", "demo/scripts/"))
    )
    if is_helper_script:
        return ("Code", "Scripts & Hooks")

    component_prefixes: tuple[tuple[str, str], ...] = (
        ("api/howler/", "API"),
        ("ui/src/", "UI"),
        ("client/howler_client/", "Client"),
        ("client/examples/", "Client"),
        ("mcp/howler_mcp/", "MCP"),
        ("plugins/evidence/evidence/", "Plugin: Evidence"),
        ("plugins/sentinel/sentinel/", "Plugin: Sentinel"),
        ("plugins/sync/sync/", "Plugin: Sync"),
    )
    for prefix, subcat in component_prefixes:
        if path.startswith(prefix):
            return ("Code", subcat)
    if path == "ui/index.html":
        return ("Code", "UI")
    if suffix in {".sh", ".bash", ".zsh"}:
        return ("Code", "Scripts & Hooks")
    return None


def classify_file(path: str) -> tuple[str, str]:
    """Classify a repository-relative path into (group, subcategory)."""
    pure = Path(path)
    parts = pure.parts
    name = pure.name
    suffix = pure.suffix.lower()

    if _is_lockfile(name):
        return ("Non-Code", "Lockfiles")
    if path.startswith("ui/src/models/entities/generated/"):
        return ("Non-Code", "Generated Code")

    for classifier in (
        lambda: _classify_agent_or_doc(path, parts, name, suffix),
        lambda: _classify_test(path, parts, name),
        lambda: _classify_asset(path, name, suffix),
        lambda: _classify_config(path, parts, name),
        lambda: _classify_code(path, parts, suffix),
    ):
        matched = classifier()
        if matched is not None:
            return matched

    if suffix in CODE_EXTENSIONS:
        return ("Code", "Other")
    if suffix in CONFIG_EXTENSIONS:
        return ("Configs", "Package & Tooling")
    if suffix in DOC_EXTENSIONS:
        return ("Non-Code", "Docs & Changelogs")
    return ("Non-Code", "Translations & Static Assets")


def parse_numstat_z(raw_output: bytes) -> dict[str, FileChange]:
    """Parse `git diff -M --numstat -z` output into FileChange entries."""
    changes: dict[str, FileChange] = {}
    tokens = raw_output.decode("utf-8", errors="surrogateescape").split("\0")
    index = 0
    total_tokens = len(tokens)

    while index < total_tokens:
        token = tokens[index]
        if not token:
            index += 1
            continue

        added_str, deleted_str, inline_path = token.split("\t", 2)
        if inline_path == "" and index + 2 < total_tokens:
            renamed_from: str | None = tokens[index + 1]
            path = tokens[index + 2]
            index += 3
        else:
            renamed_from = None
            path = inline_path
            index += 1

        is_binary = added_str == "-" or deleted_str == "-"
        added = 0 if is_binary else int(added_str)
        deleted = 0 if is_binary else int(deleted_str)
        group, subcategory = classify_file(path)
        changes[path] = FileChange(
            path=path,
            group=group,
            subcategory=subcategory,
            package=classify_package(path),
            added=added,
            deleted=deleted,
            is_binary=is_binary,
            renamed_from=renamed_from,
        )

    return changes


def inspect_untracked_file(full_path: Path) -> tuple[int, bool]:
    """Count added lines and binary status for an untracked working-tree file."""
    if full_path.is_symlink():
        return (1, False)
    if not full_path.is_file():
        return (0, False)

    data = full_path.read_bytes()
    if not data:
        return (0, False)
    if b"\x00" in data[:8000]:
        return (0, True)

    lines = data.count(b"\n")
    if not data.endswith(b"\n"):
        lines += 1
    return (lines, False)


def add_untracked_changes(repo_root: Path, changes: dict[str, FileChange]) -> list[str]:
    """Collect untracked non-ignored files and merge them into `changes`."""
    raw = run_git_bytes(
        repo_root, "ls-files", "--others", "--exclude-standard", "-z"
    ).stdout
    untracked_paths = [
        entry
        for entry in raw.decode("utf-8", errors="surrogateescape").split("\0")
        if entry
    ]
    for rel_path in untracked_paths:
        added, is_binary = inspect_untracked_file(repo_root / rel_path)
        existing = changes.get(rel_path)
        if existing is not None:
            existing.added += added
            existing.is_binary = existing.is_binary or is_binary
            existing.is_untracked = True
            continue

        group, subcategory = classify_file(rel_path)
        changes[rel_path] = FileChange(
            path=rel_path,
            group=group,
            subcategory=subcategory,
            package=classify_package(rel_path),
            added=added,
            deleted=0,
            is_binary=is_binary,
            is_untracked=True,
        )
    return untracked_paths


def count_worktree_status(repo_root: Path) -> tuple[int, int]:
    """Return counts of (dirty_tracked_files, untracked_files) from git status."""
    raw = run_git_bytes(repo_root, "status", "--porcelain=v1", "-z").stdout
    tokens = raw.decode("utf-8", errors="surrogateescape").split("\0")
    dirty_tracked = 0
    untracked = 0
    index = 0
    while index < len(tokens):
        entry = tokens[index]
        if not entry:
            index += 1
            continue
        status = entry[:2]
        if status == "??":
            untracked += 1
            index += 1
        elif "R" in status or "C" in status:
            dirty_tracked += 1
            index += 2
        else:
            dirty_tracked += 1
            index += 1
    return dirty_tracked, untracked


def aggregate_report(
    *,
    branch: str,
    base_ref: str,
    base_sha: str,
    compare_sha: str,
    head_sha: str,
    two_dot: bool,
    commit_count: int,
    include_worktree: bool,
    include_untracked: bool,
    dirty_tracked_count: int,
    untracked_count: int,
    notes: list[str],
    changes: dict[str, FileChange],
) -> SummaryReport:
    """Aggregate individual FileChange records into group and package buckets."""
    totals = BucketStats()
    groups = {group: BucketStats() for group in GROUPS_ORDER}
    subcategories = {
        group: {sub: BucketStats() for sub in SUBCATEGORIES_ORDER[group]}
        for group in GROUPS_ORDER
    }
    packages = {pkg: PackageStats() for pkg in PACKAGES_ORDER}

    sorted_files = sorted(changes.values(), key=lambda item: item.path)
    for change in sorted_files:
        totals.add_file(change)
        groups[change.group].add_file(change)
        subcategories[change.group][change.subcategory].add_file(change)
        packages[change.package].add_file(change)

    scripts_churn = subcategories["Code"]["Scripts & Hooks"].churn
    core_code_churn = groups["Code"].churn - scripts_churn
    lockfiles_stats = subcategories["Non-Code"]["Lockfiles"]
    generated_stats = subcategories["Non-Code"]["Generated Code"]
    noise_files = lockfiles_stats.files + generated_stats.files
    noise_churn = lockfiles_stats.churn + generated_stats.churn

    return SummaryReport(
        branch=branch,
        base_ref=base_ref,
        base_sha=base_sha,
        compare_sha=compare_sha,
        head_sha=head_sha,
        two_dot=two_dot,
        commit_count=commit_count,
        include_worktree=include_worktree,
        include_untracked=include_untracked,
        dirty_tracked_count=dirty_tracked_count,
        untracked_count=untracked_count,
        notes=notes,
        files=sorted_files,
        totals=totals,
        groups=groups,
        subcategories=subcategories,
        packages=packages,
        core_code_churn=core_code_churn,
        scripts_churn=scripts_churn,
        noise_files=noise_files,
        noise_churn=noise_churn,
    )


def build_report(args: argparse.Namespace) -> SummaryReport:
    """Collect Git state and diff statistics and assemble the SummaryReport."""
    repo_root = resolve_repo_root(args.repo)
    head_sha = verify_commit(repo_root, "HEAD")
    if head_sha is None:
        raise DiffSummaryError("repository does not have a valid HEAD commit")

    branch = (
        run_git_text(
            repo_root, "symbolic-ref", "--quiet", "--short", "HEAD", check=False
        )
        or "HEAD (detached)"
    )
    base_ref, base_sha, notes = resolve_base_ref(
        repo_root, args.base, args.base_explicit
    )

    if args.two_dot:
        compare_sha = base_sha
    else:
        compare_sha = run_git_text(repo_root, "merge-base", base_sha, head_sha)

    commit_count_str = run_git_text(
        repo_root, "rev-list", "--count", f"{compare_sha}..{head_sha}"
    )
    commit_count = int(commit_count_str or "0")
    dirty_tracked, untracked_total = count_worktree_status(repo_root)

    diff_cmd = ["diff", "-M", "--numstat", "-z", compare_sha]
    if args.no_worktree:
        diff_cmd.append(head_sha)
    raw_diff = run_git_bytes(repo_root, *diff_cmd).stdout
    changes = parse_numstat_z(raw_diff)

    include_worktree = not args.no_worktree
    include_untracked = include_worktree and not args.no_untracked
    if include_untracked:
        add_untracked_changes(repo_root, changes)

    return aggregate_report(
        branch=branch,
        base_ref=base_ref,
        base_sha=base_sha,
        compare_sha=compare_sha,
        head_sha=head_sha,
        two_dot=args.two_dot,
        commit_count=commit_count,
        include_worktree=include_worktree,
        include_untracked=include_untracked,
        dirty_tracked_count=dirty_tracked,
        untracked_count=untracked_total,
        notes=notes,
        changes=changes,
    )


def visible_len(text: str) -> int:
    """Measure printable character width after stripping ANSI escape codes."""
    return len(ANSI_ESCAPE_RE.sub("", text))


def pad_cell(text: str, width: int, *, align_right: bool = False) -> str:
    """Pad a potentially ANSI-styled string to an exact visible column width."""
    padding = max(0, width - visible_len(text))
    if align_right:
        return (" " * padding) + text
    return text + (" " * padding)


def fmt_int(value: int) -> str:
    """Format an integer with thousands separators."""
    return f"{value:,}"


def fmt_signed(value: int) -> str:
    """Format a signed delta (`+N`, `-N`, or `0`)."""
    if value > 0:
        return f"+{value:,}"
    if value < 0:
        return f"{value:,}"
    return "0"


def fmt_pct(numerator: int, denominator: int) -> str:
    """Format a percentage string, returning 0.0% when denominator is zero."""
    if denominator <= 0:
        return "0.0%"
    return f"{(numerator / denominator) * 100.0:.1f}%"


def fmt_files_cell(stats: BucketStats) -> str:
    """Format file count, annotating binary file counts when present."""
    if stats.binary_files > 0:
        return f"{fmt_int(stats.files)} ({stats.binary_files} bin)"
    return fmt_int(stats.files)


def describe_scope(report: SummaryReport) -> str:
    """Describe whether uncommitted/untracked working-tree changes are included."""
    total_dirty = report.dirty_tracked_count + report.untracked_count
    if not report.include_worktree:
        if total_dirty == 0:
            return "HEAD only (working tree clean)"
        return (
            f"HEAD only ({report.dirty_tracked_count} uncommitted, "
            f"{report.untracked_count} untracked omitted)"
        )

    if total_dirty == 0:
        return "HEAD + working tree (clean)"
    parts = [f"{report.dirty_tracked_count} uncommitted"]
    if report.include_untracked:
        parts.append(f"{report.untracked_count} untracked")
    elif report.untracked_count > 0:
        parts.append(f"{report.untracked_count} untracked omitted")
    return f"HEAD + working tree (includes {', '.join(parts)})"


def describe_ratio(report: SummaryReport) -> str:
    """Format the headline Test : Core Code churn ratio."""
    tests_churn = report.groups["Tests"].churn
    core_churn = report.core_code_churn
    suffix = (
        f"; excludes {fmt_int(report.scripts_churn)} helper-script churn"
        if report.scripts_churn > 0
        else ""
    )
    if core_churn <= 0:
        return f"N/A ({fmt_int(tests_churn)} test / 0 core code churn{suffix})"
    ratio = tests_churn / core_churn
    return (
        f"{ratio:.2f}x ({fmt_int(tests_churn)} test / "
        f"{fmt_int(core_churn)} core code churn{suffix})"
    )


def describe_hand_authored(report: SummaryReport) -> str:
    """Summarize category shares excluding lockfiles and generated code."""
    effective_total = report.totals.churn - report.noise_churn
    if effective_total <= 0:
        return (
            f"0 hand-authored line churn "
            f"({fmt_int(report.noise_churn)} churn in {report.noise_files} lockfile/generated file(s))"
        )
    code_pct = fmt_pct(report.groups["Code"].churn, effective_total)
    test_pct = fmt_pct(report.groups["Tests"].churn, effective_total)
    cfg_pct = fmt_pct(report.groups["Configs"].churn, effective_total)
    non_code_eff = report.groups["Non-Code"].churn - report.noise_churn
    non_code_pct = fmt_pct(non_code_eff, effective_total)
    return (
        f"{fmt_int(effective_total)} churn -> "
        f"Code {code_pct} · Tests {test_pct} · Configs {cfg_pct} · Non-Code {non_code_pct} "
        f"(excludes {fmt_int(report.noise_churn)} lockfile/generated churn)"
    )


def _build_category_rows(
    report: SummaryReport, styler: Styler
) -> list[tuple[str, str, str, str, str, str, str]]:
    """Build formatted rows for the 4-group category breakdown table."""
    rows: list[tuple[str, str, str, str, str, str, str]] = []
    total_churn = report.totals.churn

    for group in GROUPS_ORDER:
        g_stats = report.groups[group]
        rows.append(
            (
                styler.bold(group),
                fmt_files_cell(g_stats),
                styler.green(f"+{fmt_int(g_stats.added)}"),
                styler.red(f"-{fmt_int(g_stats.deleted)}"),
                fmt_signed(g_stats.net),
                fmt_int(g_stats.churn),
                fmt_pct(g_stats.churn, total_churn),
            )
        )
        non_empty_subs = [
            sub
            for sub in SUBCATEGORIES_ORDER[group]
            if report.subcategories[group][sub].files > 0
        ]
        for idx, sub in enumerate(non_empty_subs):
            branch_glyph = "└─" if idx == len(non_empty_subs) - 1 else "├─"
            s_stats = report.subcategories[group][sub]
            rows.append(
                (
                    f"  {styler.dim(branch_glyph)} {sub}",
                    fmt_files_cell(s_stats),
                    styler.green(f"+{fmt_int(s_stats.added)}"),
                    styler.red(f"-{fmt_int(s_stats.deleted)}"),
                    fmt_signed(s_stats.net),
                    fmt_int(s_stats.churn),
                    fmt_pct(s_stats.churn, total_churn),
                )
            )
    return rows


def _render_aligned_table(
    headers: tuple[str, ...],
    rows: list[tuple[str, ...]],
    footer: tuple[str, ...] | None,
    right_aligned_cols: frozenset[int],
    styler: Styler,
) -> list[str]:
    """Render an aligned plain-text/ANSI table with header and optional footer."""
    all_rows = [headers, *rows] + ([footer] if footer is not None else [])
    widths = [
        max(visible_len(row[col]) for row in all_rows) for col in range(len(headers))
    ]

    def format_row(row: tuple[str, ...]) -> str:
        cells = [
            pad_cell(cell, widths[idx], align_right=(idx in right_aligned_cols))
            for idx, cell in enumerate(row)
        ]
        return "  ".join(cells)

    rule = styler.dim("─" * (sum(widths) + 2 * (len(widths) - 1)))
    lines = [styler.bold(format_row(headers)), rule]
    lines.extend(format_row(row) for row in rows)
    if footer is not None:
        lines.extend([rule, styler.bold(format_row(footer))])
    return lines


def _render_terminal_packages(report: SummaryReport, styler: Styler) -> list[str]:
    """Render the secondary By-Package / Area summary table."""
    rows: list[tuple[str, ...]] = []
    for pkg in PACKAGES_ORDER:
        p_stats = report.packages[pkg]
        if p_stats.total.files == 0:
            continue
        p_churn = p_stats.total.churn
        split = (
            f"Code {fmt_pct(p_stats.code_churn, p_churn)} · "
            f"Tests {fmt_pct(p_stats.tests_churn, p_churn)} · "
            f"Other {fmt_pct(p_stats.other_churn, p_churn)}"
        )
        rows.append(
            (
                pkg,
                fmt_files_cell(p_stats.total),
                styler.green(f"+{fmt_int(p_stats.total.added)}"),
                styler.red(f"-{fmt_int(p_stats.total.deleted)}"),
                fmt_int(p_churn),
                split,
            )
        )

    headers = (
        "Package / Area",
        "Files",
        "+Added",
        "-Deleted",
        "Churn",
        "Split (Code / Tests / Other)",
    )
    table = _render_aligned_table(headers, rows, None, frozenset({1, 2, 3, 4}), styler)
    return ["", *table]


def _format_file_entry(change: FileChange) -> str:
    """Format a single per-file summary line."""
    label = (
        f"{change.renamed_from} -> {change.path}"
        if change.renamed_from
        else change.path
    )
    tag = " [untracked]" if change.is_untracked else ""
    if change.is_binary:
        return f"    binary           {label}{tag}"
    stats = f"+{fmt_int(change.added)} / -{fmt_int(change.deleted)}"
    return f"    {stats:<16} {label}{tag}"


def _render_terminal_files(report: SummaryReport, styler: Styler) -> list[str]:
    """Render per-file listings grouped under their categories."""
    if not report.files:
        return []
    lines = ["", styler.bold("Changed Files")]
    for group in GROUPS_ORDER:
        for sub in SUBCATEGORIES_ORDER[group]:
            matching = [
                item
                for item in report.files
                if item.group == group and item.subcategory == sub
            ]
            if not matching:
                continue
            lines.append(f"  {styler.cyan(f'{group} -> {sub}')} ({len(matching)})")
            lines.extend(_format_file_entry(item) for item in matching)
    return lines


def render_terminal(
    report: SummaryReport, *, compact: bool, show_files: bool, use_color: bool
) -> str:
    """Render the report as an aligned terminal summary."""
    styler = Styler(use_color)
    range_sep = ".." if report.two_dot else "..."
    title = f"Howler Diff Summary — {report.branch} vs {report.base_ref}{range_sep}HEAD"
    commit_word = "commit" if report.commit_count == 1 else "commits"
    base_detail = (
        f"{report.base_ref} ({report.base_sha[:8]})"
        if report.two_dot
        else (
            f"{report.base_ref} ({report.base_sha[:8]}) · "
            f"Merge-base: {report.compare_sha[:8]}"
        )
    )

    lines = [
        styler.bold(styler.cyan(title)),
        (
            f"  Base:       {base_detail} · "
            f"HEAD: {report.head_sha[:8]} ({report.commit_count} {commit_word})"
        ),
        f"  Scope:      {describe_scope(report)}",
        (
            f"  Totals:     {fmt_files_cell(report.totals)} files · "
            f"{styler.green('+' + fmt_int(report.totals.added))}  "
            f"{styler.red('-' + fmt_int(report.totals.deleted))}  "
            f"(net {fmt_signed(report.totals.net)}, churn {fmt_int(report.totals.churn)})"
        ),
        f"  Test:Code:  {describe_ratio(report)}",
    ]
    if report.noise_files > 0:
        lines.append(f"  Effective:  {describe_hand_authored(report)}")
    for note in report.notes:
        lines.append(f"  {styler.yellow('Note:')}       {note}")

    if report.totals.files == 0:
        lines.extend(["", "No changes detected relative to comparison base."])
        return "\n".join(lines) + "\n"

    cat_headers = (
        "Category",
        "Files",
        "+Added",
        "-Deleted",
        "Net",
        "Churn",
        "% Churn",
    )
    cat_rows = _build_category_rows(report, styler)
    cat_footer = (
        "Total",
        fmt_files_cell(report.totals),
        styler.green(f"+{fmt_int(report.totals.added)}"),
        styler.red(f"-{fmt_int(report.totals.deleted)}"),
        fmt_signed(report.totals.net),
        fmt_int(report.totals.churn),
        "100.0%" if report.totals.churn > 0 else "0.0%",
    )
    lines.extend(
        [
            "",
            *_render_aligned_table(
                cat_headers, cat_rows, cat_footer, frozenset({1, 2, 3, 4, 5, 6}), styler
            ),
        ]
    )
    if not compact:
        lines.extend(_render_terminal_packages(report, styler))
    if show_files:
        lines.extend(_render_terminal_files(report, styler))
    return "\n".join(lines) + "\n"


def _render_markdown_categories(report: SummaryReport) -> list[str]:
    """Render the 4-group category breakdown as a Markdown table."""
    total_churn = report.totals.churn
    lines = [
        "| Category | Files | +Added | -Deleted | Net | Churn | % Churn |",
        "| :--- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for group in GROUPS_ORDER:
        g_stats = report.groups[group]
        lines.append(
            f"| **{group}** | {fmt_files_cell(g_stats)} | +{fmt_int(g_stats.added)} | "
            f"-{fmt_int(g_stats.deleted)} | {fmt_signed(g_stats.net)} | "
            f"{fmt_int(g_stats.churn)} | {fmt_pct(g_stats.churn, total_churn)} |"
        )
        for sub in SUBCATEGORIES_ORDER[group]:
            s_stats = report.subcategories[group][sub]
            if s_stats.files == 0:
                continue
            lines.append(
                f"| &nbsp;&nbsp;↳ {sub} | {fmt_files_cell(s_stats)} | "
                f"+{fmt_int(s_stats.added)} | -{fmt_int(s_stats.deleted)} | "
                f"{fmt_signed(s_stats.net)} | {fmt_int(s_stats.churn)} | "
                f"{fmt_pct(s_stats.churn, total_churn)} |"
            )
    pct_total = "100.0%" if total_churn > 0 else "0.0%"
    lines.append(
        f"| **Total** | **{fmt_files_cell(report.totals)}** | "
        f"**+{fmt_int(report.totals.added)}** | **-{fmt_int(report.totals.deleted)}** | "
        f"**{fmt_signed(report.totals.net)}** | **{fmt_int(total_churn)}** | "
        f"**{pct_total}** |"
    )
    return lines


def _render_markdown_packages(report: SummaryReport) -> list[str]:
    """Render the By-Package / Area breakdown as a Markdown table."""
    lines = [
        "",
        "### By Package / Area",
        "",
        "| Package / Area | Files | +Added | -Deleted | Churn | Split (Code / Tests / Other) |",
        "| :--- | ---: | ---: | ---: | ---: | :--- |",
    ]
    for pkg in PACKAGES_ORDER:
        p_stats = report.packages[pkg]
        if p_stats.total.files == 0:
            continue
        p_churn = p_stats.total.churn
        split = (
            f"Code {fmt_pct(p_stats.code_churn, p_churn)} · "
            f"Tests {fmt_pct(p_stats.tests_churn, p_churn)} · "
            f"Other {fmt_pct(p_stats.other_churn, p_churn)}"
        )
        lines.append(
            f"| `{pkg}` | {fmt_files_cell(p_stats.total)} | "
            f"+{fmt_int(p_stats.total.added)} | -{fmt_int(p_stats.total.deleted)} | "
            f"{fmt_int(p_churn)} | {split} |"
        )
    return lines


def render_markdown(report: SummaryReport, *, compact: bool, show_files: bool) -> str:
    """Render the report as GitHub-Flavored Markdown."""
    range_sep = ".." if report.two_dot else "..."
    lines = [
        f"## Howler Diff Summary (`{report.branch}` vs `{report.base_ref}{range_sep}HEAD`)",
        "",
        (
            f"- **Base**: `{report.base_ref}` (`{report.base_sha[:8]}`) · "
            f"**Comparison commit**: `{report.compare_sha[:8]}` · "
            f"**HEAD**: `{report.head_sha[:8]}` ({report.commit_count} commit(s))"
        ),
        f"- **Scope**: {describe_scope(report)}",
        (
            f"- **Totals**: {fmt_files_cell(report.totals)} files · "
            f"`+{fmt_int(report.totals.added)}` / `-{fmt_int(report.totals.deleted)}` "
            f"(net `{fmt_signed(report.totals.net)}`, churn `{fmt_int(report.totals.churn)}`)"
        ),
        f"- **Test : Core Code**: {describe_ratio(report)}",
    ]
    if report.noise_files > 0:
        lines.append(
            f"- **Effective (hand-authored)**: {describe_hand_authored(report)}"
        )
    for note in report.notes:
        lines.append(f"- **Note**: {note}")

    if report.totals.files == 0:
        lines.extend(["", "_No changes detected relative to comparison base._"])
        return "\n".join(lines) + "\n"

    lines.extend(["", *_render_markdown_categories(report)])
    if not compact:
        lines.extend(_render_markdown_packages(report))
    if show_files and report.files:
        lines.extend(["", "### Changed Files", ""])
        for item in report.files:
            label = (
                f"{item.renamed_from} -> {item.path}"
                if item.renamed_from
                else item.path
            )
            stat = "binary" if item.is_binary else f"+{item.added} / -{item.deleted}"
            lines.append(f"- `{label}` ({item.group} → {item.subcategory}: `{stat}`)")
    return "\n".join(lines) + "\n"


def _bucket_to_dict(stats: BucketStats, total_churn: int) -> dict[str, object]:
    """Serialize a BucketStats instance for JSON output."""
    pct = round((stats.churn / total_churn) * 100.0, 2) if total_churn > 0 else 0.0
    return {
        "files": stats.files,
        "binary_files": stats.binary_files,
        "added": stats.added,
        "deleted": stats.deleted,
        "net": stats.net,
        "churn": stats.churn,
        "pct_churn": pct,
    }


def render_json(report: SummaryReport, *, compact: bool, show_files: bool) -> str:
    """Render the report as structured JSON."""
    total_churn = report.totals.churn
    effective_churn = total_churn - report.noise_churn
    tests_churn = report.groups["Tests"].churn
    ratio: float | None = (
        round(tests_churn / report.core_code_churn, 4)
        if report.core_code_churn > 0
        else None
    )

    groups_payload: dict[str, object] = {}
    for group in GROUPS_ORDER:
        subs_payload = {
            sub: _bucket_to_dict(report.subcategories[group][sub], total_churn)
            for sub in SUBCATEGORIES_ORDER[group]
            if report.subcategories[group][sub].files > 0
        }
        groups_payload[group] = {
            **_bucket_to_dict(report.groups[group], total_churn),
            "subcategories": subs_payload,
        }

    payload: dict[str, object] = {
        "branch": report.branch,
        "base_ref": report.base_ref,
        "base_sha": report.base_sha,
        "compare_sha": report.compare_sha,
        "head_sha": report.head_sha,
        "mode": "two-dot" if report.two_dot else "merge-base",
        "commit_count": report.commit_count,
        "include_worktree": report.include_worktree,
        "include_untracked": report.include_untracked,
        "dirty_tracked_files": report.dirty_tracked_count,
        "untracked_files": report.untracked_count,
        "notes": report.notes,
        "totals": {
            **_bucket_to_dict(report.totals, total_churn),
            "core_code_churn": report.core_code_churn,
            "scripts_and_hooks_churn": report.scripts_churn,
            "test_to_core_code_ratio": ratio,
            "lockfile_and_generated_files": report.noise_files,
            "lockfile_and_generated_churn": report.noise_churn,
            "hand_authored_churn": effective_churn,
        },
        "groups": groups_payload,
    }
    if not compact:
        payload["packages"] = {
            pkg: {
                **_bucket_to_dict(report.packages[pkg].total, total_churn),
                "code_churn": report.packages[pkg].code_churn,
                "tests_churn": report.packages[pkg].tests_churn,
                "other_churn": report.packages[pkg].other_churn,
            }
            for pkg in PACKAGES_ORDER
            if report.packages[pkg].total.files > 0
        }
    if show_files:
        payload["files"] = [
            {
                "path": item.path,
                "renamed_from": item.renamed_from,
                "group": item.group,
                "subcategory": item.subcategory,
                "package": item.package,
                "added": item.added,
                "deleted": item.deleted,
                "net": item.net,
                "churn": item.churn,
                "is_binary": item.is_binary,
                "is_untracked": item.is_untracked,
            }
            for item in report.files
        ]
    return json.dumps(payload, indent=2) + "\n"


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line options for `diff_summary.py`."""
    parser = argparse.ArgumentParser(
        description=(
            "Summarize changes on the current HEAD/working tree compared to main, "
            "broken down into Code, Tests, Configs, and Non-Code."
        )
    )
    parser.add_argument(
        "--base",
        default=None,
        metavar="REF",
        help="Base Git ref to compare against (default: main, falling back to origin/main).",
    )
    parser.add_argument(
        "--two-dot",
        action="store_true",
        help="Compare directly against base tip (<base>..HEAD) instead of merge-base.",
    )
    parser.add_argument(
        "--no-worktree",
        action="store_true",
        help="Exclude uncommitted staged, unstaged, and untracked working-tree changes.",
    )
    parser.add_argument(
        "--no-untracked",
        action="store_true",
        help="Exclude untracked files when working-tree changes are included.",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Omit the secondary By-Package / Area breakdown table.",
    )
    parser.add_argument(
        "-v",
        "--files",
        action="store_true",
        help="List individual changed files grouped under their categories.",
    )
    parser.add_argument(
        "--repo",
        default=None,
        metavar="PATH",
        help="Target Git repository or worktree path (default: current directory).",
    )
    parser.add_argument(
        "--color",
        choices=("auto", "always", "never"),
        default="auto",
        help="Control ANSI color in terminal output (default: auto).",
    )
    parser.add_argument(
        "--never-fail",
        action="store_true",
        help="Print a notice and exit 0 if Git state/base resolution fails.",
    )

    fmt_group = parser.add_mutually_exclusive_group()
    fmt_group.add_argument(
        "--markdown",
        action="store_true",
        help="Render output as GitHub-Flavored Markdown.",
    )
    fmt_group.add_argument(
        "--json",
        action="store_true",
        help="Render output as JSON.",
    )

    parsed = parser.parse_args(argv)
    parsed.base_explicit = parsed.base is not None
    if parsed.base is None:
        parsed.base = "main"
    return parsed


def should_use_color(mode: str) -> bool:
    """Determine whether terminal output should include ANSI color sequences."""
    if mode == "always":
        return True
    if mode == "never":
        return False
    return (
        sys.stdout.isatty()
        and os.environ.get("NO_COLOR") is None
        and os.environ.get("TERM") != "dumb"
    )


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for generating and printing the branch diff summary."""
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        report = build_report(args)
    except (DiffSummaryError, OSError, ValueError) as error:
        if args.never_fail:
            sys.stdout.write(f"Howler Diff Summary skipped: {error}\n")
            return 0
        sys.stderr.write(f"diff_summary.py: error: {error}\n")
        return 1

    if args.json:
        output = render_json(report, compact=args.compact, show_files=args.files)
    elif args.markdown:
        output = render_markdown(report, compact=args.compact, show_files=args.files)
    else:
        output = render_terminal(
            report,
            compact=args.compact,
            show_files=args.files,
            use_color=should_use_color(args.color),
        )
    sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
