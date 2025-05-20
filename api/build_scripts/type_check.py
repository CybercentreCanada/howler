import shlex
import subprocess


def prep_command(cmd: str) -> list[str]:
    "Take in a raw string and return a split array of entries understood by functions like subprocess.check_output."
    print(">", cmd)
    return shlex.split(cmd)


def main() -> None:
    "Main type checking script"
    result = subprocess.check_output(prep_command('find howler -type f -name "*.py"')).decode().strip().split("\n")

    subprocess.check_call(prep_command(f'python -m mypy {" ".join(result)}'))


if __name__ == "__main__":
    main()
