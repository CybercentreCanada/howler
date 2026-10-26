"""Tests for the shared coverage report renderer."""

from __future__ import annotations

import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from howler_coverage_report import (  # noqa: E402
    format_coverage_markdown,
    generate_coverage_report,
    get_color,
)


class TestCoverageReport(unittest.TestCase):
    """Coverage Markdown formatting tests."""

    def test_diff_markdown_is_not_indented_as_code(self: TestCoverageReport) -> None:
        """Keep injected diff Markdown at the document's normal indentation."""
        diff_markdown = (
            "## Diff Coverage\n\nNo lines with coverage information in this diff."
        )
        report_result = "Name Stmts Miss Branch BrPart Cover\nTOTAL 149 7 40 4 94%"

        markdown = format_coverage_markdown(
            "Howler Sync Plugin",
            "94%",
            "green",
            "![Diff Coverage](badge)",
            diff_markdown,
            report_result,
        )

        self.assertIn("\n# Howler Sync Plugin - Coverage Results\n", markdown)
        self.assertIn(
            "\n## Diff Coverage\n\nNo lines with coverage information in this diff.",
            markdown,
        )
        self.assertNotIn("            # Howler Sync Plugin", markdown)
        self.assertIn("<summary>Expand</summary>\n\n```text\nName Stmts", markdown)
        self.assertTrue(markdown.endswith("```\n\n</details>"))

    def test_empty_diff_markdown_omits_diff_section(self: TestCoverageReport) -> None:
        """Omit the diff section when there is no diff report."""
        markdown = format_coverage_markdown(
            "Howler API", "84%", "green", "", "", "TOTAL 84%"
        )

        self.assertIn("# Howler API - Coverage Results", markdown)
        self.assertNotIn("Diff Coverage", markdown)
        self.assertNotIn("  \n", markdown)

    def test_coverage_color_thresholds(self: TestCoverageReport) -> None:
        """Use the expected color thresholds for coverage badges."""
        self.assertEqual(get_color(49), "red")
        self.assertEqual(get_color(50), "yellow")
        self.assertEqual(get_color(69), "yellow")
        self.assertEqual(get_color(70), "green")

    def test_generate_report_writes_rendered_markdown(self: TestCoverageReport) -> None:
        """Generate the report with a diff without indenting its Markdown."""

        def fake_check_output(command: list[str], cwd: Path) -> bytes:
            """Return coverage output and emulate diff-cover's report file."""
            if command[0] == "/tools/coverage" and command[1] == "report":
                return b"Name Stmts Miss Branch BrPart Cover\nTOTAL 10 1 2 0 90%\n"
            if command[0] == "/tools/diff-cover":
                (cwd / "diff-cover-report.md").write_text(
                    "# Diff Coverage\n\nDiff summary\n\n## src/app.py\nDetails\n",
                    encoding="utf-8",
                )
                return b"Coverage: 83%\n"
            return b""

        with TemporaryDirectory() as directory:
            package_root = Path(directory)
            (package_root / "diff.txt").write_text("diff", encoding="utf-8")
            with (
                patch(
                    "howler_coverage_report.shutil.which",
                    side_effect=lambda name: f"/tools/{name}",
                ),
                patch(
                    "howler_coverage_report.subprocess.check_output",
                    side_effect=fake_check_output,
                ),
                redirect_stdout(StringIO()),
            ):
                generate_coverage_report("Howler Sync Plugin", package_root)

            markdown = (package_root / "coverage-results.md").read_text(
                encoding="utf-8"
            )

        self.assertIn("\n# Howler Sync Plugin - Coverage Results\n", markdown)
        self.assertIn("\n## Diff Coverage\n", markdown)
        self.assertIn("<summary>src/app.py</summary>", markdown)
        self.assertIn("\n```text\nName Stmts", markdown)
        self.assertIn("Diff_Coverage-83%25-green", markdown)

    def test_generate_report_without_diff_shows_unavailable_badge(
        self: TestCoverageReport,
    ) -> None:
        """Show an NA badge when there is no diff file to measure."""

        def fake_check_output(command: list[str], cwd: Path) -> bytes:
            """Return the total coverage output."""
            if command[0] == "/tools/coverage" and command[1] == "report":
                return b"Name Stmts Miss Branch BrPart Cover\nTOTAL 10 1 2 0 90%\n"
            return b""

        with TemporaryDirectory() as directory:
            package_root = Path(directory)
            with (
                patch(
                    "howler_coverage_report.shutil.which",
                    side_effect=lambda name: f"/tools/{name}",
                ),
                patch(
                    "howler_coverage_report.subprocess.check_output",
                    side_effect=fake_check_output,
                ),
                redirect_stdout(StringIO()),
            ):
                generate_coverage_report("Howler API", package_root)

            markdown = (package_root / "coverage-results.md").read_text(
                encoding="utf-8"
            )

        self.assertIn("Diff_Coverage-NA%25-red", markdown)


if __name__ == "__main__":
    unittest.main()
