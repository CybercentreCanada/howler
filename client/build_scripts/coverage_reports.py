"""Client coverage report entry point."""

import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SHARED_SCRIPTS = next(
    ancestor / "scripts"
    for ancestor in Path(__file__).resolve().parents
    if (ancestor / "scripts" / "howler_coverage_report.py").is_file()
)
if str(SHARED_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SHARED_SCRIPTS))

from howler_coverage_report import generate_coverage_report  # noqa: E402


def main() -> None:
    generate_coverage_report("Howler Client", PACKAGE_ROOT)


if __name__ == "__main__":
    main()
