"""Readers for immutable ODM cutover goldens.

The fixtures in this module were captured from the legacy ODM before its removal. Tests must
compare migrated models with these checked-in outcomes, never regenerate expectations from the
implementation under test.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MODEL_GOLDEN_PATH = Path(__file__).parent / "fixtures/legacy_primitive_goldens.json"
SERIALIZATION_GOLDEN_PATH = Path(__file__).parent / "fixtures/legacy_serialization_edge_goldens.json"
TEMPLATE_ORDER_GOLDEN_PATH = Path(__file__).parent / "fixtures/legacy_dynamic_template_order.json"
CONTRACT_GOLDEN_PATH = Path(__file__).parent.parent / "odm/fixtures/odm_contract_inventory.json"


def primitive_golden(case: str) -> Any:
    """Return one immutable serialized legacy-model outcome."""
    data = json.loads(MODEL_GOLDEN_PATH.read_text(encoding="utf-8"))
    assert data["fixture_version"] == 1
    return data["cases"][case]


def contract_golden() -> dict[str, Any]:
    """Return the preserved full legacy contract inventory."""
    return json.loads(CONTRACT_GOLDEN_PATH.read_text(encoding="utf-8"))


def serialization_golden() -> dict[str, Any]:
    """Return focused frozen legacy IP/date/Related/Hit serialization outcomes."""
    return json.loads(SERIALIZATION_GOLDEN_PATH.read_text(encoding="utf-8"))


def template_order_golden() -> dict[str, Any]:
    """Return the frozen semantic dynamic-template precedence sequences."""
    return json.loads(TEMPLATE_ORDER_GOLDEN_PATH.read_text(encoding="utf-8"))
