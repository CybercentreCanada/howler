import os
import platform
import re
import shlex
import socket
import subprocess
import sys
import textwrap
import time
import uuid
from pathlib import Path


def prep_command(cmd: str):
    print(">", cmd)
    return shlex.split(cmd)


def get_available_port() -> int:
    """Reserve an ephemeral local port number for the test API server."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main():  # noqa: C901
    background_server = None
    try:
        run_id = uuid.uuid4().hex
        api_port = get_available_port()
        test_env = {
            **os.environ,
            "FLASK_RUN_PORT": str(api_port),
            "HWL_DATASTORE_INDEX_PREFIX": f"howler-test-{run_id}",
            "HWL_TEST_API_HOST": f"http://localhost:{api_port}",
            "TESTING": "true",
            "HWL_START_BACKGROUND_SERVICES": "false",
            "HWL_CORRELATION_QUEUE_NAME": f"howler.ingestion_queue.test.{run_id}",
        }

        print("Removing existing coverage files")
        subprocess.check_call(
            prep_command("coverage erase --data-file=.coverage"),
        )

        print("Running howler server (with coverage)")
        background_server = subprocess.Popen(
            prep_command("coverage run -m flask --app howler.app run --no-reload"),
            env={**test_env, "HWL_START_BACKGROUND_SERVICES": "true"},
        )

        time.sleep(5)
        print("Running pytest")
        pytest_args = sys.argv[1:] if len(sys.argv) > 1 else ["test"]
        pytest_cmd = [
            "pytest",
            "--cov=howler",
            "--cov-branch",
            "--cov-config=.coveragerc.pytest",
            "-rFE",
            "-v",
            *pytest_args,
        ]
        print(">", shlex.join(pytest_cmd))

        pytest = subprocess.Popen(
            pytest_cmd,
            stdout=subprocess.PIPE,
            env=test_env,
        )

        output = ""
        while pytest.poll() is None:
            if pytest.stdout:
                out = pytest.stdout.read(1).decode(errors="ignore")
                output += out
                sys.stdout.write(out)
                sys.stdout.flush()

        if pytest.stdout:
            out = pytest.stdout.read().decode(errors="ignore")
            output += out
            sys.stdout.write(out)
            sys.stdout.flush()

        return_code = pytest.poll()
        if return_code is not None and return_code > 0:
            if output and os.environ.get("WRITE_MARKDOWN", ""):
                markdown_output = textwrap.dedent(
                    f"""
                ![Static Badge](https://img.shields.io/badge/build%20(Python%20{platform.python_version()})-failing-red)

                <details>
                    <summary>Error Output</summary>
                """
                ).strip()

                raw_failures = re.sub(
                    r"[\s\S]+=+ FAILURES =+([\S\s]+)-+ coverage[\s\S]+",
                    r"\n\1",
                    output,
                )

                markdown_output += "\n".join(("    " + line) for line in raw_failures.splitlines())

                markdown_output += "\n</details>"

                print("Markdown result:")
                print(markdown_output)

                summary_file = os.getenv("GITHUB_STEP_SUMMARY")
                if summary_file:
                    print(f"Writing to {summary_file}")
                    Path(summary_file).write_text(f"```\n{raw_failures}\n```")

                (Path(__file__).parent.parent / "test-results.md").write_text(markdown_output)

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
        if background_server:
            background_server.send_signal(2)
            background_server.wait()
        sys.exit(e.returncode)


if __name__ == "__main__":
    main()
