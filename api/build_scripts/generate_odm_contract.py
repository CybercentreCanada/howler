"""Generate or verify the legacy ODM compatibility contract fixture."""

from __future__ import annotations

import argparse
from pathlib import Path

from howler.odm.contract import render_contract_inventory, write_contract_inventory

DEFAULT_OUTPUT = Path(__file__).parents[1] / "test/unit/odm/fixtures/odm_contract_inventory.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if the committed contract differs from the ODM")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Contract JSON output path")
    args = parser.parse_args()

    if args.check:
        expected = args.output.read_text(encoding="utf-8")
        if expected != render_contract_inventory():
            parser.error(f"{args.output} is stale; regenerate it without --check")
        return 0

    write_contract_inventory(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
