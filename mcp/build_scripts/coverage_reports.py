import platform
import re
import shlex
import subprocess
import sys
import textwrap
from pathlib import Path

newline = "\n"


def get_color(percentage: int) -> str:
    if percentage < 50:
        return "red"
    if percentage < 70:
        return "yellow"
    return "green"


def main() -> None:
    diff_exists = Path("diff.txt").exists()
    try:
        report_result = subprocess.check_output(shlex.split("coverage report --data-file=.coverage")).decode()
        subprocess.check_output(shlex.split("coverage xml --data-file=.coverage"))
        subprocess.check_output(shlex.split("coverage html --data-file=.coverage"))

        diff_result = ""
        diff_badge = ""
        if diff_exists:
            diff_report = subprocess.check_output(
                shlex.split("diff-cover coverage.xml --diff-file diff.txt --markdown-report diff-cover-report.md")
            ).decode()
            diff_percentage = next(
                (line.split()[-1] for line in diff_report.splitlines() if "Coverage:" in line), "NA%"
            )
            diff_badge = (
                f"![Static Badge](https://img.shields.io/badge/Diff_Coverage-{diff_percentage}"
                f"-{get_color(int(diff_percentage.rstrip('%')) if diff_percentage != 'NA%' else 0)}?style=flat)"
            )
            diff_result = Path("diff-cover-report.md").read_text()
            diff_result = re.sub(r"### (.+py)", r"<details>\n<summary>\1</summary>\n", diff_result)
            diff_result += "\n</details>"

        total_percentage = report_result.splitlines()[-1].split()[-1]
        total_color = get_color(int(total_percentage.rstrip("%")))
        markdown_output = textwrap.dedent(
            f"""
            ![Static Badge](https://img.shields.io/badge/Build%20(Python%20{platform.python_version()})-passing-brightgreen)

            # Howler MCP - Coverage Results
            ![Static Badge](https://img.shields.io/badge/Total_Coverage-{total_percentage}-{total_color}?style=flat) {diff_badge}

{newline.join([(" " * 8) + line for line in diff_result.splitlines()]) if diff_result else ""}

            ## Full Coverage Report
            <details>
                <summary>Expand</summary>

{newline.join([(" " * 12) + line for line in report_result.splitlines()])}
            </details>
            """
        ).strip()
        Path(__file__).parent.parent.joinpath("coverage-results.md").write_text(markdown_output)
    except subprocess.CalledProcessError as error:
        sys.stderr.write(" ".join(error.cmd) + " failed.\n")
        if error.output:
            sys.stderr.write(error.output.decode())
        sys.exit(error.returncode)
