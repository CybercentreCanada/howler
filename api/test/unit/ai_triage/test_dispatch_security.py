import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from flask import Flask

from howler import actions
from howler.api.v1.action import action_api
from howler.security import login
from howler.services import action_service

from .support import make_user


@pytest.fixture
def endpoint(monkeypatch):
    user = make_user()
    auth = Mock()
    auth.bearer_auth.return_value = (user, ["R", "E"])
    monkeypatch.setattr(login, "auth_service", auth)
    monkeypatch.setattr(login, "QUOTA_TRACKER", Mock(begin=Mock(return_value=True)))
    monkeypatch.setattr(login, "audit", Mock())
    monkeypatch.setattr("howler.api.v1.action.audit", Mock())
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="test-key")
    app.register_blueprint(action_api)
    return app.test_client(), auth


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


def dispatch(client, authorization=None, data=None):
    headers = {"Authorization": authorization} if authorization else {}
    return client.post(
        "/api/v1/action/execute",
        headers=headers,
        json={
            "query": "*:*",
            "request_id": "request-1",
            "operations": [{"operation_id": "ai_triage", "data_json": json.dumps(data or {})}],
        },
    )


def test_action_data_cannot_supply_or_replace_trusted_bearer(endpoint, operation):
    client, auth = endpoint

    response = dispatch(client, "Bearer real-token", {"auth_token": "forged-token", "prompt": "Direct prompt"})

    assert response.status_code == 200
    operation.assert_called_once()
    assert operation.call_args.kwargs["trusted_auth_token"] == "real-token"
    assert operation.call_args.kwargs["prompt"] == "Direct prompt"
    assert "forged-token" not in repr(operation.call_args)
    auth.bearer_auth.assert_called_once()
    assert auth.bearer_auth.call_args.args == ("real-token",)


def test_missing_header_cannot_be_replaced_with_action_data(endpoint, operation):
    client, auth = endpoint

    response = dispatch(client, data={"auth_token": "forged-token"})

    assert response.status_code == 401
    operation.assert_not_called()
    auth.bearer_auth.assert_not_called()


def test_saved_triggered_action_preserves_optional_prompt_and_trusted_token(monkeypatch):
    user = make_user()
    saved_action = SimpleNamespace(
        action_id="action-1",
        query="*:*",
        operations=[
            SimpleNamespace(
                operation_id="ai_triage",
                data_json=json.dumps({"prompt": "Saved prompt", "trusted_auth_token": "forged-token"}),
                data={},
            )
        ],
    )
    storage = Mock()
    storage.action.search.return_value = {"items": [saved_action]}
    storage.hit.search.return_value = {"total": 1}
    execute = Mock(return_value=[])
    monkeypatch.setattr(action_service, "datastore", lambda: storage)
    monkeypatch.setattr(action_service, "audit", Mock())
    monkeypatch.setattr(actions, "execute", execute)

    action_service.bulk_execute_on_query("*:*", trigger="create", user=user, auth_token="real-token")

    execute.assert_called_once()
    assert execute.call_args.kwargs["prompt"] == "Saved prompt"
    assert execute.call_args.kwargs["trusted_auth_token"] == "real-token"
    assert execute.call_args.kwargs["trigger"] == "create"
    assert "forged-token" not in repr(execute.call_args)
