"""Generate consistent coverage reports for Howler's Python packages."""

from __future__ import annotations

import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path


def get_color(percentage: int) -> str:
    """Return the badge color for a coverage percentage."""
    if percentage < 50:
        return "red"
    if percentage < 70:
        return "yellow"
    return "green"


def generate_badge(title: str, percentage: str, color: str) -> str:
    """Build a shields.io badge for a coverage metric."""
    return (
        f"![Static Badge](https://img.shields.io/badge/{title.replace(' ', '_')}-{percentage}25-{color}?style="
        "flat&logo=azuredevops&logoColor=%230078D7)"
    )


def format_coverage_markdown(
    project_title: str,
    total_percentage: str,
    total_color: str,
    diff_badge: str,
    diff_markdown: str,
    report_result: str,
) -> str:
    """Render badges, diff details, and the full report as valid Markdown."""
    badges = [generate_badge("Total Coverage", total_percentage, total_color)]
    if diff_badge:
        badges.append(diff_badge)

    markdown_lines = [
        f"![Static Badge](https://img.shields.io/badge/Build%20(Python%20{platform.python_version()})-passing-brightgreen)",
        "",
        f"# {project_title} - Coverage Results",
        " ".join(badges),
    ]

    if diff_markdown.strip():
        markdown_lines.extend(["", diff_markdown.strip()])

    markdown_lines.extend(
        [
            "",
            "## Full Coverage Report",
            "<details>",
            "<summary>Expand</summary>",
            "",
            "```text",
            report_result.rstrip(),
            "```",
            "",
            "</details>",
        ]
    )
    return "\n".join(markdown_lines)


def generate_coverage_report(project_title: str, package_root: Path) -> None:
    """Run coverage tools and write a report in the package directory."""
    try:
        coverage_executable = _resolve_executable("coverage")
        report_result = subprocess.check_output(
            [coverage_executable, "report", "--data-file=.coverage"], cwd=package_root
        ).decode()
        subprocess.check_output(
            [coverage_executable, "xml", "--data-file=.coverage"], cwd=package_root
        )
        subprocess.check_output(
            [coverage_executable, "html", "--data-file=.coverage"], cwd=package_root
        )
        sys.stdout.write(report_result + "\n")

        diff_markdown = ""
        diff_percentage = "NA%"
        diff_color = "red"
        diff_badge = generate_badge("Diff Coverage", diff_percentage, diff_color)
        diff_file = package_root / "diff.txt"
        if diff_file.is_file():
            diff_report_result = subprocess.check_output(
                [
                    _resolve_executable("diff-cover"),
                    "coverage.xml",
                    "--diff-file",
                    "diff.txt",
                    "--markdown-report",
                    "diff-cover-report.md",
                ],
                cwd=package_root,
            ).decode()
            sys.stdout.write(diff_report_result + "\n")

            coverage_line = next(
                (
                    line
                    for line in diff_report_result.splitlines()
                    if "Coverage:" in line
                ),
                None,
            )
            if coverage_line:
                diff_percentage = coverage_line.split()[-1]
                try:
                    diff_color = get_color(int(diff_percentage.rstrip("%")))
                except ValueError:
                    diff_color = "red"
            diff_badge = generate_badge("Diff Coverage", diff_percentage, diff_color)

            report_path = package_root / "diff-cover-report.md"
            if report_path.is_file():
                diff_markdown = report_path.read_text(encoding="utf-8").replace(
                    "# ", "## "
                )
                diff_markdown = diff_markdown.replace("__init__.py", r"\_\_init\_\_.py")
                diff_markdown = re.sub(
                    r"### (.+py)", r"<details>\n<summary>\1</summary>\n", diff_markdown
                )
                diff_markdown = re.sub(
                    r"\n---(\n+<details>)", r"\n</details>\1", diff_markdown
                )
                diff_markdown += "\n</details>"

        total_percentage = report_result.splitlines()[-1].split()[-1]
        total_color = get_color(int(total_percentage.rstrip("%")))
        markdown_output = format_coverage_markdown(
            project_title,
            total_percentage,
            total_color,
            diff_badge,
            diff_markdown,
            report_result,
        )

        sys.stdout.write("Markdown result:\n")
        sys.stdout.write(markdown_output + "\n")
        output_path = package_root / "coverage-results.md"
        sys.stdout.write(f"Writing to: {output_path}\n")
        output_path.write_text(markdown_output, encoding="utf-8")
    except subprocess.CalledProcessError as error:
        command = (
            error.cmd if isinstance(error.cmd, str) else " ".join(map(str, error.cmd))
        )
        sys.stderr.write(f"{command} failed.\n")
        if error.output:
            if isinstance(error.output, bytes):
                sys.stderr.write(error.output.decode(errors="replace"))
            else:
                sys.stderr.write(str(error.output))
        sys.exit(error.returncode)


def _resolve_executable(name: str) -> str:
    """Resolve a required CLI tool to its absolute path."""
    executable = shutil.which(name)
    if executable is None:
        raise FileNotFoundError(f"Required executable '{name}' was not found on PATH")
    return executable
