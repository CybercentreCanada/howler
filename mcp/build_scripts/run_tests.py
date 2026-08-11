import os
import platform
import re
import shlex
import subprocess
import sys
import textwrap
from pathlib import Path


def main() -> None:
    pytest_args = sys.argv[1:] if len(sys.argv) > 1 else ["test"]
    pytest_cmd = [
        "pytest",
        "-vv",
        "-ra",
        "--tb=long",
        "-s",
        *pytest_args,
    ]
    if len(sys.argv) == 1:
        pytest_cmd[1:1] = ["--cov=howler_mcp", "--cov-branch"]

    sys.stdout.write(f"> {shlex.join(pytest_cmd)}\n")

    process = subprocess.Popen(pytest_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output = ""
    if process.stdout is None:
        raise RuntimeError("Could not capture pytest output")
    for line in iter(process.stdout.readline, b""):
        decoded = line.decode(errors="ignore")
        output += decoded
        sys.stdout.write(decoded)
        sys.stdout.flush()

    return_code = process.wait()
    if return_code == 0:
        return

    if os.environ.get("WRITE_MARKDOWN"):
        raw_failures = re.sub(r"[\s\S]+=+ FAILURES =+([\S\s]+)-+ coverage[\s\S]+", r"\n\1", output)
        markdown_output = textwrap.dedent(
            f"""
            ![Static Badge](https://img.shields.io/badge/build%20(Python%20{platform.python_version()})-failing-red)

            <details>
                <summary>Error Output</summary>
            """
        ).strip()
        markdown_output += "\n" + "\n".join("    " + line for line in raw_failures.splitlines())
        markdown_output += "\n</details>"
        Path(__file__).parent.parent.joinpath("test-results.md").write_text(markdown_output)

    raise SystemExit(return_code)
