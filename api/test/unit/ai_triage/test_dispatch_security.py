from types import ModuleType
from unittest.mock import Mock

import pytest
from flask import Flask
from pydantic import ValidationError

from howler import actions
from howler.actions import ai_triage
from howler.actions.models import ActionDescription, ActionSpecification
from howler.config import CLASSIFICATION

from .support import make_user


def test_ai_specification_preserves_optional_prompt_for_ui_and_validation():
    specification = ai_triage.specification()
    serialized = specification.to_ui_dict()
    step = serialized["steps"][0]

    assert isinstance(specification, ActionSpecification)
    assert serialized["requires_auth_token"] is True
    assert serialized["i18nKey"] == "operations.ai_triage"
    assert step["args"] == {}
    assert step["optional_args"] == ["prompt"]
    assert specification.validate_arguments({}).model_dump(exclude_unset=True) == {}
    assert specification.validate_arguments({"prompt": "Investigate"}).prompt == "Investigate"
    assert specification.validate_arguments({"prompt": None}).prompt is None
    with pytest.raises(ValidationError):
        specification.validate_arguments({"prompt": 123})
    with pytest.raises(ValidationError):
        specification.validate_arguments({"unexpected": "value"})


def test_dispatch_rejects_non_string_prompt(monkeypatch):
    execute = Mock()
    monkeypatch.setattr(ai_triage, "execute", execute)
    monkeypatch.setattr(actions, "_get_operation", lambda _operation_id: ai_triage)

    result = actions.execute("ai_triage", "*:*", make_user(), auth_token="token", prompt=123)

    assert result[0]["title"] == "Invalid Arguments"
    execute.assert_not_called()


@pytest.fixture
def operation(monkeypatch):
    execute = Mock(return_value=[{"query": "*:*", "outcome": "success", "title": "Queued", "message": "Queued"}])
    operation = ModuleType("requires_auth")
    operation.SKIP_CENTRAL_LIMIT = True
    operation.specification = lambda: ActionSpecification(
        id="requires_auth",
        title="Requires auth",
        description=ActionDescription(short="Test operation"),
        roles=["actionrunner_basic"],
        requires_auth_token=True,
    )
    operation.execute = execute
    monkeypatch.setattr(actions, "_get_operation", lambda _operation_id: operation)
    return execute


def test_background_dispatch_uses_explicit_auth_token(operation):
    result = actions.execute(
        "requires_auth",
        "*:*",
        make_user(),
        auth_token="queued-token",
    )

    assert result[0]["outcome"] == "success"
    operation.assert_called_once()
    assert operation.call_args.kwargs["auth_token"] == "queued-token"
    assert "bearer_token" not in operation.call_args.kwargs


def test_background_dispatch_without_auth_token(operation):
    actions.execute("requires_auth", "*:*", make_user())

    assert operation.call_args.kwargs["auth_token"] is None


@pytest.mark.parametrize(
    ("authorization", "expected"),
    [("Bearer request-token", "request-token"), ("Basic dXNlcjpwYXNz", None), (None, None)],
)
def test_http_dispatch_ignores_credentials_in_operation_data(operation, authorization, expected):
    headers = {"Authorization": authorization} if authorization else {}
    with Flask(__name__).test_request_context(headers=headers):
        actions.execute("requires_auth", "*:*", make_user(), auth_token="spoofed-token")

    assert operation.call_args.kwargs["auth_token"] == expected


def test_dispatch_only_forwards_auth_token_to_operations_that_require_it(monkeypatch):
    execute = Mock(return_value=[])
    operation = ModuleType("ordinary")
    operation.SKIP_CENTRAL_LIMIT = True
    operation.specification = lambda: ActionSpecification(
        id="ordinary",
        title="Ordinary",
        description=ActionDescription(short="Test operation"),
        roles=["actionrunner_basic"],
    )
    operation.execute = execute
    monkeypatch.setattr(actions, "_get_operation", lambda _operation_id: operation)

    actions.execute("ordinary", "*:*", make_user(), auth_token="queued-token")

    assert "auth_token" not in execute.call_args.kwargs
    assert "bearer_token" not in execute.call_args.kwargs


def test_missing_auth_token_returns_the_ai_operation_error_report(monkeypatch):
    execute = Mock(wraps=ai_triage.execute)
    enqueue = Mock()
    monkeypatch.setattr(ai_triage, "is_available", lambda: True)
    monkeypatch.setattr(CLASSIFICATION, "enforce", False)
    monkeypatch.setattr(ai_triage, "execute", execute)
    monkeypatch.setattr("howler.services.ai_service.enqueue_alerts", enqueue)
    monkeypatch.setattr(actions, "_get_operation", lambda _operation_id: ai_triage)

    result = actions.execute("ai_triage", "*:*", make_user(), auth_token=None)

    assert result == [
        {
            "query": "(*:*)",
            "outcome": "error",
            "title": "Authentication required",
            "message": "AI triage requires a Bearer authorization token.",
        }
    ]
    assert execute.call_args.kwargs["auth_token"] is None
    enqueue.assert_not_called()
