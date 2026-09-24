"""Synthetic data must exercise real validation and stay independent of the legacy ODM."""

import ast
import subprocess
import sys
from pathlib import Path

import pytest

from howler.models.action import Action
from howler.models.analytic import Analytic
from howler.models.event import Event
from howler.models.hit import Hit
from howler.models.user import User
from howler.sample_data.randomizer import random_minimal_obj, random_model_obj


@pytest.mark.parametrize("model", [Action, Analytic, Event, Hit, User])
@pytest.mark.parametrize("generator", [random_model_obj, random_minimal_obj])
def test_generated_model_round_trips(model, generator):
    instance = generator(model)
    data = instance.as_primitives()
    data.pop("__index", None)
    restored = model.model_validate(data)
    assert restored.as_primitives() == instance.as_primitives()


def test_sample_data_import_does_not_load_legacy_odm():
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import howler.app; import howler.sample_data.random_data; "
            "assert not any(n == 'howler.odm' or n.startswith('howler.odm.') for n in sys.modules)",
        ],
        check=True,
    )


def test_runtime_modules_do_not_import_legacy_odm():
    root = Path(__file__).resolve().parents[3] / "howler"
    violations = []
    for path in root.rglob("*.py"):
        if path.is_relative_to(root / "odm"):
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
                if node.module == "howler":
                    names.extend(f"howler.{alias.name}" for alias in node.names)
            else:
                continue
            if any(name == "howler.odm" or name.startswith("howler.odm.") for name in names):
                violations.append(f"{path.relative_to(root)}:{node.lineno}")
    assert not violations
