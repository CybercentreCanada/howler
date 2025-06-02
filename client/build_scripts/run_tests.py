import os
import re
import shlex
import subprocess
import sys
import textwrap
from pathlib import Path


def prep_command(cmd: str):
    print(">", cmd)
    return shlex.split(cmd)


def main():
    try:
        if Path(".coverage").exists():
            print("Removing existing coverage files")
            subprocess.check_call(
                prep_command("coverage erase --data-file=.coverage"),
            )

        print("Running pytest")
        if len(sys.argv) > 1:
            pytest = subprocess.Popen(
                prep_command(f"pytest -rP -vv {' '.join(sys.argv[1:])}"),
            )
        else:
            pytest = subprocess.Popen(
                prep_command("pytest --cov=howler_client --cov-branch -rP -vv test"),
                stdout=subprocess.PIPE,
            )

        output = ""
        while pytest.poll() is None:
            if pytest.stdout:
                out = pytest.stdout.read(1).decode()
                output += out
                sys.stdout.write(out)
                sys.stdout.flush()

        if pytest.stdout:
            out = pytest.stdout.read().decode()
            output += out
            sys.stdout.write(out)
            sys.stdout.flush()

        return_code = pytest.poll()
        if return_code is not None and return_code > 0:
            if output and os.environ.get("TF_BUILD", ""):
                markdown_output = textwrap.dedent(
                    """
                ![Static Badge](https://img.shields.io/badge/build-failing-red)

                <details>
                    <summary>Error Output</summary>
                """
                ).strip()

                markdown_output += "\n".join(
                    ("    " + line)
                    for line in re.sub(
                        r"[\s\S]+=+ FAILURES =+([\S\s]+)-+ coverage[\s\S]+",
                        r"\n\1",
                        output,
                    ).splitlines()
                )

                markdown_output += "\n</details>"

                print(
                    "##vso[task.setvariable variable=error_result]" + markdown_output.replace("\n", "%0D%0A") + "\n\n"
                )
            raise subprocess.CalledProcessError(return_code, pytest.args, output=output, stderr=None)

    except subprocess.CalledProcessError as e:
        print("Error occurred while running script:", e)
        sys.exit(e.returncode)


if __name__ == "__main__":
    main()
