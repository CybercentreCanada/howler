"""Verify the byte-for-byte frozen ODM migration contract.

The legacy generator was intentionally retired with ``howler.odm``. This command only verifies
the durable cutover baseline; it never imports application model code or regenerates expectations.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

DEFAULT_OUTPUT = Path(__file__).parents[1] / "test/unit/odm/fixtures/odm_contract_inventory.json"
FROZEN_CONTRACT_SHA256 = "6a85a3df82c548ad9d398e6af18c07927e957b2b771ac21c40faea40821add35"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify the frozen inventory's SHA-256")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Frozen inventory path to verify")
    args = parser.parse_args()

    if not args.check:
        parser.error("contract generation is retired; use --check to verify the frozen migration baseline")
    if args.output.resolve() != DEFAULT_OUTPUT.resolve():
        parser.error("only the checked-in frozen migration baseline can be verified")

    actual_hash = hashlib.sha256(args.output.read_bytes()).hexdigest()
    if actual_hash != FROZEN_CONTRACT_SHA256:
        parser.error(f"{args.output} differs from the frozen Step 1 migration baseline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
