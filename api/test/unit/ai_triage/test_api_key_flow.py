from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import jwt
import pytest
from flask import Flask

from howler import actions
from howler.actions import ai_triage
from howler.config import CLASSIFICATION, config
from howler.cronjobs import ai_triage_worker
from howler.odm.models.config import AITriage
from howler.services import action_service, ai_service, auth_service, hit_service, user_service

from .support import make_hit, make_user


@pytest.mark.parametrize("authorization", ["Basic dXNlcjpwYXNz", "Basic dXNlcjprZXk6c2VjcmV0", "Bearer incoming-token"])
def test_dispatch_and_worker_use_provider_key_without_queueing_credentials(monkeypatch, authorization):
    settings = AITriage(enabled=True, endpoint="https://ai.invalid/chat", model="model", api_key="provider-secret")
    monkeypatch.setattr(config.core, "ai", settings)
    monkeypatch.setattr(config.system, "encryption_key", None)
    monkeypatch.setattr(CLASSIFICATION, "enforce", False)
    monkeypatch.setattr(actions, "_get_operation", lambda _operation_id: ai_triage)
    monkeypatch.setattr(ai_service, "_eligible_targets", lambda *_args: ["hit-1"])
    queue = Mock()
    monkeypatch.setattr(ai_service, "get_queue", lambda: queue)
    encrypt = Mock()
    decrypt = Mock()
    monkeypatch.setattr(auth_service, "encrypt_token", encrypt)
    monkeypatch.setattr(auth_service, "decrypt_token", decrypt)

    user = make_user()
    hit = make_hit(id="hit-1")
    monkeypatch.setattr(user_service, "get_user", Mock(return_value=user))
    monkeypatch.setattr(hit_service, "get_hit", Mock(return_value=(hit, "version")))
    save = Mock(return_value=True)
    monkeypatch.setattr(ai_service, "save_ai_lead", save)
    session = MagicMock()
    session.__enter__.return_value = session
    response = session.post.return_value.__enter__.return_value
    response.json.return_value = {"choices": [{"message": {"content": "generated opinion"}}]}
    monkeypatch.setattr(ai_service.requests, "Session", Mock(return_value=session))

    with Flask(__name__).test_request_context(headers={"Authorization": authorization}):
        report = actions.execute("ai_triage", "*:*", user)

    assert report[0]["outcome"] == "success"
    job = queue.push.call_args.args[0]
    assert job["bearer_token"] is None
    assert "provider-secret" not in repr(job)
    assert "incoming-token" not in repr(job)
    encrypt.assert_not_called()

    ai_triage_worker._process(job)

    decrypt.assert_not_called()
    assert session.post.call_args.kwargs["headers"]["Authorization"] == "Bearer provider-secret"
    save.assert_called_once_with("hit-1", user, "generated opinion")


def test_worker_discards_key_backed_job_if_key_was_removed(monkeypatch, caplog):
    settings = AITriage(enabled=True, endpoint="https://ai.invalid/chat", model="model")
    monkeypatch.setattr(config.core, "ai", settings)
    monkeypatch.setattr(user_service, "get_user", Mock(return_value=make_user()))
    monkeypatch.setattr(hit_service, "get_hit", Mock(return_value=(make_hit(), "version")))
    save = Mock()
    session = Mock()
    monkeypatch.setattr(ai_service, "save_ai_lead", save)
    monkeypatch.setattr(ai_service.requests, "Session", session)

    ai_triage_worker._process({"hit_id": "hit-1", "uname": "analyst", "bearer_token": None, "prompt": None})

    assert "requires a provider credential" in caplog.text
    session.assert_not_called()
    save.assert_not_called()


def test_basic_request_without_provider_key_is_rejected(monkeypatch):
    settings = AITriage(enabled=True, endpoint="https://ai.invalid/chat", model="model")
    monkeypatch.setattr(config.core, "ai", settings)
    monkeypatch.setattr(config.system, "encryption_key", "0123456789abcdef0123456789abcdef")
    monkeypatch.setattr(CLASSIFICATION, "enforce", False)
    monkeypatch.setattr(actions, "_get_operation", lambda _operation_id: ai_triage)
    queue = Mock()
    monkeypatch.setattr(ai_service, "get_queue", lambda: queue)

    with Flask(__name__).test_request_context(headers={"Authorization": "Basic dXNlcjpwYXNz"}):
        report = actions.execute("ai_triage", "*:*", make_user())

    assert report[0]["title"] == "Authentication required"
    queue.push.assert_not_called()


def test_provider_key_does_not_bypass_action_permissions(monkeypatch):
    settings = AITriage(enabled=True, endpoint="https://ai.invalid/chat", model="model", api_key="provider-secret")
    monkeypatch.setattr(config.core, "ai", settings)
    monkeypatch.setattr(actions, "_get_operation", lambda _operation_id: ai_triage)
    queue = Mock()
    monkeypatch.setattr(ai_service, "get_queue", lambda: queue)
    user = make_user()
    user.type = ["user"]

    assert actions.execute("ai_triage", "*:*", None)[0]["title"] == "Authentication required"
    assert actions.execute("ai_triage", "*:*", user)[0]["title"] == "Insufficient permissions"
    queue.push.assert_not_called()


@pytest.mark.parametrize(
    ("data_json", "should_enqueue"),
    [("{}", True), ('{"auth_token":"persisted-token"}', False)],
)
def test_triggered_action_uses_decrypted_token_without_request_context(monkeypatch, data_json, should_enqueue):
    settings = AITriage(enabled=True, endpoint="https://ai.invalid/chat", model="model")
    monkeypatch.setattr(config.core, "ai", settings)
    monkeypatch.setattr(config.system, "encryption_key", "0123456789abcdef0123456789abcdef")
    monkeypatch.setattr(CLASSIFICATION, "enforce", False)
    monkeypatch.setattr(action_service, "audit", Mock())
    monkeypatch.setattr(ai_service, "_eligible_targets", lambda *_args: ["hit-1"])
    queue = Mock()
    monkeypatch.setattr(ai_service, "get_queue", lambda: queue)
    user = make_user()
    operation = SimpleNamespace(operation_id="ai_triage", data_json=data_json, data={})
    action = SimpleNamespace(action_id="action-id", query="*:*", operations=[operation])
    storage = Mock()
    storage.user.get.return_value = user
    storage.action.search.return_value = {"items": [action]}
    storage.hit.search.return_value = {"total": 1}
    monkeypatch.setattr(action_service, "datastore", lambda: storage)

    encrypted_token = auth_service.encrypt_token("trusted-token")
    action_service.process_action_batch(
        "create", [{"hit_ids": ["hit-1"], "uname": user.uname, "auth_token": encrypted_token}]
    )

    if not should_enqueue:
        queue.push.assert_not_called()
        return

    queue.push.assert_called_once()
    job = queue.push.call_args.args[0]
    assert auth_service.decrypt_token(job["bearer_token"]) == "trusted-token"
    assert "persisted-token" not in repr(job)


@pytest.mark.parametrize(
    "token",
    ["non-jwt-token", jwt.encode({"sub": "analyst"}, "test-secret-which-is-at-least-32-bytes", algorithm="HS256")],
)
def test_bearer_fallback_is_encrypted_and_forwarded(monkeypatch, token):
    settings = AITriage(enabled=True, endpoint="https://ai.invalid/chat", model="model")
    monkeypatch.setattr(config.core, "ai", settings)
    monkeypatch.setattr(config.system, "encryption_key", "0123456789abcdef0123456789abcdef")
    monkeypatch.setattr(CLASSIFICATION, "enforce", False)
    monkeypatch.setattr(actions, "_get_operation", lambda _operation_id: ai_triage)
    monkeypatch.setattr(ai_service, "_eligible_targets", lambda *_args: ["hit-1"])
    queue = Mock()
    monkeypatch.setattr(ai_service, "get_queue", lambda: queue)
    user = make_user()
    monkeypatch.setattr(user_service, "get_user", Mock(return_value=user))
    monkeypatch.setattr(hit_service, "get_hit", Mock(return_value=(make_hit(), "version")))
    save = Mock(return_value=True)
    monkeypatch.setattr(ai_service, "save_ai_lead", save)
    session = MagicMock()
    session.__enter__.return_value = session
    session.post.return_value.__enter__.return_value.json.return_value = {
        "choices": [{"message": {"content": "generated opinion"}}]
    }
    monkeypatch.setattr(ai_service.requests, "Session", Mock(return_value=session))

    with Flask(__name__).test_request_context(headers={"Authorization": f"Bearer {token}"}):
        report = actions.execute("ai_triage", "*:*", user)

    assert report[0]["outcome"] == "success"
    job = queue.push.call_args.args[0]
    assert token not in repr(job)
    assert auth_service.decrypt_token(job["bearer_token"]) == token

    ai_triage_worker._process(job)

    assert session.post.call_args.kwargs["headers"]["Authorization"] == f"Bearer {token}"
    save.assert_called_once_with("hit-1", user, "generated opinion")
