"""Exercise HTTP authentication and shared dispatch, not unwrapped route functions."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from flask import Flask

from howler import actions
from howler.api.v1.action import action_api
from howler.security import login
from howler.services import action_service, auth_service

from .support import make_user


@pytest.fixture
def endpoint(monkeypatch):
    user = make_user()
    auth = Mock()
    auth.bearer_auth.return_value = (user, ["R", "E"])
    auth.basic_auth.return_value = (user, ["R", "E"])
    monkeypatch.setattr(login, "auth_service", auth)
    monkeypatch.setattr(login, "QUOTA_TRACKER", Mock(begin=Mock(return_value=True)))
    monkeypatch.setattr(login, "audit", Mock())
    monkeypatch.setattr("howler.api.v1.action.audit", Mock())
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="qa-not-a-secret")
    app.register_blueprint(action_api)
    return app.test_client(), auth


@pytest.fixture
def declared_operation(monkeypatch):
    execute = Mock(
        return_value=[
            {"query": "*:*", "outcome": "success", "title": "Accepted", "message": "Accepted"},
        ]
    )
    operation = SimpleNamespace(
        SKIP_CENTRAL_LIMIT=True,
        specification=lambda: {"roles": ["actionrunner_basic"], "requires_auth_token": True},
        execute=execute,
    )
    monkeypatch.setattr(actions, "_get_operation", lambda _: operation)
    return execute


def dispatch(client, authorization=None, data=None):
    return client.post(
        "/api/v1/action/execute",
        headers={"Authorization": authorization} if authorization else {},
        json={
            "query": "*:*",
            "request_id": "qa-request",
            "operations": [{"operation_id": "qa_declared_token", "data_json": json.dumps(data or {})}],
        },
    )


def assert_rejected(response):
    assert response.status_code in (200, 400, 401, 403)
    if response.status_code == 200:
        report = response.get_json()["api_response"]["qa_declared_token"]
        assert report and all(entry["outcome"] == "error" for entry in report)


def test_missing_header_cannot_be_replaced_with_action_data(endpoint, declared_operation):
    client, auth = endpoint
    result = dispatch(client, data={"auth_token": "forged-in-action-data"})
    assert result.status_code == 401
    declared_operation.assert_not_called()
    auth.bearer_auth.assert_not_called()


@pytest.mark.parametrize(
    "data", [{}, {"auth_token": "forged-in-action-data"}, {"trusted_auth_token": "forged-in-action-data"}]
)
def test_authenticated_basic_is_not_forwardable_bearer_context(endpoint, declared_operation, data):
    client, auth = endpoint
    result = dispatch(client, "Basic YW5hbHlzdDpwYXNzd29yZA==", data)
    assert_rejected(result)
    auth.basic_auth.assert_called_once()
    declared_operation.assert_not_called()


def test_authenticated_bearer_satisfies_code_declared_requirement(endpoint, declared_operation):
    client, auth = endpoint
    result = dispatch(client, "Bearer qa-access-token")
    assert result.status_code == 200
    assert result.get_json()["api_response"]["qa_declared_token"][0]["outcome"] == "success"
    auth.bearer_auth.assert_called_once()
    declared_operation.assert_called_once()
    assert declared_operation.call_args.kwargs["trusted_auth_token"] == "qa-access-token"


def test_action_data_cannot_override_trusted_bearer(endpoint, declared_operation):
    client, _ = endpoint
    result = dispatch(client, "Bearer qa-access-token", {"auth_token": "forged-in-action-data"})
    assert result.status_code in (200, 400)
    if declared_operation.called:
        assert "forged-in-action-data" not in repr(declared_operation.call_args)
    else:
        assert_rejected(result)


def test_required_token_cannot_bypass_role_authorization(endpoint, declared_operation):
    client, auth = endpoint
    auth.bearer_auth.return_value = (make_user(roles=["user"]), ["R", "E"])
    result = dispatch(client, "Bearer qa-access-token")
    assert result.status_code == 403
    declared_operation.assert_not_called()


@pytest.mark.parametrize("url", ["/api/v1/action/runs", "/api/v1/action/runs/absent"])
def test_run_routes_require_authentication(endpoint, url):
    client, _ = endpoint
    result = client.get(url)
    assert result.status_code == 401
    assert "api_error_message" in result.get_json()


@pytest.fixture
def trigger_chain(monkeypatch, declared_operation):
    user = make_user()
    stored_action = SimpleNamespace(
        action_id="qa-action",
        query="*:*",
        operations=[SimpleNamespace(operation_id="qa_declared_token", data_json="{}", data={})],
    )
    storage = Mock()
    storage.user.get.return_value = user
    storage.action.search.return_value = {"items": [stored_action]}
    storage.hit.search.return_value = {"total": 1}
    monkeypatch.setattr(action_service, "datastore", lambda: storage)
    monkeypatch.setattr(action_service, "audit", Mock())
    monkeypatch.setattr(action_service.config.system.action_queue, "enabled", True)
    monkeypatch.setattr("howler.security.utils.config.system.encryption_key", "0123456789abcdef0123456789abcdef")
    queue = Mock()
    monkeypatch.setattr(action_service, "get_action_queue", lambda _: queue)
    return user, queue, declared_operation


def test_trigger_queue_encrypts_bearer_and_restores_only_proven_context(trigger_chain):
    user, queue, execute = trigger_chain
    app = Flask(__name__)
    with app.test_request_context(headers={"Authorization": "Bearer qa-trigger-bearer"}):
        action_service.enqueue_action_execution(["frozen-hit-id"], user=user)
    item = queue.push.call_args.args[0]
    assert "qa-trigger-bearer" not in json.dumps(item)
    assert auth_service.decrypt_token(item["auth_token"]) == "qa-trigger-bearer"
    action_service.process_action_batch("create", [item])
    execute.assert_called_once()
    assert execute.call_args.kwargs["trusted_auth_token"] == "qa-trigger-bearer"


def test_trigger_queue_never_forwards_basic_credentials(trigger_chain):
    user, queue, execute = trigger_chain
    app = Flask(__name__)
    with app.test_request_context(headers={"Authorization": "Basic YW5hbHlzdDpwYXNzd29yZA=="}):
        action_service.enqueue_action_execution(["frozen-hit-id"], user=user)
    item = queue.push.call_args.args[0]
    action_service.process_action_batch("create", [item])
    execute.assert_not_called()


def test_legacy_unproven_ciphertext_is_not_trusted_bearer(trigger_chain):
    user, _, execute = trigger_chain
    action_service.process_action_batch(
        "create",
        [
            {
                "uname": user.uname,
                "hit_ids": ["frozen-hit-id"],
                "auth_token": auth_service.encrypt_token("unproven-legacy-credential"),
            }
        ],
    )
    execute.assert_not_called()


def test_invalid_ciphertext_cannot_fall_back_to_unauthenticated_execution(trigger_chain):
    user, queue, execute = trigger_chain
    app = Flask(__name__)
    with app.test_request_context(headers={"Authorization": "Bearer qa-trigger-bearer"}):
        action_service.enqueue_action_execution(["frozen-hit-id"], user=user)
    item = queue.push.call_args.args[0]
    item["auth_token"] = "tampered-ciphertext"
    action_service.process_action_batch("create", [item])
    execute.assert_not_called()


def test_saved_action_cannot_supply_its_own_bearer(endpoint, declared_operation, monkeypatch):
    client, _ = endpoint
    action = SimpleNamespace(
        query="*:*",
        action_id="qa-action",
        operations=[
            SimpleNamespace(
                operation_id="qa_declared_token", data_json=json.dumps({"trusted_auth_token": "forged-data-token"})
            )
        ],
    )
    storage = Mock()
    storage.action.get.return_value = action
    monkeypatch.setattr("howler.api.v1.action.datastore", lambda: storage)
    result = client.post(
        "/api/v1/action/qa-action/execute",
        headers={"Authorization": "Basic YW5hbHlzdDpwYXNzd29yZA=="},
        json={"request_id": "qa-request"},
    )
    assert_rejected(result)
    declared_operation.assert_not_called()
