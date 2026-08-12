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


def generate_badge(title, percentage, color):
    return (
        f"![Static Badge](https://img.shields.io/badge/{title.replace(' ', '_')}-{percentage}25-{color}?style="
        "flat&logo=azuredevops&logoColor=%230078D7)"
    )


def main() -> None:
    diff_exists = Path("diff.txt").exists()
    try:
        report_result = subprocess.check_output(shlex.split("coverage report --data-file=.coverage")).decode()
        subprocess.check_output(shlex.split("coverage xml --data-file=.coverage"))
        subprocess.check_output(shlex.split("coverage html --data-file=.coverage"))

        sys.stdout.write(report_result + "\n")

        diff_report_result = ""
        if diff_exists:
            diff_report_result = subprocess.check_output(
                shlex.split("diff-cover coverage.xml --diff-file diff.txt --markdown-report diff-cover-report.md")
            ).decode()
            sys.stdout.write(diff_report_result + "\n")

        diff_result = ""
        diff_badge = ""
        diff_percentage = "NA%"
        diff_percentage_int = 0
        diff_color = "grey"
        if diff_exists:
            try:
                diff_percentage = (
                    [line for line in diff_report_result.splitlines() if "Coverage:" in line].pop().split(" ").pop()
                )
                diff_percentage_int = int(diff_percentage.replace("%", ""))
            except IndexError:
                pass

            diff_color = get_color(diff_percentage_int)

            with open("diff-cover-report.md") as diff_report:
                diff_result = diff_report.read().replace("# ", "## ").replace("__init__.py", "\\_\\_init\\_\\_.py")

                diff_result = re.sub(r"### (.+py)", r"<details>\n<summary>\1</summary>\n", diff_result)
                diff_result = re.sub(r"\n---(\n+<details>)", r"\n</details>\1", diff_result)

                diff_result += "\n</details>"

            diff_badge = generate_badge("Diff Coverage", diff_percentage, diff_color)

        total_percentage = report_result.splitlines()[-1].split()[-1]
        total_color = get_color(int(total_percentage.rstrip("%")))
        markdown_output = textwrap.dedent(
            f"""
            ![Static Badge](https://img.shields.io/badge/Build%20(Python%20{platform.python_version()})-passing-brightgreen)

            # Howler MCP - Coverage Results
            {generate_badge("Total Coverage", total_percentage, total_color)} {diff_badge}

{newline.join([(" " * 12) + line for line in diff_result.splitlines()]) if diff_result else ""}

            ## Full Coverage Report
            <details>
                <summary>Expand</summary>

{newline.join([(" " * 16) + line for line in report_result.splitlines()])}
            </details>
            """
        ).strip()
        Path(__file__).parent.parent.joinpath("coverage-results.md").write_text(markdown_output)
    except subprocess.CalledProcessError as error:
        sys.stderr.write(" ".join(error.cmd) + " failed.\n")
        if error.output:
            sys.stderr.write(error.output.decode())
        sys.exit(error.returncode)
