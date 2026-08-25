import subprocess
import sys
from pathlib import Path

from howler.odm.contract import build_contract_inventory, render_contract_inventory

CONTRACT_PATH = Path(__file__).parent / "fixtures/odm_contract_inventory.json"


def test_odm_contract_matches_snapshot():
    subprocess.run(
        [
            sys.executable,
            "-m",
            "build_scripts.generate_odm_contract",
            "--check",
            "--output",
            str(CONTRACT_PATH),
        ],
        check=True,
    )


def test_odm_contract_covers_migration_surfaces():
    inventory = build_contract_inventory()

    assert len(inventory["models"]) > 100
    assert len(inventory["field_types"]) > 30
    assert set(inventory["collections"]) >= {"action", "analytic", "case", "event", "hit", "user"}
    assert all("legacy_index" in collection for collection in inventory["collections"].values())
    assert all("ilm_template" in inventory["collections"][collection] for collection in ("case", "event", "hit"))
    assert inventory["generated_artifacts"]
    assert inventory["source_usage"]["imports"]
    assert inventory["source_usage"]["datastore_calls"]
    assert inventory["source_usage"]["extension_hooks"]
    assert all(outcomes for outcomes in inventory["field_validation"].values())


def test_odm_contract_rendering_is_deterministic():
    assert render_contract_inventory() == render_contract_inventory()
