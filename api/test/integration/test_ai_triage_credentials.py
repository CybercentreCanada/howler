"""AI triage credential handling across dispatch, the real persistent Redis queue, and the worker.

Needs the Redis container from `api/dev/docker-compose.yml`. The provider HTTP session and the user/hit
lookups are still mocked; everything between dispatch and worker (serialization, storage) is real.
"""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import jwt
import pytest
import redis
from flask import Flask

from howler import actions
from howler.actions import ai_triage
from howler.config import CLASSIFICATION, config
from howler.cronjobs import ai_triage_worker
from howler.odm.models.config import AIConfig
from howler.remote.datatypes import get_client
from howler.services import action_service, ai_service, auth_service, hit_service, user_service
from howler.utils.uid import get_random_id
from test.unit.ai.support import make_hit, make_user

ENCRYPTION_KEY = "0123456789abcdef0123456789abcdef"
JWT = jwt.encode({"sub": "analyst"}, "test-secret-which-is-at-least-32-bytes", algorithm="HS256")


@pytest.fixture
def queue(monkeypatch):
    persistent = config.core.redis.persistent
    try:
        get_client(persistent.host, persistent.port, False).ping()
    except redis.ConnectionError:
        pytest.skip("Connection to the persistent Redis server failed. This test cannot be performed.")

    monkeypatch.setattr(ai_service, "AI_TRIAGE_QUEUE_NAME", f"test.ai_triage.{get_random_id()}")
    monkeypatch.setattr(ai_service, "_queue", None)
    queue = ai_service.get_queue()
    yield queue
    queue.delete()


def configure(monkeypatch, api_key=None):
    ai = AIConfig(enabled=True, endpoint="https://ai.invalid/chat", model="m", api_key=api_key)
    monkeypatch.setattr(config.core, "ai", ai)
    monkeypatch.setattr(config.system, "encryption_key", ENCRYPTION_KEY)
    monkeypatch.setattr(CLASSIFICATION, "enforce", False)
    monkeypatch.setattr(actions, "_get_operation", lambda _operation_id: ai_triage)
    monkeypatch.setattr(ai_service, "_eligible_targets", lambda *_args: ["hit-1"])


@pytest.fixture
def pipeline(monkeypatch, queue):
    user = make_user()
    monkeypatch.setattr(user_service, "get_user", Mock(return_value=user))
    monkeypatch.setattr(hit_service, "get_hit", Mock(return_value=make_hit(id="hit-1")))
    save = Mock(return_value=True)
    monkeypatch.setattr(ai_service, "save_ai_lead", save)
    session = MagicMock()
    session.__enter__.return_value = session
    response = session.post.return_value.__enter__.return_value
    response.iter_content.side_effect = lambda chunk_size: iter(
        [json.dumps({"choices": [{"message": {"content": "generated opinion"}}]}).encode("utf-8")]
    )
    monkeypatch.setattr(ai_service.requests, "Session", Mock(return_value=session))

    def dispatch(authorization):
        with Flask(__name__).test_request_context(headers={"Authorization": authorization}):
            report = actions.execute("ai_triage", "*:*", user)
        stored = queue.c.lrange(queue.name, 0, -1)
        return report, stored, queue.pop(blocking=False)

    return SimpleNamespace(dispatch=dispatch, session=session, save=save, user=user)


@pytest.mark.parametrize(
    ("api_key", "authorization", "queued_token", "credential"),
    [
        ("provider-secret", "Basic dXNlcjpwYXNz", None, "provider-secret"),
        ("provider-secret", "Bearer incoming-token", None, "provider-secret"),
        (None, "Bearer non-jwt-token", "non-jwt-token", "non-jwt-token"),
        (None, f"Bearer {JWT}", JWT, JWT),
    ],
)
def test_credential_survives_queue_and_reaches_provider_without_being_stored(
    monkeypatch, pipeline, api_key, authorization, queued_token, credential
):
    configure(monkeypatch, api_key)

    report, stored, job = pipeline.dispatch(authorization)

    assert report[0]["outcome"] == "success"
    assert len(stored) == 1
    assert credential.encode() not in stored[0]
    assert isinstance(job, ai_service.AIAlertJob)
    if queued_token is None:
        assert job.bearer_token is None
    else:
        assert auth_service.decrypt_token(job.bearer_token) == queued_token

    ai_triage_worker._process(job)

    assert pipeline.session.post.call_args.kwargs["headers"]["Authorization"] == f"Bearer {credential}"
    pipeline.save.assert_called_once_with("hit-1", pipeline.user, "generated opinion")


def test_worker_discards_key_backed_job_if_key_was_removed(monkeypatch, pipeline, caplog):
    configure(monkeypatch)

    ai_triage_worker._process(ai_service.AIAlertJob(hit_id="hit-1", uname="analyst", bearer_token=None, prompt=None))

    assert "requires a provider credential" in caplog.text
    pipeline.session.post.assert_not_called()
    pipeline.save.assert_not_called()


def test_provider_key_does_not_bypass_action_permissions(monkeypatch, queue):
    configure(monkeypatch, "provider-secret")
    user = make_user()
    user.type = ["user"]

    assert actions.execute("ai_triage", "*:*", None)[0]["title"] == "Authentication required"
    assert actions.execute("ai_triage", "*:*", user)[0]["title"] == "Insufficient permissions"
    assert len(queue) == 0


@pytest.mark.parametrize(("data_json", "should_enqueue"), [("{}", True), ('{"auth_token":"persisted-token"}', False)])
def test_triggered_action_uses_decrypted_token_without_request_context(monkeypatch, queue, data_json, should_enqueue):
    configure(monkeypatch)
    monkeypatch.setattr(action_service, "audit", Mock())
    user = make_user()
    operation = SimpleNamespace(operation_id="ai_triage", data_json=data_json, data={})
    action = SimpleNamespace(action_id="action-id", query="*:*", operations=[operation])
    storage = Mock()
    storage.user.get.return_value = user
    storage.action.search.return_value = {"items": [action]}
    storage.hit.search.return_value = {"total": 1}
    monkeypatch.setattr(action_service, "datastore", lambda: storage)

    action_service.process_action_batch(
        "create",
        [{"hit_ids": ["hit-1"], "uname": user.uname, "auth_token": auth_service.encrypt_token("trusted-token")}],
    )

    assert len(queue) == int(should_enqueue)
    if should_enqueue:
        stored = queue.c.lrange(queue.name, 0, -1)[0]
        job = queue.pop(blocking=False)
        assert auth_service.decrypt_token(job.bearer_token) == "trusted-token"
        assert b"trusted-token" not in stored and b"persisted-token" not in stored
