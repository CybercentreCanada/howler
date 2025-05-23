import os
import platform
import re
import shlex
import subprocess
import sys
import textwrap
import time
from pathlib import Path


def prep_command(cmd: str):
    print(">", cmd)
    return shlex.split(cmd)


def main():
    try:
        print("Removing existing coverage files")
        subprocess.check_call(
            prep_command("coverage erase --data-file=.coverage"),
        )

        print("Running howler server (with coverage)")
        background_server = subprocess.Popen(
            prep_command("coverage run -m flask --app howler.app run --no-reload"),
        )

        print("Running pytest")
        time.sleep(2)
        _path = sys.argv[1] if len(sys.argv) > 1 else "test"

        pytest = subprocess.Popen(
            prep_command(f"pytest --cov=howler --cov-branch --cov-config=.coveragerc.pytest -rP -vv {_path}"),
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
                    f"""
                ![Static Badge](https://img.shields.io/badge/build%20(Python%20{platform.python_version()})-failing-red)

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

        print("Shutting down background server")
        background_server.send_signal(2)
        background_server.wait()

        print("Coverage server is down, combining coverage files")

        workdir = Path(__file__).parent.parent
        if not (workdir / ".coverage.server").exists():
            print("WARN: .coverage.server file missing!")

        if not (workdir / ".coverage.pytest").exists():
            print("WARN: .coverage.pytest file missing!")

        subprocess.check_call(
            prep_command("coverage combine --data-file=.coverage .coverage.server .coverage.pytest"),
        )

    except subprocess.CalledProcessError as e:
        print("Error occurred while running script:", e)
        print("Shutting down background server")
        background_server.send_signal(2)
        background_server.wait()
        sys.exit(e.returncode)


if __name__ == "__main__":
    main()
