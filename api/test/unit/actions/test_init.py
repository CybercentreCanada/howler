import os
from pathlib import Path

from howler.actions import execute, specifications
from howler.config import config
from howler.odm.models.user import User
from howler.odm.randomizer import random_model_obj

PLUGIN_PATH = Path(os.environ.get("HWL_PLUGIN_DIRECTORY", "/etc/howler/plugins"))

folders = [Path(__file__).parent.parent.parent.parent / "howler" / "actions"]

for plugin in config.core.plugins:
    folders.append(PLUGIN_PATH / plugin / "actions")


def test_specifications():
    result = specifications()
    files: list[Path] = []

    for folder in folders:
        files += list(path for path in folder.glob("*.py") if path.stem != "__init__")

    # We ignore the example action, which isn't included in the list of valid actions
    assert len(result) == len(files) - 1

    assert sorted([data["id"] for data in result]) == sorted([f.stem for f in files if f.stem != "example_plugin"])


def test_execute_bad_plugin():
    result = execute(
        "doesntexistandneverwillpleasedontusethisid",
        "howler.id:*",
        user=random_model_obj(User),
    )

    assert len(result) == 1

    result = result[0]

    assert result["outcome"] == "error"
    assert result["title"] == "Unknown Action"
    assert (
        result["message"]
        == "The operation ID provided (doesntexistandneverwillpleasedontusethisid) does not match any enabled "
        "operations."
    )


def test_execute_missing_roles():
    bad_user: User = random_model_obj(User)

    bad_user.type = []

    result = execute("add_label", "howler.id:*", user=bad_user)

    assert len(result) == 1

    result = result[0]

    assert result["outcome"] == "error"
    assert result["title"] == "Insufficient permissions"
    assert (
        result["message"]
        == "The operation ID provided (add_label) requires permissions you do not have (automation_basic). Contact "
        "HOWLER Support for more information."
    )
