import platform
import re
import subprocess
import sys
import textwrap
from pathlib import Path


def get_color(percentage):
    if percentage < 50:
        return "red"
    elif percentage < 70:
        return "yellow"
    else:
        return "green"


def generate_badge(title, percentage, color):
    return (
        f"![Static Badge](https://img.shields.io/badge/{title.replace(' ', '_')}-{percentage}25-{color}?style="
        "flat&logo=azuredevops&logoColor=%230078D7)"
    )


def main():
    try:
        report_result = subprocess.check_output(["coverage", "report", "--data-file=.coverage"]).decode()
        subprocess.check_output(["coverage", "xml", "--data-file=.coverage"])
        subprocess.check_output(["coverage", "html", "--data-file=.coverage"])
        print(report_result)

        diff_markdown = ""
        diff_badge = ""
        diff_file = Path("diff.txt")
        if diff_file.is_file():
            diff_report_result = subprocess.check_output(
                [
                    "diff-cover",
                    "coverage.xml",
                    "--diff-file",
                    str(diff_file),
                    "--markdown-report",
                    "diff-cover-report.md",
                ]
            ).decode()
            print(diff_report_result)

            coverage_line = next((line for line in diff_report_result.splitlines() if "Coverage:" in line), None)
            diff_percentage = coverage_line.split()[-1] if coverage_line else "NA%"
            diff_color = get_color(int(diff_percentage.rstrip("%"))) if diff_percentage.rstrip("%").isdigit() else "red"
            diff_badge = generate_badge("Diff Coverage", diff_percentage, diff_color)

            report_path = Path("diff-cover-report.md")
            if report_path.is_file():
                diff_markdown = report_path.read_text().replace("# ", "## ")
                diff_markdown = diff_markdown.replace("__init__.py", r"\_\_init\_\_.py")
                diff_markdown = re.sub(r"### (.+py)", r"<details>\n<summary>\1</summary>\n", diff_markdown)
                diff_markdown = re.sub(r"\n---(\n+<details>)", r"\n</details>\1", diff_markdown)
                diff_markdown += "\n</details>"

        total_percentage = report_result.splitlines()[-1].split()[-1]
        total_color = get_color(int(total_percentage.rstrip("%")))
        newline = "\n"
        markdown_output = textwrap.dedent(
            f"""
            ![Static Badge](https://img.shields.io/badge/Build%20(Python%20{platform.python_version()})-passing-brightgreen)

            # Howler Evidence Plugin - Coverage Results
            {generate_badge("Total Coverage", total_percentage, total_color)} {diff_badge}

            {diff_markdown}

            ## Full Coverage Report
            <details>
                <summary>Expand</summary>

            {newline.join([(" " * 12) + line for line in report_result.splitlines()])}
            </details>
            """
        ).strip()

        print("Markdown result:")
        print(markdown_output)
        (Path(__file__).parent.parent / "coverage-results.md").write_text(markdown_output)
    except subprocess.CalledProcessError as error:
        print(" ".join(error.cmd), "failed.")
        if error.output:
            print(error.output.decode())
        sys.exit(error.returncode)


if __name__ == "__main__":
    main()
