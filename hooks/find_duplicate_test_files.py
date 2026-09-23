#!/usr/bin/env python3

import subprocess
import sys
from collections import defaultdict
from pathlib import Path


def test_files(repository_root: Path) -> list[tuple[Path, Path]]:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repository_root),
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    files: list[tuple[Path, Path]] = []
    for filename in result.stdout.splitlines():
        path = Path(filename)
        if not (path.match("test_*.py") or path.match("*_test.py")):
            continue

        try:
            test_root_index = path.parts.index("test")
        except ValueError:
            continue

        absolute_path = repository_root / path
        if not absolute_path.is_file():
            continue

        test_root = repository_root.joinpath(*path.parts[: test_root_index + 1])
        files.append((absolute_path, test_root))

    return files


def pytest_module_name(path: Path, test_root: Path) -> str:
    module_parts = [path.stem]
    directory = path.parent

    while directory != test_root and (directory / "__init__.py").is_file():
        module_parts.insert(0, directory.name)
        directory = directory.parent

    if directory == test_root and (directory / "__init__.py").is_file():
        module_parts.insert(0, directory.name)

    return ".".join(module_parts)


def main() -> int:
    repository_root = Path(__file__).resolve().parent.parent
    modules: dict[tuple[Path, str], list[Path]] = defaultdict(list)

    for path, test_root in test_files(repository_root):
        module_name = pytest_module_name(path, test_root)
        modules[(test_root, module_name)].append(path)

    duplicates = {key: paths for key, paths in modules.items() if len(paths) > 1}
    if not duplicates:
        print("No duplicate pytest test modules found.")
        return 0

    print("Duplicate pytest test modules found:")
    for (test_root, module_name), paths in sorted(
        duplicates.items(), key=lambda item: str(item[0])
    ):
        print(f"  {module_name} ({test_root.relative_to(repository_root)}):")
        for path in sorted(paths):
            print(f"    {path.relative_to(repository_root)}")

    return 1


if __name__ == "__main__":
    sys.exit(main())
