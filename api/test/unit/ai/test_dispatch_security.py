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


def make_operation(monkeypatch, requires_auth_token):
    execute = Mock(return_value=[])
    operation = ModuleType("operation")
    operation.SKIP_CENTRAL_LIMIT = True
    operation.execute = execute
    operation.specification = lambda: ActionSpecification(
        id="operation",
        title="Operation",
        description=ActionDescription(short="Test operation"),
        roles=["actionrunner_basic"],
        requires_auth_token=requires_auth_token,
    )
    monkeypatch.setattr(actions, "_get_operation", lambda _operation_id: operation)
    return execute


def test_ai_specification_declares_optional_prompt():
    specification = ai_triage.specification()
    serialized = specification.to_ui_dict()
    step = serialized["steps"][0]

    assert serialized["requires_auth_token"] is True
    assert (step["args"], step["optional_args"]) == ({}, ["prompt"])
    assert specification.validate_arguments({}).model_dump(exclude_unset=True) == {}
    assert specification.validate_arguments({"prompt": "Investigate"}).prompt == "Investigate"
    for invalid in ({"prompt": 123}, {"unexpected": "value"}):
        with pytest.raises(ValidationError):
            specification.validate_arguments(invalid)


def test_dispatch_rejects_non_string_prompt(monkeypatch):
    execute = Mock()
    monkeypatch.setattr(ai_triage, "execute", execute)
    monkeypatch.setattr(actions, "_get_operation", lambda _operation_id: ai_triage)

    result = actions.execute("ai_triage", "*:*", make_user(), auth_token="token", prompt=123)

    assert result[0]["title"] == "Invalid Arguments"
    execute.assert_not_called()


@pytest.mark.parametrize(
    ("authorization", "expected"),
    [("Bearer request-token", "request-token"), ("Basic dXNlcjpwYXNz", None), (None, None)],
)
def test_http_dispatch_ignores_credentials_in_operation_data(monkeypatch, authorization, expected):
    execute = make_operation(monkeypatch, requires_auth_token=True)
    headers = {"Authorization": authorization} if authorization else {}

    with Flask(__name__).test_request_context(headers=headers):
        actions.execute("operation", "*:*", make_user(), auth_token="spoofed-token")

    assert execute.call_args.kwargs["auth_token"] == expected


@pytest.mark.parametrize(
    ("requires_auth_token", "passed", "expected"),
    [(True, "queued-token", "queued-token"), (True, None, None), (False, "queued-token", "absent")],
)
def test_background_dispatch_forwards_explicit_token_only_to_operations_that_need_it(
    monkeypatch, requires_auth_token, passed, expected
):
    execute = make_operation(monkeypatch, requires_auth_token)

    actions.execute("operation", "*:*", make_user(), auth_token=passed)

    assert execute.call_args.kwargs.get("auth_token", "absent") == expected
    assert "bearer_token" not in execute.call_args.kwargs


def test_missing_auth_token_returns_the_ai_operation_error_report(monkeypatch):
    enqueue = Mock()
    monkeypatch.setattr(ai_triage, "is_available", lambda: True)
    monkeypatch.setattr(CLASSIFICATION, "enforce", False)
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
    enqueue.assert_not_called()
