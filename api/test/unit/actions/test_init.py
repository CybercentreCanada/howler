import os
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Annotated, Literal
from unittest.mock import patch

import pytest
from pydantic import Field, ValidationError

from howler.actions import _load_specification, ai_triage, execute, specifications
from howler.actions.models import DISPATCHER_ARGUMENTS, ActionArguments, ActionSpecification, ActionStep
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

    # The example action is excluded, and locally unavailable actions are not advertised.
    expected_ids = {f.stem for f in files if f.stem != "example_plugin"}
    if not ai_triage.is_available():
        expected_ids.discard(ai_triage.OPERATION_ID)

    assert {data["id"] for data in result} == expected_ids


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
@patch("howler.actions.add_label.execute")
def test_execute_rejects_extra_arguments(mock_execute, mock_datastore):
    user: User = random_model_obj(User)
    user.type = ["actionrunner_basic"]

    for extra_kwargs, expected_message in [
        ({"===": "unexpected"}, "===: Extra inputs are not permitted (received 'unexpected')"),
        ({"arguments": 42}, "arguments: Extra inputs are not permitted (received 42)"),
    ]:
        result = execute(
            "add_label",
            "howler.id:*",
            user=user,
            category="generic",
            label="test",
            **extra_kwargs,
        )
        assert result == [
            {
                "query": "(howler.id:*)",
                "outcome": "error",
                "title": "Invalid Arguments",
                "message": expected_message,
            }
        ]

    mock_execute.assert_not_called()
    mock_datastore.assert_not_called()


@pytest.mark.parametrize(
    ("transition_name", "extra_kwargs", "expected_escalation"),
    [
        ("demote", {"escalation": "alert"}, "alert"),
        ("promote", {"escalation": ""}, "alert"),
        ("demote", {"escalation": None}, "hit"),
    ],
)
@patch("howler.actions.transition.datastore")
@patch("howler.actions.datastore")
@patch("howler.actions.transition.hit_service.transition_hit")
def test_execute_transition_escalation_handling(
    mock_transition_hit,
    mock_action_datastore,
    mock_transition_datastore,
    transition_name,
    extra_kwargs,
    expected_escalation,
):
    user: User = random_model_obj(User)
    user.type = ["admin"]
    hit_id = "stored-transition-hit"
    mock_action_datastore.return_value.hit.search.return_value = {"total": 1}
    mock_transition_datastore.return_value.hit.search.side_effect = [
        {"total": 1, "items": [SimpleNamespace(howler=SimpleNamespace(id=hit_id))]},
        {"total": 0},
    ]

    result = execute(
        "transition",
        "howler.id:*",
        user=user,
        status="in-progress",
        transition=transition_name,
        **extra_kwargs,
    )

    assert result[0]["outcome"] == "success"
    mock_transition_hit.assert_called_once_with(
        hit_id,
        HitStatusTransition(transition_name),
        user,
        escalation=expected_escalation,
    )


@patch("howler.actions.datastore")
@patch("howler.actions.add_label.execute")
def test_execute_forwards_auth_token_separately_from_validated_arguments(mock_execute, mock_datastore):
    user: User = random_model_obj(User)
    user.type = ["actionrunner_basic"]
    mock_execute.return_value = []
    mock_datastore.return_value.hit.search.return_value = {"total": 1}

    result = execute(
        "add_label",
        "howler.id:*",
        user=user,
        category="generic",
        label="kept",
        auth_token="plugin-token",
    )

    assert result == []
    mock_execute.assert_called_once_with(
        query="howler.id:*",
        request_id=None,
        user=user,
        category="generic",
        label="kept",
        auth_token="plugin-token",
    )


def test_legacy_specification_loads_warns_once_and_forbids_extras(caplog):
    legacy_module = ModuleType("legacy_plugin_op")
    legacy_module.OPERATION_ID = "legacy_plugin_op"  # type: ignore[attr-defined]
    legacy_module.specification = lambda: {  # type: ignore[attr-defined]
        "id": "legacy_plugin_op",
        "title": "Legacy",
        "description": {"short": "Legacy plugin operation"},
        "roles": ["admin"],
        "steps": [
            {"args": {}, "options": {}, "validation": {}},
            {"args": {"plugin_value": [], "conditional_value": ["plugin_value:enabled"]}},
        ],
    }

    specification = _load_specification(legacy_module)
    assert _load_specification(legacy_module) is specification
    assert caplog.text.count("legacy_plugin_op returns a dict specification") == 1
    assert set(specification.arguments.model_fields) == {"plugin_value", "conditional_value"}
    assert specification.validate_arguments({"plugin_value": "enabled"}).model_dump(exclude_unset=True) == {
        "plugin_value": "enabled"
    }

    for extra_key in ("undeclared", *sorted(DISPATCHER_ARGUMENTS)):
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            specification.validate_arguments({"plugin_value": "enabled", extra_key: "not permitted"})


@pytest.mark.parametrize("model_options", [{}, {"arguments": None}, {"arguments": ActionArguments}])
def test_argument_free_specification(model_options):
    specification = ActionSpecification.model_validate(
        {
            "id": "no-arguments",
            "title": "No arguments",
            "description": {"short": "Operation without arguments"},
            "roles": ["admin"],
            **model_options,
        }
    )

    assert specification.arguments is ActionArguments
    assert specification.validate_arguments({}).model_dump() == {}
    assert specification.to_ui_dict()["steps"] == []
    assert "arguments" not in specification.to_ui_dict()

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        specification.validate_arguments({"unexpected": "not permitted"})


def test_specification_model_invariants():
    for reserved in sorted(DISPATCHER_ARGUMENTS):
        with pytest.raises(ValidationError, match="declares reserved argument"):
            ActionSpecification.from_legacy(
                {
                    "id": "legacy",
                    "title": "Legacy",
                    "description": {"short": "Legacy"},
                    "roles": ["admin"],
                    "steps": [{"args": {reserved: []}}],
                }
            )

    with pytest.raises(ValidationError, match="Step argument\\(s\\) missing from the arguments model"):
        ActionSpecification.model_validate(
            {
                "id": "missing-model",
                "title": "Missing model",
                "description": {"short": "Step requires an argument model"},
                "roles": ["admin"],
                "steps": [{"args": {"value": []}}],
            }
        )

    class HiddenArguments(ActionArguments):
        hidden: str

    with pytest.raises(ValidationError, match="not included in any step"):
        ActionSpecification(
            id="hidden-arg",
            title="Hidden arg",
            description={"short": "Hidden arg"},
            roles=["admin"],
            arguments=HiddenArguments,
        )

    with pytest.raises(ValidationError, match="Options are provided for 'other'"):
        ActionStep(args={"count": []}, options={"other": ["1"]})


@pytest.mark.parametrize(
    ("conditions", "options", "error"),
    [
        (["mode:enabled"], ["1", "2"], None),
        (["mode:enabled"], {"mode:enabled": ["1"]}, None),
        (["mode"], [], "must be in the form"),
        (["unknown:enabled"], [], "must be in the form"),
        (["mode:invalid"], [], "'invalid' is offered for 'mode' but is invalid"),
        (["count:0"], [], "'0' is offered for 'count' but is invalid"),
        ([], ["0"], "'0' is offered for 'count' but is invalid"),
        ([], {"unknown:enabled": ["1"]}, "must be in the form"),
        ([], {"mode:invalid": ["1"]}, "'invalid' is offered for 'mode' but is invalid"),
        ([], {"mode:enabled": ["0"]}, "'0' is offered for 'count' but is invalid"),
    ],
)
def test_action_step_validates_against_specification_arguments(conditions, options, error):
    class StepArguments(ActionArguments):
        mode: Literal["enabled", "disabled"]
        count: Annotated[int, Field(gt=0)]

    step = {"args": {"count": conditions}, "options": {"count": options}}
    specification = {
        "id": "step-validation",
        "title": "Step validation",
        "description": {"short": "Validate action steps"},
        "roles": ["admin"],
        "arguments": StepArguments,
        "steps": [{"args": {"mode": []}}, step],
    }

    if error is not None:
        with pytest.raises(ValidationError, match=error):
            ActionSpecification.model_validate(specification)
    else:
        result = ActionSpecification.model_validate(specification)
        assert result.to_ui_dict()["steps"][1] == step


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
