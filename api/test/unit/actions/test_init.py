import os
from pathlib import Path
from unittest.mock import patch

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
    assert result["message"].startswith("The operation ID provided (add_label) requires permissions you do not have")


@patch("howler.actions.datastore")
def test_execute_basic_user_hit_limit_exceeded(mock_ds):
    """Test that basic users are blocked when exceeding hit limits."""
    basic_user: User = random_model_obj(User)
    basic_user.type = ["user", "actionrunner_basic"]

    # Mock datastore to return a hit count exceeding the basic limit
    mock_ds.return_value.hit.search.return_value = {"total": 100}  # Exceeds MAX_HITS_BASIC of 20 for add_label

    result = execute("add_label", "howler.id:*", user=basic_user, category="generic", label="test")

    assert len(result) == 1
    result = result[0]

    assert result["outcome"] == "error"
    assert result["title"] == "Hit limit exceeded"
    assert "100 hits" in result["message"]
    assert "20" in result["message"]


@patch("howler.actions.datastore")
def test_execute_advanced_user_higher_limit(mock_ds):
    """Test that advanced users have higher limits."""
    advanced_user: User = random_model_obj(User)
    advanced_user.type = ["user", "actionrunner_advanced"]

    # Mock datastore to return a hit count that exceeds basic but not advanced limit
    # This should pass the limit check - action itself will be called
    mock_ds.return_value.hit.search.return_value = {"total": 50, "items": []}
    mock_ds.return_value.hit.update_by_query.return_value = None

    result = execute("add_label", "howler.id:*", user=advanced_user, category="generic", label="test")

    # Should not be blocked by limit - will proceed to action execution
    # The action might return "skipped" because no hits match, but not "Hit limit exceeded"
    assert all(r["title"] != "Hit limit exceeded" for r in result)


@patch("howler.actions.datastore")
def test_execute_admin_user_bypasses_role_check_and_gets_advanced_limit(mock_ds):
    """Test that admin users bypass role checks and get the advanced hit limit."""
    admin_user: User = random_model_obj(User)
    admin_user.type = ["admin", "user"]  # Admin without explicit actionrunner roles

    # Mock datastore to return a hit count that exceeds basic (20) but not advanced (1000)
    mock_ds.return_value.hit.search.return_value = {"total": 500, "items": []}
    mock_ds.return_value.hit.update_by_query.return_value = None

    result = execute("add_label", "howler.id:*", user=admin_user, category="generic", label="test")

    # Admin should bypass role check and use advanced limit, so 500 hits should be allowed
    assert all(r["title"] != "Insufficient permissions" for r in result)
    assert all(r["title"] != "Hit limit exceeded" for r in result)


@patch("howler.actions.datastore")
def test_execute_user_with_both_basic_and_advanced_roles(mock_ds):
    """Test that users with both basic and advanced roles get the higher (advanced) limit."""
    mixed_user: User = random_model_obj(User)
    mixed_user.type = ["user", "actionrunner_basic", "actionrunner_advanced"]

    # Mock datastore to return a hit count that exceeds basic (20) but not advanced (1000)
    mock_ds.return_value.hit.search.return_value = {"total": 50, "items": []}
    mock_ds.return_value.hit.update_by_query.return_value = None

    result = execute("add_label", "howler.id:*", user=mixed_user, category="generic", label="test")

    # Should use advanced limit, so 50 hits should be allowed
    assert all(r["title"] != "Hit limit exceeded" for r in result)
