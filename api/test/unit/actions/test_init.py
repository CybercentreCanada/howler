import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from howler.actions import execute, execute_stored_action, specifications
from howler.config import config
from howler.odm.models.howler_data import HitStatusTransition
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
        files += list(path for path in folder.glob("*.py") if path.stem not in ("__init__", "models"))

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


def test_execute_invalid_argument_with_sanitizer_delimiter():
    user: User = random_model_obj(User)
    user.type = ["actionrunner_basic"]

    result = execute(
        "add_label",
        "howler.id:*",
        user=user,
        category="generic",
        label="test",
        **{"===": "unexpected"},
    )

    assert result == [
        {
            "query": "(howler.id:*)",
            "outcome": "error",
            "title": "Invalid Arguments",
            "message": "===: Extra inputs are not permitted (received 'unexpected')",
        }
    ]


@patch("howler.actions.datastore")
@patch("howler.actions.add_label.execute")
def test_execute_stored_action_ignores_extra_arguments(mock_execute, mock_datastore):
    user: User = random_model_obj(User)
    user.type = ["actionrunner_basic"]
    mock_execute.return_value = []
    mock_datastore.return_value.hit.search.return_value = {"total": 1}

    result = execute_stored_action(
        "add_label",
        "howler.id:*",
        user=user,
        category="generic",
        label="kept",
        obsolete_argument="from an older action",
    )

    assert result == []
    mock_execute.assert_called_once_with(
        query="howler.id:*",
        request_id=None,
        user=user,
        category="generic",
        label="kept",
    )


@patch("howler.actions.datastore")
@patch("howler.actions.add_label.execute")
def test_execute_stored_action_still_rejects_invalid_declared_arguments(mock_execute, mock_datastore):
    user: User = random_model_obj(User)
    user.type = ["actionrunner_basic"]

    result = execute_stored_action(
        "add_label",
        "howler.id:*",
        user=user,
        category="generic",
        label="",
        obsolete_argument="from an older action",
    )

    assert len(result) == 1
    assert result[0]["title"] == "Invalid Arguments"
    assert "label" in result[0]["message"]
    mock_execute.assert_not_called()
    mock_datastore.assert_not_called()


@patch("howler.actions.datastore")
@patch("howler.actions.add_label.execute")
def test_execute_user_arguments_cannot_enable_compatibility_mode(mock_execute, mock_datastore):
    user: User = random_model_obj(User)
    user.type = ["actionrunner_basic"]

    result = execute(
        "add_label",
        "howler.id:*",
        user=user,
        category="generic",
        label="kept",
        ignore_extra_arguments=True,
        obsolete_argument="from an older action",
    )

    assert len(result) == 1
    assert result[0]["title"] == "Invalid Arguments"
    assert "ignore_extra_arguments" in result[0]["message"]
    assert "obsolete_argument" in result[0]["message"]
    mock_execute.assert_not_called()
    mock_datastore.assert_not_called()


@patch("howler.actions.transition.datastore")
@patch("howler.actions.datastore")
@patch("howler.actions.transition.hit_service.transition_hit")
def test_execute_stored_transition_preserves_escalation(
    mock_transition_hit,
    mock_action_datastore,
    mock_transition_datastore,
):
    user: User = random_model_obj(User)
    user.type = ["admin"]
    hit_id = "stored-transition-hit"
    mock_action_datastore.return_value.hit.search.return_value = {"total": 1}
    mock_transition_datastore.return_value.hit.search.side_effect = [
        {"total": 1, "items": [SimpleNamespace(howler=SimpleNamespace(id=hit_id))]},
        {"total": 0},
    ]

    result = execute_stored_action(
        "transition",
        "howler.id:*",
        user=user,
        status="in-progress",
        transition="demote",
        escalation="alert",
    )

    assert result[0]["outcome"] == "success"
    mock_transition_hit.assert_called_once_with(hit_id, HitStatusTransition.DEMOTE, user, escalation="alert")


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


@patch("howler.actions.add_label.execute")
@patch("howler.actions.datastore")
def test_execute_admin_user_bypasses_role_check_and_gets_advanced_limit(mock_ds, mock_add_label_execute):
    """Test that admin users bypass role checks and get the advanced hit limit."""
    admin_user: User = random_model_obj(User)
    admin_user.type = ["admin", "user"]  # Admin without explicit actionrunner roles

    # Isolate execute() role/limit behavior from add_label's own datastore interactions.
    mock_add_label_execute.return_value = [
        {
            "query": "howler.id:*",
            "outcome": "success",
            "title": "Executed Successfully",
            "message": "ok",
        }
    ]

    # Mock datastore to return a hit count that exceeds basic (20) but not advanced (1000)
    mock_ds.return_value.hit.search.return_value = {"total": 500, "items": []}
    mock_ds.return_value.hit.update_by_query.return_value = None

    result = execute("add_label", "howler.id:*", user=admin_user, category="generic", label="test")

    # Admin should bypass role check and use advanced limit, so 500 hits should be allowed
    assert all(r["title"] != "Insufficient permissions" for r in result)
    assert all(r["title"] != "Hit limit exceeded" for r in result)


@patch("howler.actions.add_label.execute")
@patch("howler.actions.datastore")
def test_execute_user_with_both_basic_and_advanced_roles(mock_ds, mock_add_label_execute):
    """Test that users with both basic and advanced roles get the higher (advanced) limit."""
    mixed_user: User = random_model_obj(User)
    mixed_user.type = ["user", "actionrunner_basic", "actionrunner_advanced"]

    # Isolate execute() role/limit behavior from add_label's own datastore interactions.
    mock_add_label_execute.return_value = [
        {
            "query": "howler.id:*",
            "outcome": "success",
            "title": "Executed Successfully",
            "message": "ok",
        }
    ]

    # Mock datastore to return a hit count that exceeds basic (20) but not advanced (1000)
    mock_ds.return_value.hit.search.return_value = {"total": 50, "items": []}
    mock_ds.return_value.hit.update_by_query.return_value = None

    result = execute("add_label", "howler.id:*", user=mixed_user, category="generic", label="test")

    # Should use advanced limit, so 50 hits should be allowed
    assert all(r["title"] != "Hit limit exceeded" for r in result)
