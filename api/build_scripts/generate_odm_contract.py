"""Generate or verify the legacy ODM compatibility contract fixture."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from howler.odm.contract import render_contract_inventory, write_contract_inventory

DEFAULT_OUTPUT = Path(__file__).parents[1] / "test/unit/odm/fixtures/odm_contract_inventory.json"
FROZEN_CONTRACT_SHA256 = "6a85a3df82c548ad9d398e6af18c07927e957b2b771ac21c40faea40821add35"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if the committed contract differs from the ODM")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Contract JSON output path")
    args = parser.parse_args()

    if args.output.resolve() == DEFAULT_OUTPUT.resolve():
        if not args.check:
            parser.error(f"{DEFAULT_OUTPUT} is a frozen migration baseline; choose a different --output")
        actual_hash = hashlib.sha256(args.output.read_bytes()).hexdigest()
        if actual_hash != FROZEN_CONTRACT_SHA256:
            parser.error(f"{args.output} differs from the frozen Step 1 migration baseline")
        return 0

    if args.check:
        expected = args.output.read_text(encoding="utf-8")
        if expected != render_contract_inventory():
            parser.error(f"{args.output} is stale; regenerate it without --check")
        return 0

    write_contract_inventory(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
