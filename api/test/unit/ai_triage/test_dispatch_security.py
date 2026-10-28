from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from howler import actions
from howler.actions import ai_triage

from .support import make_user


@pytest.fixture
def operation(monkeypatch):
    execute = Mock(return_value=[{"query": "*:*", "outcome": "success", "title": "Queued", "message": "Queued"}])
    spec = {"roles": ["actionrunner_basic"], "requires_auth_token": True}
    monkeypatch.setattr(
        actions,
        "_get_operation",
        lambda _operation_id: SimpleNamespace(SKIP_CENTRAL_LIMIT=True, specification=lambda: spec, execute=execute),
    )
    return execute


def test_dispatch_overrides_persisted_auth_token_with_request_bearer(operation):
    result = actions.execute(
        "requires_auth",
        "*:*",
        make_user(),
        bearer_token="request-token",
        auth_token="persisted-token",
    )

    assert result[0]["outcome"] == "success"
    operation.assert_called_once()
    assert operation.call_args.kwargs["auth_token"] == "request-token"
    assert "bearer_token" not in operation.call_args.kwargs


def test_dispatch_only_forwards_bearer_to_operations_that_require_it(monkeypatch):
    execute = Mock(return_value=[])
    spec = {"roles": ["actionrunner_basic"]}
    monkeypatch.setattr(
        actions,
        "_get_operation",
        lambda _operation_id: SimpleNamespace(SKIP_CENTRAL_LIMIT=True, specification=lambda: spec, execute=execute),
    )

    actions.execute("ordinary", "*:*", make_user(), bearer_token="request-token")

    assert "auth_token" not in execute.call_args.kwargs
    assert "bearer_token" not in execute.call_args.kwargs


def test_missing_bearer_returns_the_ai_operation_error_report(monkeypatch):
    execute = Mock(wraps=ai_triage.execute)
    monkeypatch.setattr(ai_triage, "is_available", lambda: True)
    monkeypatch.setattr(ai_triage, "execute", execute)
    monkeypatch.setattr(actions, "_get_operation", lambda _operation_id: ai_triage)

    result = actions.execute("ai_triage", "*:*", make_user(), bearer_token=None)

    assert result == [
        {
            "query": "(*:*)",
            "outcome": "error",
            "title": "Authentication required",
            "message": "AI triage requires a Bearer authorization token.",
        }
    ]
    assert execute.call_args.kwargs["auth_token"] is None
