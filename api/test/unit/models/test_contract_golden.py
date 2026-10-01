"""Integrity and substantive coverage checks for frozen migration goldens."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys

from test.unit.models._goldens import CONTRACT_GOLDEN_PATH, MODEL_GOLDEN_PATH, contract_golden

FROZEN_CONTRACT_SHA256 = "6a85a3df82c548ad9d398e6af18c07927e957b2b771ac21c40faea40821add35"


def test_full_contract_fixture_is_the_original_frozen_baseline() -> None:
    """The complete 4.4 MB ODM inventory remains byte-for-byte unchanged."""
    assert hashlib.sha256(CONTRACT_GOLDEN_PATH.read_bytes()).hexdigest() == FROZEN_CONTRACT_SHA256


def test_full_contract_fixture_retains_migration_surfaces() -> None:
    inventory = contract_golden()

    assert inventory["contract_version"] == 1
    assert len(inventory["models"]) > 100
    assert len(inventory["field_types"]) > 30
    assert set(inventory["collections"]) >= {"action", "analytic", "case", "event", "hit", "user"}
    assert all("legacy_index" in collection for collection in inventory["collections"].values())
    assert all("ilm_template" in inventory["collections"][name] for name in ("case", "event", "hit"))
    assert inventory["generated_artifacts"]
    assert inventory["source_usage"]["imports"]
    assert inventory["source_usage"]["datastore_calls"]
    assert inventory["source_usage"]["extension_hooks"]
    assert all(outcomes for outcomes in inventory["field_validation"].values())


def test_contract_check_command_is_legacy_free_and_read_only() -> None:
    subprocess.run(
        [sys.executable, "-m", "build_scripts.generate_odm_contract", "--check"],
        check=True,
    )


def test_primitive_golden_has_pinned_capture_provenance() -> None:
    data = json.loads(MODEL_GOLDEN_PATH.read_text(encoding="utf-8"))
    assert data["fixture_version"] == 1
    assert data["capture"]["source_head"] == "3071fc4ea45d4b2dd44a7ee1646095426097d061"
    assert data["capture"]["command"].startswith("One-off api/.venv/bin/python capture")
    assert hashlib.sha256(MODEL_GOLDEN_PATH.read_bytes()).hexdigest() == (
        "4f8e5b2f1625a8c0a16fdfec46104d6ab9c3f788c88df1970e699bd06cff16b9"
    )
