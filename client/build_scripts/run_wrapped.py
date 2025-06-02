import os
import re
import shlex
import subprocess
import sys
import textwrap


def prep_command(cmd: str) -> list[str]:
    "Take in a raw string and return a split array of entries understood by functions like subprocess.check_output."
    print(">", cmd)
    return shlex.split(cmd)


def main() -> None:
    "Main command script"
    print(sys.argv)

    cmd = sys.argv.copy()
    cmd.pop(0)

    mypy = subprocess.Popen(
        prep_command(f'python -m {" ".join(cmd)}'),
        stdout=subprocess.PIPE,
    )

    output = ""
    while mypy.poll() is None:
        if mypy.stdout:
            out = mypy.stdout.read(1).decode()
            output += out
            sys.stdout.write(out)
            sys.stdout.flush()

    if mypy.stdout:
        out = mypy.stdout.read().decode()
        output += out
        sys.stdout.write(out)
        sys.stdout.flush()

    return_code = mypy.poll()
    if return_code is not None and return_code > 0:
        if output and os.environ.get("TF_BUILD", ""):
            shield_str = re.sub(r" --.+", "", " ".join(cmd)).replace(" ", "_")

            markdown_output = (
                textwrap.dedent(
                    f"""
            ![Static Badge](https://img.shields.io/badge/{shield_str}-failing-red)

            <details>
                <summary>Command Output</summary>
            """
                ).strip()
                + "\n\n"
            )

            markdown_output += "\n".join(f"    {line}" for line in output.strip().splitlines())

            markdown_output += "\n</details>"

            print("##vso[task.setvariable variable=error_result]" + markdown_output.replace("\n", "%0D%0A") + "\n\n")

        raise subprocess.CalledProcessError(return_code, mypy.args, output=output, stderr=None)


if __name__ == "__main__":
    main()
