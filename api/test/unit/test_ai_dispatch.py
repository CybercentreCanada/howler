"""Focused regression coverage for guarded AI triage dispatch and queue state."""

import json
import os
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import gevent
import pytest
import redis

import howler.actions as actions
from howler.actions import ai_triage
from howler.odm.models.config import AITriage
from howler.services import ai_transport, ai_triage_queue, ai_triage_service, ai_triage_worker


def _ai_config(**overrides) -> AITriage:
    fields = {
        "enabled": True,
        "provider": "openai",
        "endpoint": "https://provider.example.invalid/v1/chat/completions",
        "model": "triage-model",
    }
    fields.update(overrides)
    return AITriage(**fields)


def test_ai_triage_configuration_is_local_and_rejects_reserved_fields():
    assert _ai_config().locally_valid()
    assert _ai_config(enabled=False).locally_valid() is False
    assert _ai_config(endpoint="http://provider.example.invalid/chat").locally_valid() is False
    assert _ai_config(endpoint="http://localhost:8000/chat").locally_valid()
    assert _ai_config(headers={"Authorization": "attacker"}).locally_valid() is False
    assert _ai_config(extra_body={"stream": True}).locally_valid() is False
    assert _ai_config(headers={"bad header": "value"}).locally_valid() is False
    assert _ai_config(extra_body={"value": object()}).locally_valid() is False
    assert _ai_config(provider="a2a", model=None, extra_body={}).locally_valid()


def test_action_spec_declares_bearer_and_only_optional_prompt():
    spec = ai_triage.specification()
    assert spec["id"] == "ai_triage"
    assert spec["requires_auth_token"] is True
    assert spec["steps"] == [{"args": {}, "optional_args": ["prompt"]}]
    assert "trusted-bearer" not in json.dumps(spec)
    assert "server-secret" not in json.dumps(spec)


def test_shared_dispatch_requires_trusted_token_and_preserves_run_references(monkeypatch):
    operation = SimpleNamespace(
        SKIP_CENTRAL_LIMIT=True,
        specification=lambda: {"roles": ["automation_basic"], "requires_auth_token": True},
        execute=MagicMock(
            return_value=[
                {
                    "query": "q1",
                    "outcome": "success",
                    "title": "Queued",
                    "message": "Accepted",
                    "run_id": "r1",
                    "status": "queued",
                },
                {
                    "query": "q2",
                    "outcome": "success",
                    "title": "Queued",
                    "message": "Accepted",
                    "run_id": "r2",
                    "status": "queued",
                },
            ]
        ),
    )
    monkeypatch.setattr(actions, "_get_operation", lambda _operation_id: operation)
    user = MagicMock()
    user.__getitem__.side_effect = lambda key: {"type": ["automation_basic"]}[key]

    rejected = actions.execute("ai_triage", "q", user)
    assert rejected[0]["outcome"] == "error"
    operation.execute.assert_not_called()

    report = actions.execute(
        "ai_triage",
        "q",
        user,
        request_id="request-1",
        trusted_auth_token="trusted-bearer",
        auth_token="untrusted-action-data",
        trusted_auth_token_override="ignored",
    )
    assert len(report) == 2
    assert {entry["run_id"] for entry in report} == {"r1", "r2"}
    kwargs = operation.execute.call_args.kwargs
    assert kwargs["trusted_auth_token"] == "trusted-bearer"
    assert "auth_token" not in kwargs


class _FakeLock:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.local = SimpleNamespace(token=uuid.uuid4().hex.encode())

    def acquire(self, blocking=True, token=None):
        del blocking
        self.local.token = token.encode("utf-8") if isinstance(token, str) else token
        self.client.values[self.name] = self.local.token
        return True

    def release(self):
        if self.client.values.get(self.name) == self.local.token:
            self.client.values.pop(self.name, None)
        return None


class _FakePipeline:
    def __init__(self, client):
        self.client = client
        self.operations = []
        self.watched = []
        self.watched_values = {}
        self.in_multi = False

    def watch(self, *keys):
        self.watched.extend(keys)
        self.watched_values.update({key: self.client.get(key) for key in keys})
        return True

    def get(self, key):
        return self.client.get(key)

    def multi(self):
        self.in_multi = True
        return self

    def reset(self):
        self.operations.clear()
        self.watched.clear()
        self.watched_values.clear()
        return None

    def __getattr__(self, name):
        def enqueue(*args, **kwargs):
            self.operations.append((name, args, kwargs))
            return self

        return enqueue

    def execute(self):
        if any(self.client.get(key) != value for key, value in self.watched_values.items()):
            raise redis.exceptions.WatchError("watched lock changed")
        return [getattr(self.client, name)(*args, **kwargs) for name, args, kwargs in self.operations]


class _FakeRedis:
    def __init__(self):
        self.values = {}
        self.lists = {}
        self.zsets = {}

    def lock(self, name, **_kwargs):
        return _FakeLock(self, name)

    def pipeline(self, **_kwargs):
        return _FakePipeline(self)

    def get(self, name):
        return self.values.get(name)

    def set(self, name, value, **_kwargs):
        self.values[name] = value
        return True

    def eval(self, _script, _numkeys, key, token):
        token = token.encode("utf-8") if isinstance(token, str) else token
        if self.values.get(key) != token:
            return 0
        self.values.pop(key, None)
        return 1

    def expire(self, _name, _ttl):
        return True

    def persist(self, _name):
        return True

    def delete(self, name):
        return int(self.values.pop(name, None) is not None)

    def zadd(self, name, values):
        self.zsets.setdefault(name, {}).update(values)
        return len(values)

    def zrem(self, name, *members):
        result = 0
        for member in members:
            existed = member in self.zsets.setdefault(name, {})
            self.zsets[name].pop(member, None)
            result += int(existed)
        return result

    def zcard(self, name):
        return len(self.zsets.setdefault(name, {}))

    def zscore(self, name, member):
        return self.zsets.setdefault(name, {}).get(member)

    def zrange(self, name, start, stop, *, withscores=False):
        ordered = sorted(self.zsets.setdefault(name, {}).items(), key=lambda entry: entry[1])
        if stop < 0:
            stop = len(ordered) + stop
        selected = ordered[start : stop + 1]
        return selected if withscores else [member for member, _score in selected]

    def zrangebyscore(self, name, minimum, maximum, *, start=0, num=None):
        lower = float("-inf") if minimum == "-inf" else float(minimum)
        upper = float(maximum)
        members = [member for member, score in self.zsets.setdefault(name, {}).items() if lower <= score <= upper]
        return members[start:] if num is None else members[start : start + num]

    def zrevrange(self, name, start, stop):
        ordered = sorted(self.zsets.setdefault(name, {}).items(), key=lambda entry: entry[1], reverse=True)
        if stop < 0:
            stop = len(ordered) + stop
        return [member for member, _score in ordered[start : stop + 1]]

    def zrevrank(self, name, member):
        ordered = sorted(self.zsets.setdefault(name, {}).items(), key=lambda entry: entry[1], reverse=True)
        return next((rank for rank, (candidate, _score) in enumerate(ordered) if candidate == member), None)

    def rpush(self, name, *values):
        self.lists.setdefault(name, []).extend(values)
        return len(self.lists[name])

    def lindex(self, name, index):
        values = self.lists.setdefault(name, [])
        return values[index] if -len(values) <= index < len(values) else None

    def lpop(self, name):
        values = self.lists.setdefault(name, [])
        return values.pop(0) if values else None

    def lrem(self, name, count, value):
        values = self.lists.setdefault(name, [])
        removed = 0
        for index, item in enumerate(list(values)):
            if item == value and (count == 0 or removed < count):
                values.pop(index - removed)
                removed += 1
                if count > 0 and removed >= count:
                    break
        return removed


def _run(run_id="run-1", targets=1):
    return {
        "run_id": run_id,
        "operation_id": "ai_triage",
        "request_id": None,
        "action_id": None,
        "trigger": None,
        "state": "queued",
        "revision": 0,
        "created_at": "2026-01-01T00:00:00Z",
        "started_at": None,
        "updated_at": "2026-01-01T00:00:00Z",
        "finished_at": None,
        "expires_at": None,
        "counts": {},
        "results": [
            {
                "hit_id": f"hit-{index}",
                "state": "queued",
                "attempts": 0,
                "reason": None,
                "message": None,
                "started_at": None,
                "finished_at": None,
                "_deadline_at": None,
            }
            for index in range(targets)
        ],
        "_owner": "alice",
        "_expires_at": None,
        "_created_at_epoch": 100,
    }


@pytest.fixture
def queue_backend(monkeypatch):
    now = [100.0]
    redis = _FakeRedis()
    settings = AITriage(
        enabled=True,
        endpoint="https://provider.example.invalid/chat",
        model="model",
        lease_seconds=3,
        deadline_seconds=10,
        max_attempts=2,
        max_concurrent_jobs=1,
        retention_seconds=60,
    )
    monkeypatch.setattr(ai_triage_queue, "redis_client", lambda: redis)
    monkeypatch.setattr(ai_triage_queue, "_now", lambda: now[0])
    monkeypatch.setattr(ai_triage_queue.config.core, "ai", settings)
    return redis, now


def _real_redis_queue(monkeypatch, *, retention_seconds=60):
    from urllib.parse import urlparse

    redis_url = urlparse(os.environ.get("AI_TRIAGE_TEST_REDIS_URL", "redis://127.0.0.1:16389/15"))
    client = redis.Redis(host=redis_url.hostname or "127.0.0.1", port=redis_url.port or 16389, db=0)
    assert client.ping(), "AI triage owner-index regression requires the isolated Redis service"
    prefix = f"howler.ai_triage.owner-test:{{{uuid.uuid4().hex}}}"
    settings = AITriage(
        enabled=True,
        endpoint="https://provider.example.invalid/chat",
        model="model",
        lease_seconds=2,
        deadline_seconds=10,
        max_attempts=2,
        max_concurrent_jobs=1,
        retention_seconds=60,
    )
    monkeypatch.setattr(ai_triage_queue, "_KEY_PREFIX", prefix)
    monkeypatch.setattr(ai_triage_queue, "redis_client", lambda: client)
    monkeypatch.setattr(ai_triage_queue.config.core, "ai", settings)
    monkeypatch.setattr(settings, "retention_seconds", retention_seconds)
    return client, prefix


def _complete_owner_history_run(run_id, created_at):
    run = _run(run_id=run_id)
    run["_created_at_epoch"] = created_at
    ai_triage_queue.create_run(run)
    job, _ = ai_triage_queue.claim_next()
    assert job is not None and job["run_id"] == run_id
    completed = ai_triage_queue.finish_item(run_id, 0, job["nonce"], state="succeeded")
    assert completed is not None and completed["state"] == "completed"
    return completed


def _seed_owner_index_run(client, run_id, score, *, state="completed", expires_at=None, visible=True, active=False):
    run = {**_run(run_id=run_id), "state": state, "_visible": visible}
    if expires_at is not None:
        run["_expires_at"] = expires_at
        run["expires_at"] = "retained"
    client.set(ai_triage_queue._run_key(run_id), json.dumps(run))
    client.zadd(ai_triage_queue._owner_key("alice"), {run_id: score})
    client.set(ai_triage_queue._owner_index_initialized_key("alice"), "1")
    if state == "completed" and expires_at is not None:
        client.zadd(ai_triage_queue._owner_expiry_key("alice"), {run_id: expires_at})
    if active:
        client.zadd(ai_triage_queue._active_key(), {run_id: score})
        client.zadd(ai_triage_queue._owner_active_key("alice"), {run_id: score})


def test_real_redis_owner_history_expires_after_terminal_document_ttl(monkeypatch):
    client, prefix = _real_redis_queue(monkeypatch, retention_seconds=1)
    expired_run_id = f"{prefix}-expires"
    live_run_id = f"{prefix}-live"
    try:
        _complete_owner_history_run(expired_run_id, time.time())
        owner_key = ai_triage_queue._owner_key("alice")
        expiry_key = ai_triage_queue._owner_expiry_key("alice")
        assert client.exists(ai_triage_queue._run_key(expired_run_id))
        assert client.zscore(owner_key, expired_run_id) is not None
        assert 0 < client.ttl(owner_key) <= 2
        assert client.zscore(expiry_key, expired_run_id) is not None

        live_run = _run(run_id=live_run_id)
        live_run["_created_at_epoch"] = time.time() + 1
        ai_triage_queue.create_run(live_run)
        live_job, _ = ai_triage_queue.claim_next()
        assert live_job is not None and live_job["run_id"] == live_run_id
        assert client.ttl(owner_key) == -1, "A live run must keep the owner's index persistent"

        deadline = time.monotonic() + 4
        while client.exists(ai_triage_queue._run_key(expired_run_id)) and time.monotonic() < deadline:
            time.sleep(0.05)

        assert not client.exists(ai_triage_queue._run_key(expired_run_id))
        runs, progress = ai_triage_queue.list_runs("alice", 0, 10)
        assert [run["run_id"] for run in runs] == [live_run_id]
        assert progress == ai_triage_queue.OwnerRunScan(fetched_count=2, next_offset=1, exhausted=True)
        assert client.zscore(owner_key, expired_run_id) is None
        assert client.zscore(owner_key, live_run_id) is not None
        assert client.ttl(owner_key) == -1

        assert ai_triage_queue.finish_item(live_run_id, 0, live_job["nonce"], state="succeeded") is not None
        assert 0 < client.ttl(owner_key) <= 2
        deadline = time.monotonic() + 4
        while client.exists(owner_key) and time.monotonic() < deadline:
            time.sleep(0.05)

        assert not client.exists(ai_triage_queue._run_key(live_run_id))
        assert not client.exists(owner_key)
        assert not client.exists(expiry_key)
        assert not client.exists(ai_triage_queue._owner_index_initialized_key("alice"))
    finally:
        keys = list(client.scan_iter(match=f"{prefix}:*"))
        if keys:
            client.delete(*keys)
        client.close()


def test_real_redis_missing_owner_document_is_pruned_without_skipping_pages(monkeypatch):
    client, prefix = _real_redis_queue(monkeypatch)
    run_ids = [f"{prefix}-{index}" for index in range(3)]
    try:
        for index, run_id in enumerate(run_ids):
            _complete_owner_history_run(run_id, 100 + index)

        owner_key = ai_triage_queue._owner_key("alice")
        newest_id = run_ids[-1]
        client.delete(ai_triage_queue._run_key(newest_id))
        # Simulate the prior deployment's permanent history index: only run
        # documents had TTLs, with no owner-active/expiry metadata.
        client.persist(owner_key)
        client.delete(
            ai_triage_queue._owner_active_key("alice"),
            ai_triage_queue._owner_expiry_key("alice"),
            ai_triage_queue._owner_index_initialized_key("alice"),
        )

        user = SimpleNamespace(uname="alice")
        monkeypatch.setattr(
            ai_triage_service,
            "_matches_run_filters",
            lambda run, current_user, **_kwargs: run.get("_owner") == current_user.uname,
        )
        page = ai_triage_service.list_runs(user, rows=1)

        assert [item["run_id"] for item in page["items"]] == [run_ids[-2]]
        assert page["has_more"] is True
        assert client.zscore(owner_key, newest_id) is None
        assert client.zcard(owner_key) == 2
        assert 0 < client.ttl(owner_key) <= 60
        next_page = ai_triage_service.list_runs(user, rows=1, offset=1)
        assert [item["run_id"] for item in next_page["items"]] == [run_ids[-3]]
        assert next_page["has_more"] is False
        assert client.zcard(ai_triage_queue._owner_active_key("alice")) == 0
    finally:
        keys = list(client.scan_iter(match=f"{prefix}:*"))
        if keys:
            client.delete(*keys)
        client.close()


def test_persistent_queue_claim_permits_ack_and_completion(queue_backend):
    redis, _now = queue_backend
    ai_triage_queue.create_run(_run(targets=2))

    first, _ = ai_triage_queue.claim_next()
    assert first["hit_id"] == "hit-0"
    assert first["attempts"] == 0
    assert first["run"]["state"] == "running"
    assert first["run"]["started_at"] is not None
    assert first["run"]["results"][0]["started_at"] is not None
    assert ai_triage_queue.lease_is_current(first["run_id"], first["index"], first["nonce"])
    blocked, _ = ai_triage_queue.claim_next()
    assert blocked is None

    updated = ai_triage_queue.finish_item(first["run_id"], first["index"], first["nonce"], state="succeeded")
    assert updated["counts"]["succeeded"] == 1
    second, _ = ai_triage_queue.claim_next()
    assert second["hit_id"] == "hit-1"
    completed = ai_triage_queue.finish_item(
        second["run_id"], second["index"], second["nonce"], state="skipped", reason="changed"
    )
    assert completed["state"] == "completed"
    assert completed["counts"] == {"total": 2, "queued": 0, "running": 0, "succeeded": 1, "failed": 0, "skipped": 1}
    assert redis.zcard(ai_triage_queue._lease_key()) == 0
    assert ai_triage_queue.lease_is_current(second["run_id"], second["index"], second["nonce"]) is False


def test_queued_runs_do_not_expire_before_claim_and_disabled_reconciliation_is_terminal(
    queue_backend,
):
    _redis, _now = queue_backend
    run = ai_triage_queue.create_run(_run())
    assert run["_expires_at"] is None
    assert run["expires_at"] is None

    changed, active = ai_triage_queue.fail_pending_when_unavailable()
    assert not active
    assert changed[0]["state"] == "completed"
    assert changed[0]["results"][0]["reason"] == "configuration_unavailable"
    assert changed[0]["_expires_at"] == pytest.approx(160)


def test_owner_history_keeps_index_member_when_document_read_fails(queue_backend, monkeypatch):
    client, _now = queue_backend
    completed = _complete_owner_history_run("transient-owner-read", 100)
    owner_key = ai_triage_queue._owner_key(completed["_owner"])
    assert client.zscore(owner_key, completed["run_id"]) is not None

    original_get = client.get

    def failed_run_read(key):
        if key == ai_triage_queue._run_key(completed["run_id"]):
            raise redis.exceptions.ConnectionError("temporary Redis read failure")
        return original_get(key)

    monkeypatch.setattr(client, "get", failed_run_read)
    with pytest.raises(redis.exceptions.ConnectionError):
        ai_triage_queue.list_runs(completed["_owner"], 0, 10)

    assert client.zscore(owner_key, completed["run_id"]) is not None


def test_action_run_pagination_does_not_treat_full_stale_window_as_eof(queue_backend, monkeypatch):
    client, _now = queue_backend
    for index in range(ai_triage_queue.RUN_SCAN_BATCH):
        client.zadd(ai_triage_queue._owner_key("alice"), {f"missing-{index}": 1000 - index})
    for index in range(2):
        _seed_owner_index_run(client, f"visible-{index}", 100 - index, expires_at=1000)
    user = SimpleNamespace(uname="alice")
    monkeypatch.setattr(
        ai_triage_service,
        "_matches_run_filters",
        lambda run, _user, **_kwargs: run.get("_visible", True),
    )

    page = ai_triage_service.list_runs(user, rows=1)

    assert [item["run_id"] for item in page["items"]] == ["visible-0"]
    assert page["has_more"] is True
    assert client.zcard(ai_triage_queue._owner_key("alice")) == 2


def test_action_run_pagination_advances_over_stale_and_filtered_full_window(queue_backend, monkeypatch):
    client, _now = queue_backend
    for index in range(ai_triage_queue.RUN_SCAN_BATCH - 1):
        client.zadd(ai_triage_queue._owner_key("alice"), {f"missing-{index}": 1000 - index})
    _seed_owner_index_run(client, "filtered-out", 100, expires_at=1000, visible=False)
    _seed_owner_index_run(client, "match-0", 99, expires_at=1000)
    _seed_owner_index_run(client, "match-1", 98, expires_at=1000)
    user = SimpleNamespace(uname="alice")
    monkeypatch.setattr(
        ai_triage_service,
        "_matches_run_filters",
        lambda run, _user, **_kwargs: run.get("_visible", True),
    )

    first_page = ai_triage_service.list_runs(user, rows=1)
    second_page = ai_triage_service.list_runs(user, rows=1, offset=1)

    assert [item["run_id"] for item in first_page["items"]] == ["match-0"]
    assert first_page["has_more"] is True
    assert [item["run_id"] for item in second_page["items"]] == ["match-1"]
    assert second_page["has_more"] is False


def test_action_run_pagination_handles_multiple_exact_full_stale_windows(queue_backend, monkeypatch):
    client, _now = queue_backend
    stale_count = ai_triage_queue.RUN_SCAN_BATCH * 2
    client.set(ai_triage_queue._owner_index_initialized_key("alice"), "1")
    for index in range(stale_count):
        client.zadd(ai_triage_queue._owner_key("alice"), {f"missing-{index}": 1000 - index})
    user = SimpleNamespace(uname="alice")
    monkeypatch.setattr(ai_triage_service, "_matches_run_filters", lambda *_args, **_kwargs: False)

    page = ai_triage_service.list_runs(user, rows=20)

    assert page["items"] == []
    assert page["has_more"] is False
    assert client.zcard(ai_triage_queue._owner_key("alice")) == 0


def test_owner_expiry_cleanup_adjusts_only_removed_ranks_before_page_boundary(queue_backend):
    client, _now = queue_backend
    expired_ids = ["expired-before", "expired-inside", "expired-after"]
    _seed_owner_index_run(client, expired_ids[0], 600, expires_at=90)
    _seed_owner_index_run(client, "live-before", 500, state="queued", active=True)
    _seed_owner_index_run(client, expired_ids[1], 400, expires_at=90)
    _seed_owner_index_run(client, "live-page", 300, state="running", active=True)
    _seed_owner_index_run(client, expired_ids[2], 200, expires_at=90)
    _seed_owner_index_run(client, "live-after", 100, state="queued", active=True)
    absent_id = "expired-member-without-owner-document"
    client.zadd(ai_triage_queue._owner_expiry_key("alice"), {absent_id: 90})

    page, progress = ai_triage_queue.list_runs("alice", offset=2, rows=2)

    assert [run["run_id"] for run in page] == ["live-page"]
    assert progress == ai_triage_queue.OwnerRunScan(fetched_count=2, next_offset=2, exhausted=False)
    assert client.zscore(ai_triage_queue._owner_key("alice"), expired_ids[0]) is None
    assert client.zscore(ai_triage_queue._owner_key("alice"), expired_ids[1]) is None
    assert client.zscore(ai_triage_queue._owner_key("alice"), expired_ids[2]) is None
    assert client.zscore(ai_triage_queue._owner_key("alice"), absent_id) is None

    next_page, next_progress = ai_triage_queue.list_runs("alice", progress.next_offset, 2)
    assert [run["run_id"] for run in next_page] == ["live-after"]
    assert next_progress.exhausted is True


def test_real_redis_lock_cancellation_drains_nonce_cleanup_and_preserves_fences(tmp_path):  # noqa: C901
    """Exercise cancellation at SET/acquire/body/release boundaries in a patched child."""
    redis_url = os.environ.get("AI_TRIAGE_TEST_REDIS_URL", "redis://127.0.0.1:16389/15")
    api_root = Path(__file__).parents[2]
    settings = {
        "ui": {"debug": False, "audit": False},
        "auth": {"oauth": {"enabled": False}},
        "core": {
            "ai": {"enabled": False},
            "plugins": [],
            "telemetry": {"enabled": False},
            "redis": {kind: {"host": "127.0.0.1", "port": 16389} for kind in ("persistent", "nonpersistent")},
        },
        "system": {
            "encryption_key": "0123456789abcdef0123456789abcdef",
            **{name: {"enabled": False} for name in ("action_queue", "correlation", "retention", "view_cleanup")},
        },
        "datastore": {"hosts": [{"name": "lock-probe", "scheme": "http", "host": "127.0.0.1:19289"}]},
    }
    (tmp_path / "config.yml").write_text(json.dumps(settings))
    (tmp_path / "classification.yml").write_text((api_root / "build_scripts" / "classification.yml").read_text())
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    env = {
        key: os.environ[key]
        for key in ("PATH", "VIRTUAL_ENV", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "LC_CTYPE", "TMPDIR")
        if key in os.environ
    }
    env.update(
        APP_NAME="howler",
        HWL_CONF_FOLDER=str(tmp_path),
        HWL_CLASSIFICATION_PATH=str(api_root / "build_scripts" / "classification.yml"),
        HWL_PLUGIN_DIRECTORY=str(plugins),
        PYTHONPATH=str(api_root),
        PYTHONSAFEPATH="1",
        PYTHONDONTWRITEBYTECODE="1",
        PYTHON_DOTENV_DISABLED="1",
        PYTHONUNBUFFERED="1",
    )
    script = r"""
from gevent.monkey import patch_all
patch_all()

import json
import sys
import time

import gevent
from gevent.event import Event
from redis import Redis

from howler.services import ai_triage_queue as queue

payload = json.loads(sys.argv[1])
client = Redis.from_url(payload["redis_url"], socket_connect_timeout=1)
queue.redis_client = lambda: client
queue._KEY_PREFIX = payload["prefix"]
evidence = {}


def cancel_boundary(stage):
    key = f"{payload['prefix']}:{stage}"
    pause_started, continue_io = Event(), Event()
    body_started, continue_body = Event(), Event()
    release_started, continue_release = Event(), Event()
    body_entries, cancellations, errors = [], [], []
    original_set, original_eval, original_lock = client.set, client.eval, client.lock
    once = [False]

    if stage == "set":
        def delayed_set(name, value, *args, **kwargs):
            result = original_set(name, value, *args, **kwargs)
            if name == key and not once[0]:
                once[0] = True
                pause_started.set()
                continue_io.wait(timeout=4)
            return result

        client.set = delayed_set
    elif stage == "acquire":
        def delayed_lock(name, **kwargs):
            lock = original_lock(name, **kwargs)
            if name == key:
                original_acquire = lock.acquire

                def delayed_acquire(*args, **acquire_kwargs):
                    result = original_acquire(*args, **acquire_kwargs)
                    if result and not once[0]:
                        once[0] = True
                        pause_started.set()
                        continue_io.wait(timeout=4)
                    return result

                lock.acquire = delayed_acquire
            return lock

        client.lock = delayed_lock
    elif stage in {"body", "release"}:
        def delayed_eval(script, numkeys, *args, **kwargs):
            if args and args[0] == key and not once[0]:
                once[0] = True
                release_started.set()
                continue_release.wait(timeout=4)
            return original_eval(script, numkeys, *args, **kwargs)

        client.eval = delayed_eval

    def contender():
        try:
            with queue._locked(client, key):
                body_entries.append(True)
                if stage == "body":
                    body_started.set()
                    continue_body.wait(timeout=4)
        except gevent.GreenletExit:
            cancellations.append(True)
        except BaseException as exc:
            errors.append(type(exc).__name__)

    root = gevent.spawn(contender)
    if stage in {"set", "acquire"}:
        assert pause_started.wait(timeout=2), f"{stage} barrier was not reached"
    elif stage == "body":
        assert body_started.wait(timeout=2)
    else:
        assert release_started.wait(timeout=2), "release barrier was not reached"

    if stage == "release":
        root.kill(block=False)
        gevent.sleep(0)
        assert not root.ready(), "release cancellation must wait for the in-flight compare-delete"
        root.kill(block=False)  # A repeated cancellation must not abandon the cleanup child.
        gevent.sleep(0)
        assert not root.ready()
        continue_release.set()
    else:
        root.kill(block=False)
        gevent.sleep(0)
        if stage in {"set", "acquire"}:
            assert not root.ready(), "cancellation must wait for the same acquire attempt"
            continue_io.set()
        elif stage == "body":
            assert not root.ready(), "body cancellation must drain its compare-delete"
            continue_body.set()
            assert release_started.wait(timeout=2)
            root.kill(block=False)
            gevent.sleep(0)
            assert not root.ready()
            continue_release.set()

    root.join(timeout=3)
    assert root.ready(), f"{stage} cancellation did not settle"
    assert not errors, (stage, errors)
    assert cancellations == [True]
    if stage in {"set", "acquire"}:
        assert not body_entries, "Cancelled acquisition must never enter the lock body"
    else:
        assert body_entries == [True]
    assert client.get(key) is None, f"{stage} cancellation stranded the Redis nonce"
    assert not queue.pending_lock_helpers()
    started = time.monotonic()
    with queue._locked(client, key):
        pass
    assert time.monotonic() - started < 0.5, "The next owner waited for TTL after cancellation"
    client.set, client.eval, client.lock = original_set, original_eval, original_lock


try:
    for boundary in ("set", "acquire", "body", "release"):
        cancel_boundary(boundary)

    # A failed contender may compare-delete only its own nonce.
    contended_key = f"{payload['prefix']}:contended"
    other_token = b"other-owner-nonce"
    client.set(contended_key, other_token, px=5000)
    queue.QUEUE_LOCK_ACQUIRE_TIMEOUT = 0.15
    try:
        with queue._locked(client, contended_key):
            raise AssertionError("A contended lock was acquired")
    except TimeoutError:
        pass
    assert client.get(contended_key) == other_token, "Failed acquire deleted another owner's token"
    queue.QUEUE_LOCK_ACQUIRE_TIMEOUT = 5.0
    client.delete(contended_key)

    # Expiry/replacement fences both the Redis transaction and nonce cleanup.
    fence_key = f"{payload['prefix']}:fenced"
    replacement = b"replacement-owner"
    result_key = f"{payload['prefix']}:stale-write"
    try:
        with queue._locked(client, fence_key):
            with queue._fenced_pipeline(client) as pipeline:
                pipeline.set(result_key, "stale")
                client.set(fence_key, replacement, px=5000)
                try:
                    pipeline.execute()
                except Exception as exc:
                    assert exc.__class__.__name__ == "WatchError"
                else:
                    raise AssertionError("A fenced stale transaction committed")
    finally:
        assert client.get(fence_key) == replacement, "Stale cleanup deleted a replacement owner's token"
        assert client.get(result_key) is None
        client.delete(fence_key)

    # A cleanup I/O timeout is an explicit fail-closed error, never a successful
    # lock exit followed by another queue claim.
    cleanup_key = f"{payload['prefix']}:cleanup-timeout"
    original_eval = client.eval
    cleanup_started = [False]

    def slow_eval(script, numkeys, *args, **kwargs):
        if args and args[0] == cleanup_key and not cleanup_started[0]:
            cleanup_started[0] = True
            gevent.sleep(0.5)
        return original_eval(script, numkeys, *args, **kwargs)

    client.eval = slow_eval
    queue.QUEUE_LOCK_CLEANUP_TIMEOUT = 0.1
    try:
        with queue._locked(client, cleanup_key):
            pass
    except queue.LockCleanupError:
        pass
    else:
        raise AssertionError("Incomplete nonce cleanup was reported as success")
    assert client.get(cleanup_key) is not None
    assert queue.pending_lock_cleanup_failure()
    assert not queue.pending_lock_helpers()
    client.eval = original_eval
    cleanup_token = client.get(cleanup_key)
    original_eval(queue._LOCK_RELEASE_SCRIPT, 1, cleanup_key, cleanup_token)

    sys.stdout.write("QA_LOCK_CANCELLATION_OK\n")
finally:
    keys = list(client.scan_iter(match=f"{payload['prefix']}:*"))
    if keys:
        client.delete(*keys)
    client.close()
"""
    redis_url = os.environ.get("AI_TRIAGE_TEST_REDIS_URL", "redis://127.0.0.1:16389/15")
    payload = {"redis_url": redis_url, "prefix": f"howler.ai_triage.lock-r3:{{{uuid.uuid4().hex}}}"}
    result = subprocess.run(
        [sys.executable, "-c", script, json.dumps(payload)],
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "QA_LOCK_CANCELLATION_OK" in result.stdout


def test_real_redis_worker_cancellation_drains_processing_heartbeat_and_renewal(tmp_path):  # noqa: C901
    """Cancel root/worker trees while a real renewal is paused after Redis SET."""
    redis_url = os.environ.get("AI_TRIAGE_TEST_REDIS_URL", "redis://127.0.0.1:16389/15")
    api_root = Path(__file__).parents[2]
    settings = {
        "ui": {"debug": False, "audit": False},
        "auth": {"oauth": {"enabled": False}},
        "core": {
            "ai": {"enabled": False},
            "plugins": [],
            "telemetry": {"enabled": False},
            "redis": {kind: {"host": "127.0.0.1", "port": 16389} for kind in ("persistent", "nonpersistent")},
        },
        "system": {
            "encryption_key": "0123456789abcdef0123456789abcdef",
            **{name: {"enabled": False} for name in ("action_queue", "correlation", "retention", "view_cleanup")},
        },
        "datastore": {"hosts": [{"name": "worker-lock-probe", "scheme": "http", "host": "127.0.0.1:19289"}]},
    }
    (tmp_path / "config.yml").write_text(json.dumps(settings))
    (tmp_path / "classification.yml").write_text((api_root / "build_scripts" / "classification.yml").read_text())
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    env = {
        key: os.environ[key]
        for key in ("PATH", "VIRTUAL_ENV", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "LC_CTYPE", "TMPDIR")
        if key in os.environ
    }
    env.update(
        APP_NAME="howler",
        HWL_CONF_FOLDER=str(tmp_path),
        HWL_CLASSIFICATION_PATH=str(api_root / "build_scripts" / "classification.yml"),
        HWL_PLUGIN_DIRECTORY=str(plugins),
        PYTHONPATH=str(api_root),
        PYTHONSAFEPATH="1",
        PYTHONDONTWRITEBYTECODE="1",
        PYTHON_DOTENV_DISABLED="1",
        PYTHONUNBUFFERED="1",
    )
    script = r"""
from gevent.monkey import patch_all
patch_all()

import json
import sys
import time

import gevent
from gevent.event import Event
from redis import Redis

from howler.odm.models.config import AITriage
from howler.odm.models.config import config
from howler.services import ai_triage_queue as queue
from howler.services import ai_triage_service as service
from howler.services import ai_triage_worker as worker

payload = json.loads(sys.argv[1])
client = Redis.from_url(payload["redis_url"], socket_connect_timeout=1)
original_set = client.set
original_heartbeat = queue.heartbeat
original_process = worker._process
original_notify = service.notify_run
queue.redis_client = lambda: client
service.is_available = lambda: True
service.notify_run = lambda *_args, **_kwargs: None
config.core.ai = AITriage(
    enabled=True,
    endpoint="https://provider.invalid/triage",
    model="worker-lifecycle-probe",
    lease_seconds=3,
    deadline_seconds=20,
    max_attempts=1,
    max_concurrent_jobs=1,
)
config.system.encryption_key = "0123456789abcdef0123456789abcdef"
evidence = {}


def record(run_id):
    run = {
        "run_id": run_id,
        "operation_id": "ai_triage",
        "request_id": None,
        "action_id": None,
        "trigger": None,
        "state": "queued",
        "revision": 0,
        "created_at": "2026-01-01T00:00:00Z",
        "started_at": None,
        "updated_at": "2026-01-01T00:00:00Z",
        "finished_at": None,
        "expires_at": None,
        "counts": {},
        "results": [{
            "hit_id": "unused-by-probe",
            "state": "queued",
            "attempts": 0,
            "reason": None,
            "message": None,
            "started_at": None,
            "finished_at": None,
            "_deadline_at": None,
        }],
        "_owner": "lock-probe",
        "_expires_at": None,
        "_created_at_epoch": time.time(),
        "_encrypted_bearer_token": "unused",
        "_auth_scheme": "Bearer",
    }
    queue.create_run(run)


def exercise(scenario):
    prefix = f"{payload['prefix']}:{scenario}"
    queue._KEY_PREFIX = prefix
    run_id = f"{scenario}-run"
    record(run_id)
    process_entered, finish_process, process_finished = Event(), Event(), Event()
    barrier_started, continue_set, heartbeat_killed = Event(), Event(), Event()
    attempts = [0]

    def stub_process(_job):
        process_entered.set()
        try:
            if scenario == "normal":
                finish_process.wait(timeout=5)
                process_finished.set()
                return
            gevent.sleep(20)
        finally:
            process_finished.set()

    worker._process = stub_process
    def lose_after_real_renewal(*args):
        original_heartbeat(*args)
        return None

    def paused_set(name, value, *args, **kwargs):
        result = original_set(name, value, *args, **kwargs)
        if name == queue._global_lock_key() and not attempts[0]:
            attempts[0] = 1
            barrier_started.set()
            continue_set.wait(timeout=5)
        return result

    scenario_original_set = client.set
    assert worker.start_workers()
    assert process_entered.wait(timeout=2)
    client.set = paused_set
    if scenario == "watchdog":
        queue.heartbeat = lose_after_real_renewal
    assert barrier_started.wait(timeout=3), f"{scenario} renewal did not pause after successful Redis SET"

    root = worker._workers[0]
    children = worker._worker_children.get(root, set())
    heartbeat = next(child for child in children if child._run.__name__ == "_heartbeat_with_lock_owner")
    original_kill = heartbeat.kill

    def observed_heartbeat_kill(*args, **kwargs):
        result = original_kill(*args, **kwargs)
        gevent.sleep(0)  # let cancellation reach the owned renewal before releasing SET
        heartbeat_killed.set()
        return result

    heartbeat.kill = observed_heartbeat_kill

    if scenario == "normal":
        finish_process.set()
        assert process_finished.wait(timeout=2)
        assert heartbeat_killed.wait(timeout=2), "Normal completion did not cancel its heartbeat"
        continue_set.set()
        worker.stop_workers(timeout=3)
    elif scenario == "watchdog":
        continue_set.set()
        assert process_finished.wait(timeout=3), "Lease watchdog did not cancel processing"
        worker.stop_workers(timeout=3)
    else:
        stopper = gevent.spawn(worker.stop_workers, 3)
        assert heartbeat_killed.wait(timeout=2), f"{scenario}: stop did not cancel the heartbeat tree"
        if scenario == "repeat_cancel":
            root.kill(block=False)
        continue_set.set()
        stopper.get(timeout=5)

    assert worker._started is False and worker._workers == []
    assert not worker._worker_children and not worker._outstanding_children
    assert not queue.pending_lock_helpers()
    assert queue.pending_lock_cleanup_failure() is None
    assert client.get(queue._global_lock_key()) is None
    started = time.monotonic()
    # The existing active lease may block a new job, but acquiring the global
    # queue lock must be immediate rather than waiting on its Redis TTL.
    queue.claim_next()
    evidence[scenario] = {"queue_lock_claim_seconds": time.monotonic() - started}
    assert evidence[scenario]["queue_lock_claim_seconds"] < 0.25
    keys = list(client.scan_iter(match=f"{prefix}:*"))
    if keys:
        client.delete(*keys)
    client.set = scenario_original_set
    queue.heartbeat = original_heartbeat


try:
    for mode in ("normal", "watchdog", "stop", "repeat_cancel"):
        exercise(mode)
    sys.stdout.write("QA_WORKER_TREE_DRAIN_OK=" + json.dumps(evidence) + "\n")
finally:
    worker.stop_workers(timeout=3)
    worker._process = original_process
    queue.heartbeat = original_heartbeat
    service.notify_run = original_notify
    keys = list(client.scan_iter(match=f"{payload['prefix']}:*"))
    if keys:
        client.delete(*keys)
    client.close()
"""
    payload = {
        "redis_url": redis_url,
        "prefix": f"howler.ai_triage.worker-lock-r3:{{{uuid.uuid4().hex}}}",
    }
    result = subprocess.run(
        [sys.executable, "-c", script, json.dumps(payload)],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "QA_WORKER_TREE_DRAIN_OK=" in result.stdout


def test_real_redis_lock_cleanup_owners_isolate_peer_helpers(tmp_path):
    """Two real worker roots isolate healthy completion from a peer's paused Redis helper."""
    api_root = Path(__file__).parents[2]
    settings = {
        "ui": {"debug": False, "audit": False},
        "auth": {"oauth": {"enabled": False}},
        "core": {
            "ai": {"enabled": False},
            "plugins": [],
            "telemetry": {"enabled": False},
            "redis": {kind: {"host": "127.0.0.1", "port": 16389} for kind in ("persistent", "nonpersistent")},
        },
        "system": {
            "encryption_key": "0123456789abcdef0123456789abcdef",
            **{name: {"enabled": False} for name in ("action_queue", "correlation", "retention", "view_cleanup")},
        },
        "datastore": {"hosts": [{"name": "owner-scope-probe", "scheme": "http", "host": "127.0.0.1:19289"}]},
    }
    (tmp_path / "config.yml").write_text(json.dumps(settings))
    (tmp_path / "classification.yml").write_text((api_root / "build_scripts" / "classification.yml").read_text())
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    env = {
        key: os.environ[key]
        for key in ("PATH", "VIRTUAL_ENV", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "LC_CTYPE", "TMPDIR")
        if key in os.environ
    }
    env.update(
        APP_NAME="howler",
        HWL_CONF_FOLDER=str(tmp_path),
        HWL_CLASSIFICATION_PATH=str(api_root / "build_scripts" / "classification.yml"),
        HWL_PLUGIN_DIRECTORY=str(plugins),
        PYTHONPATH=str(api_root),
        PYTHONSAFEPATH="1",
        PYTHONDONTWRITEBYTECODE="1",
        PYTHON_DOTENV_DISABLED="1",
        PYTHONUNBUFFERED="1",
    )
    script = r"""
from gevent.monkey import patch_all
patch_all()

import json
import sys
import time

import gevent
from gevent.event import Event
from redis import Redis

from howler.odm.models.config import AITriage, config
from howler.services import ai_triage_queue as queue
from howler.services import ai_triage_service as service
from howler.services import ai_triage_worker as worker

payload = json.loads(sys.argv[1])
client = Redis.from_url(payload["redis_url"], socket_connect_timeout=1)
queue.redis_client = lambda: client
queue._KEY_PREFIX = payload["prefix"]
config.core.ai = AITriage(
    enabled=True,
    endpoint="https://provider.invalid/triage",
    model="owner-scope-probe",
    lease_seconds=30,
    deadline_seconds=60,
    max_attempts=1,
    max_concurrent_jobs=2,
)
config.system.encryption_key = "0123456789abcdef0123456789abcdef"
service.is_available = lambda: True
service.notify_run = lambda *_args, **_kwargs: None
pause_started, release_pause, body_entered = Event(), Event(), Event()
processing_a, processing_b = Event(), Event()
run_a, run_b = "healthy-a", "paused-b"
paused_key = queue._run_lock_key(run_b)
root_owner_for_run = {}
original_set = client.set
paused = [False]


def paused_set(name, value, *args, **kwargs):
    result = original_set(name, value, *args, **kwargs)
    if name == paused_key and processing_b.is_set() and not paused[0]:
        paused[0] = True
        pause_started.set()
        release_pause.wait(timeout=8)
    return result


client.set = paused_set


def make_run(run_id):
    queue.create_run({
        "run_id": run_id,
        "operation_id": "ai_triage",
        "request_id": None,
        "action_id": None,
        "trigger": None,
        "state": "queued",
        "revision": 0,
        "created_at": "2026-01-01T00:00:00Z",
        "started_at": None,
        "updated_at": "2026-01-01T00:00:00Z",
        "finished_at": None,
        "expires_at": None,
        "counts": {},
        "results": [{
            "hit_id": f"{run_id}-hit",
            "state": "queued",
            "attempts": 0,
            "reason": None,
            "message": None,
            "started_at": None,
            "finished_at": None,
            "_deadline_at": None,
        }],
        "_owner": "owner-scope-probe",
        "_expires_at": None,
        "_created_at_epoch": time.time(),
    })


def process(job):
    bound_owner = queue.current_lock_cleanup_owner()
    assert bound_owner is not None and bound_owner.parent is not None
    root_owner_for_run[job["run_id"]] = bound_owner.parent
    if job["run_id"] == run_a:
        processing_a.set()
        assert pause_started.wait(timeout=8), "peer did not reach the Redis SET barrier"
        return
    if job["run_id"] == run_b:
        processing_b.set()
        with queue._locked(client, paused_key):
            body_entered.set()
        return
    raise AssertionError(f"unexpected claimed run: {job['run_id']}")


worker._process = process
make_run(run_a)
make_run(run_b)
assert worker.start_workers()
assert processing_a.wait(timeout=3) and processing_b.wait(timeout=3)
assert pause_started.wait(timeout=3), "peer SET did not reach the after-write barrier"

root_owner_a = root_owner_for_run[run_a]
root_owner_b = root_owner_for_run[run_b]
deadline = time.monotonic() + 3
while root_owner_a.children and time.monotonic() < deadline:
    gevent.sleep(0.01)
assert not root_owner_a.children, "healthy job A did not complete its own cleanup scope"
assert queue.pending_lock_helpers(root_owner_a) == ()
assert queue.pending_lock_cleanup_failure(root_owner_a) is None
assert queue.pending_lock_helpers(root_owner_b), "paused peer helper was not retained by its root"
root_a = next(root for root in worker._workers if worker._worker_cleanup_owners[root] is root_owner_a)
root_b = next(root for root in worker._workers if worker._worker_cleanup_owners[root] is root_owner_b)
assert not root_a.ready() and not root_b.ready()
assert not body_entered.is_set()
assert worker._stopping is False and not worker._stop_event.is_set(), "peer I/O stopped a healthy worker pool"

release_pause.set()
deadline = time.monotonic() + 3
while not body_entered.is_set() and time.monotonic() < deadline:
    gevent.sleep(0.01)
assert body_entered.is_set()
worker.stop_workers(timeout=3)
assert not worker._worker_cleanup_owners
assert not queue.pending_lock_helpers()
assert queue.pending_lock_cleanup_failure() is None

# An actual nonce cleanup failure remains fail-closed for its owning scope,
# while it does not turn an unrelated ordinary queue acquire into worker failure.
failure_owner = queue.new_lock_cleanup_owner()
failure_key = f"{payload['prefix']}:owned-cleanup-failure"
original_eval = client.eval


def failed_eval(*_args, **_kwargs):
    raise RuntimeError("deliberate compare-delete failure")


client.eval = failed_eval
try:
    with queue.bind_lock_cleanup_owner(failure_owner):
        try:
            with queue._locked(client, failure_key):
                pass
        except queue.LockCleanupError:
            pass
        else:
            raise AssertionError("the failed owner reported successful cleanup")
finally:
    client.eval = original_eval

assert queue.pending_lock_cleanup_failure(failure_owner)
with queue.bind_lock_cleanup_owner(failure_owner):
    try:
        with queue._locked(client, f"{payload['prefix']}:owned-followup"):
            pass
    except queue.LockCleanupError:
        pass
    else:
        raise AssertionError("a scope with incomplete nonce cleanup accepted more Redis work")
with queue._locked(client, f"{payload['prefix']}:unrelated-request"):
    pass
assert client.get(failure_key) is not None, "failed owner nonce should remain fail-closed"
client.delete(failure_key)

# Failure to create the release helper after a successful SET is itself an
# incomplete cleanup result and must remain owned/fail-closed.
start_failure_owner = queue.new_lock_cleanup_owner()
start_failure_key = f"{payload['prefix']}:release-helper-start-failure"
original_helper_start = queue._start_lock_helper
start_calls = [0]


def fail_release_helper_start(operation, owner):
    start_calls[0] += 1
    if start_calls[0] == 2:
        raise RuntimeError("deliberate release-helper start failure")
    return original_helper_start(operation, owner)


queue._start_lock_helper = fail_release_helper_start
try:
    with queue.bind_lock_cleanup_owner(start_failure_owner):
        try:
            with queue._locked(client, start_failure_key):
                pass
        except queue.LockCleanupError:
            pass
        else:
            raise AssertionError("release-helper start failure was reported as successful cleanup")
finally:
    queue._start_lock_helper = original_helper_start

assert queue.pending_lock_cleanup_failure(start_failure_owner)
with queue.bind_lock_cleanup_owner(start_failure_owner):
    try:
        with queue._locked(client, f"{payload['prefix']}:start-failure-followup"):
            pass
    except queue.LockCleanupError:
        pass
    else:
        raise AssertionError("a scope with unstarted nonce cleanup accepted more Redis work")
start_failure_token = client.get(start_failure_key)
assert start_failure_token is not None
original_eval(queue._LOCK_RELEASE_SCRIPT, 1, start_failure_key, start_failure_token)
sys.stdout.write("QA_OWNER_SCOPES_OK\n")
client.close()
"""
    payload = {
        "redis_url": os.environ.get("AI_TRIAGE_TEST_REDIS_URL", "redis://127.0.0.1:16389/15"),
        "prefix": f"howler.ai_triage.owner-r4:{{{uuid.uuid4().hex}}}",
    }
    result = subprocess.run(
        [sys.executable, "-c", script, json.dumps(payload)],
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "QA_OWNER_SCOPES_OK" in result.stdout


def test_real_redis_a2a_checkpoint_cancellation_closes_http_before_lease_reuse(tmp_path):  # noqa: C901
    """A blocked real checkpoint may outlive HTTP, but never lease recovery."""
    api_root = Path(__file__).parents[2]
    settings = {
        "ui": {"debug": False, "audit": False},
        "auth": {"oauth": {"enabled": False}},
        "core": {
            "ai": {"enabled": False},
            "plugins": [],
            "telemetry": {"enabled": False},
            "redis": {kind: {"host": "127.0.0.1", "port": 16389} for kind in ("persistent", "nonpersistent")},
        },
        "system": {
            "encryption_key": "0123456789abcdef0123456789abcdef",
            **{name: {"enabled": False} for name in ("action_queue", "correlation", "retention", "view_cleanup")},
        },
        "datastore": {"hosts": [{"name": "a2a-lifecycle-probe", "scheme": "http", "host": "127.0.0.1:19289"}]},
    }
    (tmp_path / "config.yml").write_text(json.dumps(settings))
    (tmp_path / "classification.yml").write_text((api_root / "build_scripts" / "classification.yml").read_text())
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    env = {
        key: os.environ[key]
        for key in ("PATH", "VIRTUAL_ENV", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "LC_CTYPE", "TMPDIR")
        if key in os.environ
    }
    env.update(
        APP_NAME="howler",
        HWL_CONF_FOLDER=str(tmp_path),
        HWL_CLASSIFICATION_PATH=str(api_root / "build_scripts" / "classification.yml"),
        HWL_PLUGIN_DIRECTORY=str(plugins),
        PYTHONPATH=str(api_root),
        PYTHONSAFEPATH="1",
        PYTHONDONTWRITEBYTECODE="1",
        PYTHON_DOTENV_DISABLED="1",
        PYTHONUNBUFFERED="1",
    )
    script = r"""
from gevent.monkey import patch_all
patch_all()

import json
import sys
import time
from types import SimpleNamespace

import gevent
import requests
from gevent.event import Event
from gevent.pywsgi import WSGIServer
from redis import Redis

from howler.odm.models.config import AITriage
from howler.odm.models.config import config
from howler.services import ai_transport, ai_triage_queue as queue
from howler.services import ai_triage_service as service
from howler.services import ai_triage_worker as worker

payload = json.loads(sys.argv[1])
client = Redis.from_url(payload["redis_url"], socket_connect_timeout=1)
queue.redis_client = lambda: client
queue._KEY_PREFIX = payload["prefix"]
queue.QUEUE_LOCK_TTL = 1.2
queue.QUEUE_LOCK_ACQUIRE_TIMEOUT = 5.0
request_seen, release_server, checkpoint_paused, release_checkpoint = Event(), Event(), Event(), Event()
checkpoint_body_ran = Event()
response_closed, session_closed = Event(), Event()
response_closed_at = [None]
session_closed_at = [None]
original_set = client.set
original_save_run = queue._save_run
pause_once = [False]
socket_handles = []


def app(environ, start_response):
    request_seen.set()
    request = json.loads(environ["wsgi.input"].read(int(environ.get("CONTENT_LENGTH", "0"))))
    result = {
        "kind": "task",
        "id": "accepted-task-1",
        "contextId": "accepted-context-1",
        "status": {"state": "working"},
        "metadata": {"padding": "x" * 9000},
    }
    event = {"jsonrpc": "2.0", "id": request["id"], "result": result}
    prefix = b"data:" + json.dumps(event, separators=(",", ":")).encode("utf-8")
    # A full 16 KiB SSE frame guarantees the real requests iterator yields the
    # complete accepted task before asking the server for another body chunk.
    frame = prefix + b" " * (16384 - len(prefix) - 2) + b"\n\n"
    terminal = (
        b"data:"
        + json.dumps(
            {
                "jsonrpc": "2.0",
                "id": request["id"],
                "result": {
                    "kind": "task",
                    "id": "accepted-task-1",
                    "contextId": "accepted-context-1",
                    "status": {"state": "completed"},
                    "artifacts": [{"parts": [{"kind": "text", "text": "finished"}]}],
                },
            },
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n\n"
    )
    start_response(
        "200 OK",
        [("Content-Type", "text/event-stream"), ("Content-Length", str(len(frame) + len(terminal)))],
    )

    def body():
        yield frame
        release_server.wait(timeout=8)
        yield terminal

    return body()


server = WSGIServer(("127.0.0.1", 0), app)
server.start()
run_id = "a2a-checkpoint-run"
run_lock_key = queue._run_lock_key(run_id)


def paused_set(name, value, *args, **kwargs):
    result = original_set(name, value, *args, **kwargs)
    if name == run_lock_key and request_seen.is_set() and not pause_once[0]:
        pause_once[0] = True
        checkpoint_paused.set()
        release_checkpoint.wait(timeout=8)
    return result


client.set = paused_set


def observed_save_run(redis_client, current_run, pipeline=None):
    result = current_run.get("results", [{}])[0]
    if current_run.get("run_id") == run_id and result.get("_a2a_task_id") == "accepted-task-1":
        checkpoint_body_ran.set()
    return original_save_run(redis_client, current_run, pipeline)


queue._save_run = observed_save_run
config.core.ai = AITriage(
    enabled=True,
    provider="a2a",
    endpoint=f"http://127.0.0.1:{server.server_port}/",
    model=None,
    timeout_seconds=30,
    deadline_seconds=20,
    lease_seconds=1,
    max_attempts=3,
    max_concurrent_jobs=1,
)
config.system.encryption_key = "0123456789abcdef0123456789abcdef"
user = SimpleNamespace(uname="alice", type=["automation_basic"], is_active=True, classification=None)
hit = SimpleNamespace(
    classification=None,
    howler=SimpleNamespace(id="hit-0", status="open", assessment=None, dossier=[]),
)
service.is_available = lambda: True
service.run_owner_and_token = lambda _run: (user, "trusted-token", queue.read_run(run_id))
service.user_can_run_ai_triage = lambda _user: True
service.get_current_user = lambda _run: user
service.get_current_hit = lambda *_args: (hit, "source-version")
service._eligible_hit = lambda _hit: True
service.build_system_prompt = lambda _prompt: "system"
service.provider_input = lambda _hit: {"howler": {"id": "hit-0"}}
service.has_managed_candidate = lambda *_args: False
service.notify_run = lambda *_args, **_kwargs: None


class TrackingSession(requests.Session):
    def __init__(self):
        super().__init__()
        self.trust_env = False

    def post(self, *args, **kwargs):
        response = super().post(*args, **kwargs)
        sock = None
        try:
            sock = response.raw._fp.fp.raw._sock
        except AttributeError:
            connection = getattr(response.raw, "_connection", None)
            sock = getattr(connection, "sock", None)
        socket_handles.append(sock)
        close = response.close

        def tracked_close():
            try:
                close()
            finally:
                response_closed_at[0] = time.time()
                response_closed.set()

        response.close = tracked_close
        return response

    def close(self):
        session_closed_at[0] = time.time()
        session_closed.set()
        super().close()


session = TrackingSession()
ai_transport._session = lambda: session
run = {
    "run_id": run_id,
    "operation_id": "ai_triage",
    "request_id": None,
    "action_id": None,
    "trigger": None,
    "state": "queued",
    "revision": 0,
    "created_at": "2026-01-01T00:00:00Z",
    "started_at": None,
    "updated_at": "2026-01-01T00:00:00Z",
    "finished_at": None,
    "expires_at": None,
    "counts": {},
    "results": [{
        "hit_id": "hit-0",
        "state": "queued",
        "attempts": 0,
        "reason": None,
        "message": None,
        "started_at": None,
        "finished_at": None,
        "_deadline_at": None,
    }],
    "_owner": "alice",
    "_expires_at": None,
    "_created_at_epoch": time.time(),
    "_encrypted_bearer_token": "unused",
    "_auth_scheme": "Bearer",
}
queue.create_run(run)
assert worker.start_workers()
assert checkpoint_paused.wait(timeout=5), "accepted A2A checkpoint SET did not pause"
assert request_seen.is_set()
assert len(socket_handles) == 1 and socket_handles[0] is not None
assert not response_closed.is_set() and not session_closed.is_set()
assert not checkpoint_body_ran.is_set(), "checkpoint body ran before the SET barrier was released"

root = worker._workers[0]
root_children = worker._worker_children.get(root, set())
processing = next(child for child in root_children if child._run.__name__ == "_process_with_lock_owner")
process_owner = processing.args[0]
assert queue.pending_lock_helpers(process_owner), "paused acquire helper is missing from its job owner"
old_nonce = queue.read_run(run_id)["results"][0]["_lease_nonce"]
lease_member = queue._lease_member(run_id, 0, old_nonce)
lease_expiry = float(client.zscore(queue._lease_key(), lease_member))
assert lease_expiry > time.time(), "the probe must observe the still-live original lease"

# The real watchdog cannot renew through the paused per-run lock. It must cancel
# the provider stack before the one-second lease can be recovered/reallocated.
assert response_closed.wait(timeout=3), "watchdog cancellation left the response open"
assert session_closed.is_set(), "watchdog cancellation left the provider session open"
assert socket_handles[0].fileno() == -1, "watchdog cancellation left the provider socket open"
assert response_closed_at[0] < lease_expiry, "HTTP response closed only after the original lease expired"
assert session_closed_at[0] < lease_expiry, "provider session closed only after the original lease expired"
callback_owner = next(scope for scope in process_owner.children if scope.cancelled)
assert callback_owner.cancelled, "the callback owner was not marked canceled before HTTP unwind"
while time.time() <= lease_expiry:
    gevent.sleep(0.01)

# At this point the actual lease is expired while the callback child and its
# Redis helper are still owned. claim_next performs real recovery; the expired
# run-lock TTL is allowed to elapse rather than remotely killing the provider.
assert not processing.ready(), "callback cleanup unexpectedly outlived its owned handle"
assert queue.pending_lock_helpers(process_owner)
replacement, _recovered = queue.claim_next()
assert replacement is not None and replacement["run_id"] == run_id
assert replacement["nonce"] != old_nonce
new_nonce = replacement["nonce"]
assert response_closed.is_set() and session_closed.is_set() and socket_handles[0].fileno() == -1
assert not checkpoint_body_ran.is_set()
assert not queue.read_run(run_id)["results"][0].get("_a2a_task_id")
assert any(not child.ready() for child in worker._worker_children.get(processing, set()))

# Exercise root-stop plus repeated cancellation while the callback is still
# draining. The second kill must not restart its nonce cleanup deadline.
stopper = gevent.spawn(worker.stop_workers, 4)
gevent.sleep(0)
root.kill(block=False)
gevent.sleep(0)
assert not root.ready()
release_server.set()
# The pause callback waits on this same Event; set it after the root has observed
# its second cancellation so the deferred acquisition/release chain can finish.
release_checkpoint.set()
stopper.get(timeout=6)
assert worker._workers == [] and worker._started is False
assert not queue.pending_lock_helpers(process_owner)
assert not checkpoint_body_ran.is_set()
assert queue.lease_is_current(run_id, 0, new_nonce), "old callback cleanup overwrote the replacement lease nonce"
assert client.get(run_lock_key) is None
sys.stdout.write("QA_A2A_HTTP_UNWIND_BEFORE_RECLAIM_OK\n")

try:
    server.stop(timeout=1)
finally:
    session.close()
    keys = list(client.scan_iter(match=f"{payload['prefix']}:*"))
    if keys:
        client.delete(*keys)
    client.close()
"""
    payload = {
        "redis_url": os.environ.get("AI_TRIAGE_TEST_REDIS_URL", "redis://127.0.0.1:16389/15"),
        "prefix": f"howler.ai_triage.a2a-r4:{{{uuid.uuid4().hex}}}",
    }
    result = subprocess.run(
        [sys.executable, "-c", script, json.dumps(payload)],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "QA_A2A_HTTP_UNWIND_BEFORE_RECLAIM_OK" in result.stdout


def test_expired_lock_owner_cannot_commit_a_fenced_redis_transaction(queue_backend):
    client, _now = queue_backend
    lock_key = ai_triage_queue._global_lock_key()

    with pytest.raises(redis.exceptions.WatchError):
        with ai_triage_queue._locked(client, lock_key):
            with ai_triage_queue._fenced_pipeline(client) as pipeline:
                pipeline.set("fenced-write", "stale-owner")
                client.values[lock_key] = b"new-owner-token"
                pipeline.execute()

    assert client.get("fenced-write") is None


def test_real_redis_paused_claim_cannot_exceed_four_global_permits(monkeypatch):
    port = int(os.environ.get("AI_TRIAGE_TEST_REDIS_PORT", "16389"))
    client = redis.Redis(host="127.0.0.1", port=port)
    try:
        client.ping()
    except redis.exceptions.RedisError:
        pytest.skip(f"isolated Redis is not available on port {port}")

    key_tag = f"ai-triage-review-{uuid.uuid4().hex}"
    prefix = f"howler.ai_triage:{{{key_tag}}}"
    monkeypatch.setattr(ai_triage_queue, "_KEY_PREFIX", prefix)
    monkeypatch.setattr(ai_triage_queue, "redis_client", lambda: client)
    monkeypatch.setattr(
        ai_triage_queue.config.core,
        "ai",
        AITriage(
            enabled=True,
            endpoint="https://provider.example.invalid/chat",
            model="model",
            lease_seconds=30,
            deadline_seconds=600,
            max_attempts=3,
            max_concurrent_jobs=4,
            retention_seconds=60,
        ),
    )
    for index in range(5):
        ai_triage_queue.create_run(_run(run_id=f"{key_tag}-{index}"))
    active = [ai_triage_queue.claim_next()[0] for _ in range(3)]
    assert all(active)

    pending = client.lindex(ai_triage_queue._queue_key(), 0)
    target_run_id = json.loads(pending)[0]
    original_load = ai_triage_queue._load_run
    paused = threading.Event()
    resume = threading.Event()
    stale_thread_id = [None]
    paused_once = [False]
    errors = []

    def pause_claim_load(redis_client, run_id):
        run = original_load(redis_client, run_id)
        if run_id == target_run_id and threading.get_ident() == stale_thread_id[0] and not paused_once[0]:
            paused_once[0] = True
            paused.set()
            resume.wait(timeout=3)
        return run

    monkeypatch.setattr(ai_triage_queue, "_load_run", pause_claim_load)
    monkeypatch.setattr(ai_triage_queue, "QUEUE_LOCK_TTL", 0.15)

    def stale_claim():
        stale_thread_id[0] = threading.get_ident()
        try:
            ai_triage_queue.claim_next()
        except Exception as exc:  # the expired fencing token must abort its transaction
            errors.append(exc)

    paused_worker = threading.Thread(target=stale_claim, daemon=True)
    paused_worker.start()
    assert paused.wait(timeout=2)
    time.sleep(0.25)
    fourth, _ = ai_triage_queue.claim_next()
    assert fourth is not None
    resume.set()
    paused_worker.join(timeout=2)

    assert not paused_worker.is_alive()
    assert errors and isinstance(errors[0], redis.exceptions.WatchError)
    assert client.zcard(ai_triage_queue._lease_key()) == 4
    assert ai_triage_queue.claim_next()[0] is None

    for job in [*active, fourth]:
        ai_triage_queue.finish_item(job["run_id"], job["index"], job["nonce"], state="succeeded")

    ai_triage_queue.create_run(_run(run_id=f"{key_tag}-recovery"))
    stale_job, _ = ai_triage_queue.claim_next()
    member = ai_triage_queue._lease_member(stale_job["run_id"], stale_job["index"], stale_job["nonce"])
    client.zadd(ai_triage_queue._lease_key(), {member: time.time() + 0.05})
    time.sleep(0.1)
    resumed_job, _ = ai_triage_queue.claim_next()
    assert resumed_job is not None
    assert resumed_job["nonce"] != stale_job["nonce"]
    assert ai_triage_queue.lease_is_current(stale_job["run_id"], stale_job["index"], stale_job["nonce"]) is False
    assert (
        ai_triage_queue.store_candidate(
            stale_job["run_id"],
            stale_job["index"],
            stale_job["nonce"],
            ai_triage_service.prepare_candidate("stale", stale_job["run_id"], "stale-version"),
        )
        is False
    )
    ai_triage_queue.finish_item(resumed_job["run_id"], resumed_job["index"], resumed_job["nonce"], state="succeeded")

    keys = client.keys(f"{prefix}:*")
    if keys:
        client.delete(*keys)
    client.close()


def test_expired_lease_recovers_attempt_and_run_deadline_is_absolute(queue_backend):
    _redis, now = queue_backend
    ai_triage_queue.create_run(_run())
    first, _ = ai_triage_queue.claim_next()
    ai_triage_queue.begin_provider_attempt(first["run_id"], first["index"], first["nonce"])
    now[0] = 104
    recovered_job, recovered = ai_triage_queue.claim_next()
    assert recovered_job["attempts"] == 1
    assert recovered_job["nonce"] != first["nonce"]
    assert recovered

    now[0] = 111
    job, recovered = ai_triage_queue.claim_next()
    assert job is None
    completed = recovered[-1]
    assert completed["results"][0]["state"] == "failed"
    assert completed["results"][0]["reason"] == "run_deadline_exceeded"


def test_each_alert_deadline_begins_on_its_own_first_claim(queue_backend):
    _redis, now = queue_backend
    ai_triage_queue.create_run(_run(targets=2))
    first, _ = ai_triage_queue.claim_next()
    assert ai_triage_queue.begin_provider_attempt(first["run_id"], first["index"], first["nonce"])
    first_deadline = first["deadline_at"]
    ai_triage_queue.finish_item(first["run_id"], first["index"], first["nonce"], state="succeeded")

    now[0] = 105
    second, _ = ai_triage_queue.claim_next()
    assert second["deadline_at"] == pytest.approx(first_deadline + 5)
    persisted = ai_triage_queue.read_run(second["run_id"])
    assert persisted["results"][0]["_deadline_at"] == pytest.approx(first_deadline)
    assert persisted["results"][1]["_deadline_at"] == pytest.approx(second["deadline_at"])
    assert "_deadline_at" not in persisted
    ai_triage_queue.finish_item(second["run_id"], second["index"], second["nonce"], state="succeeded")


def test_only_transient_errors_retry_and_attempts_are_bounded(queue_backend):
    ai_triage_queue.create_run(_run())
    first, _ = ai_triage_queue.claim_next()
    ai_triage_queue.begin_provider_attempt(first["run_id"], first["index"], first["nonce"])
    retry = ai_triage_queue.finish_item(
        first["run_id"],
        first["index"],
        first["nonce"],
        state="failed",
        reason="provider_transient_error",
        transient=True,
    )
    assert retry["results"][0]["state"] == "queued"
    second, _ = ai_triage_queue.claim_next()
    assert second["attempts"] == 1
    ai_triage_queue.begin_provider_attempt(second["run_id"], second["index"], second["nonce"])
    failed = ai_triage_queue.finish_item(
        second["run_id"],
        second["index"],
        second["nonce"],
        state="failed",
        reason="provider_transient_error",
        transient=True,
    )
    assert failed["results"][0]["state"] == "failed"
    assert failed["results"][0]["attempts"] == 2


def test_provider_attempt_counter_changes_only_when_generation_begins(queue_backend):
    ai_triage_queue.create_run(_run())
    first, _ = ai_triage_queue.claim_next()
    assert first["attempts"] == 0
    started = ai_triage_queue.begin_provider_attempt(first["run_id"], first["index"], first["nonce"])
    assert started["attempts"] == 1
    retry = ai_triage_queue.finish_item(
        first["run_id"],
        first["index"],
        first["nonce"],
        state="failed",
        reason="temporary",
        transient=True,
    )
    assert retry["results"][0]["attempts"] == 1
    second, _ = ai_triage_queue.claim_next()
    assert second["attempts"] == 1
    assert ai_triage_queue.begin_provider_attempt(second["run_id"], second["index"], second["nonce"])["attempts"] == 2
    assert ai_triage_queue.checkpoint(second["run_id"], second["index"], second["nonce"], "a2a-task", "a2a-context")
    assert ai_triage_queue.begin_provider_attempt(second["run_id"], second["index"], second["nonce"]) is None


def test_ambiguous_commit_releases_provider_permit_and_expires_truthfully(queue_backend):
    redis, now = queue_backend
    ai_triage_queue.create_run(_run())
    job, _ = ai_triage_queue.claim_next()
    assert ai_triage_queue.begin_provider_attempt(job["run_id"], job["index"], job["nonce"])
    candidate = ai_triage_service.prepare_candidate("same canonical candidate", job["run_id"], "source-v1")
    assert ai_triage_queue.store_candidate(job["run_id"], job["index"], job["nonce"], candidate)
    assert ai_triage_queue.set_commit_phase(job["run_id"], job["index"], job["nonce"], "write_pending")

    pending = ai_triage_queue.defer_candidate_reconciliation(job["run_id"], job["index"], job["nonce"])
    assert pending["results"][0]["reason"] == "write_reconciliation_pending"
    assert pending["results"][0]["state"] == "running"
    assert pending["results"][0]["_candidate"] == candidate
    assert redis.zcard(ai_triage_queue._lease_key()) == 0
    assert redis.zcard(ai_triage_queue._reconcile_due_key()) == 1

    now[0] = 161
    recovered, changed = ai_triage_queue.claim_reconciliation()
    assert recovered is None
    terminal = changed[-1]
    assert terminal["state"] == "completed"
    assert terminal["results"][0]["state"] == "failed"
    assert terminal["results"][0]["reason"] == "write_outcome_unknown"
    assert "may have been replaced" in terminal["results"][0]["message"]


def test_third_generation_attempt_recovers_saved_candidate_without_fourth_request(queue_backend, monkeypatch):
    _redis, now = queue_backend
    monkeypatch.setattr(ai_triage_queue.config.core.ai, "max_attempts", 3)
    ai_triage_queue.create_run(_run())

    for attempt_number in (1, 2):
        job, _ = ai_triage_queue.claim_next()
        started = ai_triage_queue.begin_provider_attempt(job["run_id"], job["index"], job["nonce"])
        assert started["attempts"] == attempt_number
        ai_triage_queue.finish_item(
            job["run_id"],
            job["index"],
            job["nonce"],
            state="failed",
            reason="provider_transient_error",
            transient=True,
        )

    final_attempt, _ = ai_triage_queue.claim_next()
    assert (
        ai_triage_queue.begin_provider_attempt(final_attempt["run_id"], final_attempt["index"], final_attempt["nonce"])[
            "attempts"
        ]
        == 3
    )
    candidate = ai_triage_service.prepare_candidate("committed final answer", final_attempt["run_id"], "v3")
    assert ai_triage_queue.store_candidate(
        final_attempt["run_id"], final_attempt["index"], final_attempt["nonce"], candidate
    )
    assert ai_triage_queue.set_commit_phase(
        final_attempt["run_id"], final_attempt["index"], final_attempt["nonce"], "write_pending"
    )

    user = SimpleNamespace(uname="alice", type=["automation_basic"], is_active=True)
    lead = ai_triage_service.Lead(
        {
            "label": candidate["label"],
            "format": candidate["format"],
            "content": candidate["content"],
            "metadata": candidate["metadata"],
        }
    )
    saved_hit = SimpleNamespace(
        classification=None,
        howler=SimpleNamespace(id="hit-0", status="open", assessment=None, dossier=[lead]),
    )
    save = MagicMock(side_effect=AssertionError("an already-saved candidate must not be written again"))
    monkeypatch.setattr(ai_triage_service, "get_current_hit", lambda _id, _user: (saved_hit, "v4"))
    monkeypatch.setattr(ai_triage_service, "datastore", lambda: SimpleNamespace(hit=SimpleNamespace(save=save)))

    now[0] = 104
    reconciliation, _changed = ai_triage_queue.claim_reconciliation()
    assert reconciliation is not None
    assert reconciliation["candidate"] == candidate
    assert reconciliation["run"]["results"][0]["attempts"] == 3
    state, reason = ai_triage_service.reconcile_candidate(
        "hit-0",
        candidate,
        user_loader=lambda: user,
        lease_check=lambda: ai_triage_queue.reconciliation_is_current(
            reconciliation["run_id"], reconciliation["index"], reconciliation["nonce"]
        ),
        write_intent_check=lambda: ai_triage_queue.mark_reconciliation_write_intent(
            reconciliation["run_id"], reconciliation["index"], reconciliation["nonce"]
        ),
        allow_write=True,
        write_intent=True,
        active_deadline=time.monotonic() + max(0, reconciliation["deadline_at"] - ai_triage_queue._now()),
    )
    assert (state, reason) == ("saved", None)
    completed = ai_triage_queue.finish_reconciliation(
        reconciliation["run_id"], reconciliation["index"], reconciliation["nonce"], state="succeeded"
    )
    assert completed["results"][0]["attempts"] == 3
    save.assert_not_called()


def test_validated_candidate_is_reused_after_worker_recovery(queue_backend):
    _redis, now = queue_backend
    ai_triage_queue.create_run(_run())
    first, _ = ai_triage_queue.claim_next()
    assert ai_triage_queue.store_candidate(
        first["run_id"],
        first["index"],
        first["nonce"],
        ai_triage_service.prepare_candidate("validated answer", first["run_id"], "source-v1"),
    )
    original_candidate = ai_triage_queue.read_run(first["run_id"])["results"][first["index"]]["_candidate"]
    assert (
        ai_triage_queue.store_candidate(
            first["run_id"],
            first["index"],
            first["nonce"],
            ai_triage_service.prepare_candidate("replacement must not win", first["run_id"], "source-v2"),
        )
        is False
    )
    assert ai_triage_queue.read_run(first["run_id"])["results"][first["index"]]["_candidate"] == original_candidate

    now[0] = 104
    second, _ = ai_triage_queue.claim_reconciliation()
    assert second["run"]["results"][second["index"]]["attempts"] == 0
    assert second["candidate"]["content"] == "validated answer"
    assert (
        ai_triage_queue.store_candidate(
            first["run_id"],
            first["index"],
            first["nonce"],
            ai_triage_service.prepare_candidate("stale candidate", first["run_id"], "source-v0"),
        )
        is False
    )
    assert second["candidate"]["source_version"] == "source-v1"


@pytest.mark.parametrize("use_gevent", [True, False])
def test_worker_startup_dispatches_gevent_and_rejects_native_provider_execution(queue_backend, monkeypatch, use_gevent):
    import threading

    ai_triage_worker.stop_workers(timeout=2)
    ai_triage_queue.create_run(_run())
    processed = threading.Event()
    monkeypatch.setattr(ai_triage_worker.ai_triage_service, "is_available", lambda: True)
    monkeypatch.setattr(ai_triage_worker, "_process", lambda _job: processed.set())
    monkeypatch.setattr(ai_triage_worker.monkey, "is_module_patched", lambda _module: use_gevent)

    if not use_gevent:
        with pytest.raises(RuntimeError, match="early-gevent-patched"):
            ai_triage_worker.start_workers()
        assert not processed.is_set()
        return

    try:
        assert ai_triage_worker.start_workers()
        deadline = time.monotonic() + 2
        while not processed.is_set() and time.monotonic() < deadline:
            gevent.sleep(0.01)
        assert processed.is_set()
    finally:
        ai_triage_worker.stop_workers(timeout=2)


def test_configured_ai_fails_fast_on_unpatched_serving_runtime(monkeypatch):
    ai_triage_worker.stop_workers(timeout=2)
    monkeypatch.setattr(ai_triage_worker.config.core.ai, "enabled", True)
    monkeypatch.setattr(ai_triage_worker.monkey, "is_module_patched", lambda _module: False)

    with pytest.raises(RuntimeError, match="early-gevent-patched"):
        ai_triage_worker.start_workers()
    assert ai_triage_worker._started is False


def test_watchdog_cancels_provider_when_redis_renewal_misses_lease_margin(monkeypatch):
    monkeypatch.setattr(ai_triage_worker.config.core.ai, "lease_seconds", 0.5)
    monkeypatch.setattr(ai_triage_queue, "heartbeat", lambda *_args: gevent.sleep(1.0))
    cleanup = threading.Event()

    def blocked_provider():
        try:
            gevent.sleep(10)
        finally:
            cleanup.set()

    now = time.time()
    processing = gevent.spawn(blocked_provider)
    watchdog = gevent.spawn(
        ai_triage_worker._heartbeat_loop,
        "run-1",
        0,
        "nonce",
        now + 0.16,
        now + 2,
        processing,
    )
    watchdog.join(timeout=1)
    processing.join(timeout=1)

    assert watchdog.ready()
    assert processing.ready()
    assert cleanup.is_set()


def test_disabled_worker_reconciles_pending_runs_without_provider_calls(queue_backend, monkeypatch):
    import threading

    ai_triage_worker.stop_workers(timeout=2)
    _redis, _now = queue_backend
    monkeypatch.setattr(ai_triage_worker.config.core.ai, "enabled", False)
    run = ai_triage_queue.create_run(_run())
    reconciled = threading.Event()
    monkeypatch.setattr(ai_triage_worker.ai_triage_service, "is_available", lambda: False)
    generate = MagicMock(side_effect=AssertionError("provider must not run"))
    monkeypatch.setattr(ai_transport, "generate", generate)
    monkeypatch.setattr(ai_triage_worker.ai_triage_service, "notify_run", lambda _changed: reconciled.set())
    monkeypatch.setattr(ai_triage_worker.monkey, "is_module_patched", lambda _module: False)

    try:
        assert ai_triage_worker.start_workers()
        assert reconciled.wait(timeout=2)
        completed = ai_triage_queue.read_run(run["run_id"])
        assert completed["state"] == "completed"
        assert completed["results"][0]["reason"] == "configuration_unavailable"
        generate.assert_not_called()
    finally:
        ai_triage_worker.stop_workers(timeout=2)


def test_disabled_reconciler_stays_alive_for_late_peer_enqueue(queue_backend, monkeypatch):
    import threading

    ai_triage_worker.stop_workers(timeout=2)
    ai_triage_worker._use_gevent = False
    monkeypatch.setattr(ai_triage_worker.config.core.ai, "enabled", False)
    reconciled = threading.Event()
    monkeypatch.setattr(ai_triage_worker.ai_triage_service, "is_available", lambda: False)
    monkeypatch.setattr(ai_triage_worker.ai_triage_service, "notify_run", lambda _run: reconciled.set())
    generate = MagicMock(side_effect=AssertionError("provider must not run"))
    monkeypatch.setattr(ai_transport, "generate", generate)

    try:
        assert ai_triage_worker.start_workers()
        time.sleep(0.05)
        run = ai_triage_queue.create_run(_run(run_id="late-peer-run"))
        assert reconciled.wait(timeout=2)
        terminal = ai_triage_queue.read_run(run["run_id"])
        assert terminal["state"] == "completed"
        assert terminal["results"][0]["reason"] == "configuration_unavailable"
        generate.assert_not_called()
    finally:
        ai_triage_worker.stop_workers(timeout=2)


def test_provider_headers_and_openai_envelope_reserve_security_fields():
    provider_config = _ai_config(
        headers={"X-Secret": "server-only", "Authorization": "spoof"}, extra_body={"stream": True}
    )
    headers = ai_transport._safe_headers(provider_config, "trusted-token")
    assert headers["Authorization"] == "Bearer trusted-token"
    assert headers["X-Secret"] == "server-only"
    assert provider_config.headers["Authorization"] == "spoof"
    assert headers["Authorization"] != "spoof"

    session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.iter_content.return_value = [
        b'{"choices":[{"message":{"role":"assistant","content":"summary"},"finish_reason":"stop"}]}'
    ]
    session.post.return_value = response
    text = ai_transport._openai_chat(
        session,
        provider_config,
        provider_config.endpoint,
        "trusted-token",
        "system",
        "{}",
        deadline=time.monotonic() + 10,
    )
    assert text == "summary"
    request_kwargs = session.post.call_args.kwargs
    assert request_kwargs["json"]["stream"] is False
    assert request_kwargs["json"]["model"] == "triage-model"
    assert request_kwargs["headers"]["Authorization"] == "Bearer trusted-token"
    assert request_kwargs["allow_redirects"] is False


@pytest.mark.parametrize(
    "choice",
    [
        {"message": {"role": "user", "content": "not assistant"}, "finish_reason": "stop"},
        {"message": {"role": "assistant", "content": "truncated"}, "finish_reason": "length"},
        {
            "message": {"role": "assistant", "content": "tool request", "tool_calls": [{"id": "call-1"}]},
            "finish_reason": "tool_calls",
        },
        {"message": {"role": "assistant", "content": "filtered"}, "finish_reason": "content_filter"},
    ],
)
def test_openai_rejects_noncompleted_or_tool_call_responses(choice):
    response = MagicMock()
    response.status_code = 200
    response.iter_content.return_value = [json.dumps({"choices": [choice]}).encode()]
    session = MagicMock()
    session.post.return_value = response

    with pytest.raises(ai_transport.AITransportError):
        ai_transport._openai_chat(
            session,
            _ai_config(),
            _ai_config().endpoint,
            "trusted-token",
            "system",
            "{}",
            deadline=time.monotonic() + 10,
        )


def test_a2a_requires_completed_task_text_and_persists_checkpoints(monkeypatch):
    events = [
        {
            "result": {
                "kind": "artifact-update",
                "taskId": "task-1",
                "contextId": "context-1",
                "artifact": {"artifactId": "answer", "parts": [{"kind": "text", "text": "Conservative summary"}]},
            }
        },
        {"result": {"kind": "status-update", "taskId": "task-1", "status": {"state": "completed"}}},
    ]
    response = MagicMock()
    response.status_code = 200
    response.headers = {"content-type": "text/event-stream"}
    session = MagicMock()

    def stream_response(_endpoint, *, json, **_kwargs):
        stream_events = [{"jsonrpc": "2.0", "id": json["id"], **event} for event in events]
        stream = b"".join(b"data:" + json_module.dumps(event).encode() + b"\n\n" for event in stream_events)
        response.iter_content.return_value = [stream]
        return response

    json_module = json
    session.post.side_effect = stream_response
    provider_config = _ai_config(provider="a2a", model=None)
    checkpoints = []
    monkeypatch.setattr(ai_transport, "_session", lambda: session)

    text = ai_transport.generate(
        provider_config,
        "trusted-token",
        "system",
        {"howler": {"id": "hit-1"}},
        deadline=time.monotonic() + 30,
        checkpoint=lambda task_id, context_id: checkpoints.append((task_id, context_id)),
    )
    assert text == "Conservative summary"
    assert ("task-1", "context-1") in checkpoints
    request = session.post.call_args
    assert request.kwargs["json"]["method"] == "message/stream"
    assert request.kwargs["allow_redirects"] is False
    assert request.kwargs["headers"]["Authorization"] == "Bearer trusted-token"

    with pytest.raises(ai_transport.AITransportError):
        ai_transport._extract_completed_text({"status": {"state": "input-required"}}, {})


def test_provider_callback_bridge_cancels_blocked_begin_attempt_before_http(monkeypatch):
    from gevent.event import Event

    callback_started, callback_finalized = Event(), Event()
    owner = ai_triage_queue.new_lock_cleanup_owner()
    bridge = ai_triage_worker._ProviderCallbackBridge(
        owner,
        lambda _task, _context: True,
        lambda: _blocking_callback(callback_started, callback_finalized),
    )
    session = MagicMock()
    monkeypatch.setattr(ai_transport, "_session", lambda: session)

    def generate():
        with ai_triage_queue.bind_lock_cleanup_owner(owner):
            try:
                try:
                    ai_transport.generate(
                        _ai_config(),
                        "trusted-token",
                        "system",
                        {"id": "hit-1"},
                        deadline=time.monotonic() + 30,
                        checkpoint=bridge.checkpoint,
                        begin_attempt=bridge.begin_attempt,
                    )
                finally:
                    bridge.drain_after_provider_unwind()
            except BaseException as exc:
                if not isinstance(exc, gevent.GreenletExit):
                    raise

    processing = gevent.spawn(generate)
    assert callback_started.wait(timeout=2)
    processing.kill(block=False)
    processing.join(timeout=2)

    assert processing.ready()
    assert callback_finalized.is_set()
    session.post.assert_not_called()
    session.close.assert_called_once()
    assert not ai_triage_queue.pending_lock_helpers(owner)


def _blocking_callback(started, finalized):
    from gevent.event import Event

    try:
        started.set()
        Event().wait(timeout=30)
    finally:
        finalized.set()


def test_provider_timeout_closes_a2a_http_before_draining_blocked_checkpoint(monkeypatch):
    from gevent.event import Event

    checkpoint_started, checkpoint_finalized = Event(), Event()
    owner = ai_triage_queue.new_lock_cleanup_owner()

    def blocked_checkpoint(_task_id, _context_id):
        return _blocking_callback(checkpoint_started, checkpoint_finalized)

    bridge = ai_triage_worker._ProviderCallbackBridge(owner, blocked_checkpoint, lambda: True)
    response = MagicMock()
    response.status_code = 200
    response.headers = {"content-type": "text/event-stream"}
    session = MagicMock()

    def stream_response(_endpoint, *, json, **_kwargs):
        event = {
            "jsonrpc": "2.0",
            "id": json["id"],
            "result": {
                "kind": "task",
                "id": "timeout-task",
                "contextId": "timeout-context",
                "status": {"state": "working"},
            },
        }
        response.iter_content.return_value = [b"data:" + json_module.dumps(event).encode() + b"\n\n"]
        return response

    json_module = json
    session.post.side_effect = stream_response
    monkeypatch.setattr(ai_transport, "_session", lambda: session)
    provider_config = _ai_config(provider="a2a", model=None, timeout_seconds=1)
    errors = []

    def process_provider():
        with ai_triage_queue.bind_lock_cleanup_owner(owner):
            try:
                try:
                    ai_transport.generate(
                        provider_config,
                        "trusted-token",
                        "system",
                        {"id": "hit-1"},
                        deadline=time.monotonic() + 10,
                        checkpoint=bridge.checkpoint,
                        begin_attempt=bridge.begin_attempt,
                    )
                finally:
                    bridge.drain_after_provider_unwind()
            except ai_transport.AITransportError as exc:
                errors.append(exc)

    processing = gevent.spawn(process_provider)
    assert checkpoint_started.wait(timeout=2)
    processing.join(timeout=3)

    assert processing.ready()
    assert errors and "provider timeout" in errors[0].reason.lower()
    assert checkpoint_finalized.is_set()
    response.close.assert_called_once()
    session.close.assert_called_once()
    assert not ai_triage_queue.pending_lock_helpers(owner)


def test_sse_slow_trickle_cannot_extend_the_absolute_deadline(monkeypatch):
    response = MagicMock()
    response.iter_content.return_value = [b": heartbeat\n", b": heartbeat\n"]
    clock = iter((0.0, 2.0))
    monkeypatch.setattr(ai_transport.time, "monotonic", lambda: next(clock))

    with pytest.raises(ai_transport.AITransportError, match="run deadline"):
        list(
            ai_transport._iter_sse_json(
                response,
                request_id="rpc-1",
                deadline=1.0,
                max_total_bytes=100,
                max_line_bytes=50,
            )
        )


def test_loopback_trickling_http_body_is_interrupted_and_response_closed():
    script = r"""
from gevent.monkey import patch_all
patch_all()

import time

import gevent
import requests
from gevent.pywsgi import WSGIServer

from howler.odm.models.config import AITriage
from howler.services import ai_transport


def app(_environ, start_response):
    start_response("200 OK", [("Content-Type", "application/json"), ("Content-Length", "16384")])

    def body():
        for _ in range(16384):
            yield b"x"
            gevent.sleep(0.002)

    return body()


server = WSGIServer(("127.0.0.1", 0), app)
server.start()
responses = []
session_closed = [False]


class TrackingSession(requests.Session):
    def __init__(self):
        super().__init__()
        self.trust_env = False

    def post(self, *args, **kwargs):
        response = super().post(*args, **kwargs)
        real_close = response.close

        def close():
            responses.append("closed")
            real_close()

        response.close = close
        responses.append(response)
        return response

    def close(self):
        session_closed[0] = True
        super().close()


session = TrackingSession()
ai_transport._session = lambda: session
provider_config = AITriage(
    enabled=True,
    provider="openai",
    endpoint=f"http://127.0.0.1:{server.server_port}/",
    model="trickle-test",
    timeout_seconds=30,
)
started = time.monotonic()
try:
    with gevent.Timeout(0.2, ai_transport.AITransportError("item deadline", transient=True)):
        ai_transport.generate(
            provider_config,
            "trusted-token",
            "system",
            {"alert": "data"},
            deadline=started + 30,
            checkpoint=lambda _task_id, _context_id: None,
        )
except ai_transport.AITransportError as error:
    assert error.reason == "item deadline"
else:
    raise AssertionError("trickling response outlived the outer deadline")
finally:
    server.stop(timeout=1)

assert time.monotonic() - started < 1
assert len(responses) == 2
assert session_closed[0]
"""
    subprocess.run([sys.executable, "-c", script], check=True, timeout=10)


def test_a2a_authentication_failure_does_not_fallback(monkeypatch):
    response = MagicMock()
    response.status_code = 401
    response.headers = {"content-type": "application/json"}
    session = MagicMock()
    session.post.return_value = response
    monkeypatch.setattr(ai_transport, "_session", lambda: session)

    with pytest.raises(ai_transport.AITransportError, match="rejected the authorization"):
        ai_transport.generate(
            _ai_config(provider="a2a", model=None),
            "trusted-token",
            "system",
            {"howler": {"id": "hit-1"}},
            deadline=time.monotonic() + 30,
            checkpoint=lambda _task_id, _context_id: None,
        )
    assert session.post.call_count == 1


def test_a2a_unsupported_error_after_task_acceptance_does_not_resubmit(monkeypatch):
    response = MagicMock()
    response.status_code = 200
    response.headers = {"content-type": "text/event-stream"}
    session = MagicMock()

    def post(_endpoint, **kwargs):
        request_body = kwargs["json"]
        events = [
            {
                "jsonrpc": "2.0",
                "id": request_body["id"],
                "result": {
                    "kind": "status-update",
                    "taskId": "accepted-task",
                    "contextId": "accepted-context",
                    "status": {"state": "working"},
                },
            },
            {
                "jsonrpc": "2.0",
                "id": request_body["id"],
                "error": {"code": -32601, "message": "unsupported"},
            },
        ]
        response.iter_content.return_value = [
            b"".join(b"data:" + json.dumps(event).encode() + b"\n\n" for event in events)
        ]
        return response

    session.post.side_effect = post
    monkeypatch.setattr(ai_transport, "_session", lambda: session)
    with pytest.raises(ai_transport.AITransportError, match="after a task was accepted"):
        ai_transport.generate(
            _ai_config(provider="a2a", model=None),
            "trusted-token",
            "system",
            {"alert": "data"},
            deadline=time.monotonic() + 30,
            checkpoint=lambda _task_id, _context_id: True,
        )
    assert session.post.call_count == 1


def test_a2a_fallback_and_recovery_resume_existing_task_without_resubmission(monkeypatch):
    calls = []

    def response(status, request_id=None, result=None, error=None):
        item = MagicMock()
        item.status_code = status
        item.headers = {"content-type": "application/json"}
        payload = {"jsonrpc": "2.0", "id": request_id}
        if result is not None:
            payload["result"] = result
        if error is not None:
            payload["error"] = error
        item.iter_content.return_value = [json.dumps(payload).encode()]
        return item

    session = MagicMock()

    def post(_endpoint, *, json, **_kwargs):
        calls.append(json["method"])
        if json["method"] == "message/stream":
            return response(200, json["id"], error={"code": -32601, "message": "unsupported"})
        if json["method"] == "message/send":
            return response(
                200,
                json["id"],
                {"kind": "task", "id": "task-1", "contextId": "context-1", "status": {"state": "working"}},
            )
        return response(
            200,
            json["id"],
            {
                "kind": "task",
                "id": "task-1",
                "contextId": "context-1",
                "status": {"state": "completed"},
                "artifacts": [{"parts": [{"kind": "text", "text": "resumed answer"}]}],
            },
        )

    session.post.side_effect = post
    monkeypatch.setattr(ai_transport, "_session", lambda: session)
    monkeypatch.setattr(ai_transport.time, "sleep", lambda _seconds: None)
    config = _ai_config(provider="a2a", model=None)
    checkpoints = []
    output = ai_transport.generate(
        config,
        "trusted-token",
        "system",
        {"alert": "data"},
        deadline=time.monotonic() + 30,
        checkpoint=lambda task_id, context_id: checkpoints.append((task_id, context_id)),
    )
    assert output == "resumed answer"
    assert calls == ["message/stream", "message/send", "tasks/get"]
    assert ("task-1", "context-1") in checkpoints

    calls.clear()
    output = ai_transport.generate(
        config,
        "trusted-token",
        "system",
        {"alert": "data"},
        deadline=time.monotonic() + 30,
        checkpoint=lambda _task_id, _context_id: True,
        resume_task_id="task-1",
        resume_context_id="context-1",
    )
    assert output == "resumed answer"
    assert calls == ["tasks/get"]


@pytest.mark.parametrize(
    "payload",
    [
        {"jsonrpc": "2.0", "id": "rpc-1"},
        {"jsonrpc": "2.0", "id": "rpc-1", "result": {}, "error": {"code": -32601, "message": "unsupported"}},
        {"jsonrpc": "1.0", "id": "rpc-1", "result": {}},
        {"jsonrpc": "2.0", "id": "wrong", "result": {}},
        {"jsonrpc": "2.0", "id": "rpc-1", "error": {"code": "-32601", "message": "unsupported"}},
        {"jsonrpc": "2.0", "id": "rpc-1", "result": {}, "method": "message/stream"},
    ],
)
def test_a2a_rpc_envelope_rejects_invalid_correlation_or_shape(payload):
    with pytest.raises(ai_transport.AITransportError):
        ai_transport._validate_rpc_response(payload, "rpc-1")


def test_a2a_non_sse_task_requires_canonical_id(monkeypatch):
    response = MagicMock()
    response.status_code = 200
    response.headers = {"content-type": "application/json"}
    session = MagicMock()
    json_module = json

    def post(_endpoint, *, json, **_kwargs):
        response.iter_content.return_value = [
            json_module.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": json["id"],
                    "result": {
                        "kind": "task",
                        "status": {"state": "completed"},
                        "artifacts": [{"parts": [{"kind": "text", "text": "answer"}]}],
                    },
                }
            ).encode()
        ]
        return response

    session.post.side_effect = post
    monkeypatch.setattr(ai_transport, "_session", lambda: session)

    with pytest.raises(ai_transport.AITransportError, match="valid id"):
        ai_transport.generate(
            _ai_config(provider="a2a", model=None),
            "trusted-token",
            "system",
            {"alert": "data"},
            deadline=time.monotonic() + 30,
            checkpoint=lambda _task_id, _context_id: True,
        )
    response.close.assert_called_once()


def test_a2a_direct_message_has_its_own_validated_shape(monkeypatch):
    response = MagicMock()
    response.status_code = 200
    response.headers = {"content-type": "application/json"}
    session = MagicMock()
    json_module = json

    def post(_endpoint, *, json, **_kwargs):
        response.iter_content.return_value = [
            json_module.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": json["id"],
                    "result": {
                        "kind": "message",
                        "messageId": "message-1",
                        "role": "agent",
                        "parts": [{"kind": "text", "text": "direct answer"}],
                    },
                }
            ).encode()
        ]
        return response

    session.post.side_effect = post
    monkeypatch.setattr(ai_transport, "_session", lambda: session)
    assert (
        ai_transport.generate(
            _ai_config(provider="a2a", model=None),
            "trusted-token",
            "system",
            {"alert": "data"},
            deadline=time.monotonic() + 30,
            checkpoint=lambda _task_id, _context_id: None,
        )
        == "direct answer"
    )

    invalid_message = {
        "kind": "message",
        "messageId": "message-1",
        "role": "user",
        "parts": [{"kind": "text", "text": "not agent output"}],
    }
    with pytest.raises(ai_transport.AITransportError, match="invalid direct message"):
        ai_transport._extract_direct_message_text(invalid_message)


def test_bare_http_not_found_does_not_trigger_a2a_method_fallback(monkeypatch):
    response = MagicMock()
    response.status_code = 404
    response.headers = {"content-type": "application/json"}
    session = MagicMock()
    session.post.return_value = response
    monkeypatch.setattr(ai_transport, "_session", lambda: session)

    with pytest.raises(ai_transport.AITransportError):
        ai_transport.generate(
            _ai_config(provider="a2a", model=None),
            "trusted-token",
            "system",
            {"alert": "data"},
            deadline=time.monotonic() + 30,
            checkpoint=lambda _task_id, _context_id: None,
        )
    assert session.post.call_count == 1
    assert session.post.call_args.kwargs["json"]["method"] == "message/stream"


def test_chunked_a2a_stream_failure_is_transient_and_resumes_saved_task(monkeypatch):
    first_session = MagicMock()
    first_response = MagicMock()
    first_response.status_code = 200
    first_response.headers = {"content-type": "text/event-stream"}

    def interrupted_stream(*, request_id):
        event = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "kind": "task",
                "id": "task-after-chunked-error",
                "contextId": "ctx-1",
                "status": {"state": "working"},
            },
        }
        yield b"data:" + json.dumps(event).encode() + b"\n\n"
        raise ai_transport.requests.exceptions.ChunkedEncodingError("private provider detail")

    def first_post(_endpoint, *, json, **_kwargs):
        first_response.iter_content.side_effect = lambda **_ignored: interrupted_stream(request_id=json["id"])
        return first_response

    first_session.post.side_effect = first_post
    second_session = MagicMock()
    second_response = MagicMock()
    second_response.status_code = 200
    second_response.headers = {"content-type": "application/json"}
    second_response.__enter__.return_value = second_response
    json_module = json

    def second_post(_endpoint, *, json, **_kwargs):
        assert json["method"] == "tasks/get"
        second_response.iter_content.return_value = [
            json_module.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": json["id"],
                    "result": {
                        "kind": "task",
                        "id": "task-after-chunked-error",
                        "contextId": "ctx-1",
                        "status": {"state": "completed"},
                        "artifacts": [{"parts": [{"kind": "text", "text": "resumed safely"}]}],
                    },
                }
            ).encode()
        ]
        return second_response

    second_session.post.side_effect = second_post
    sessions = iter((first_session, second_session))
    monkeypatch.setattr(ai_transport, "_session", lambda: next(sessions))
    monkeypatch.setattr(ai_transport.time, "sleep", lambda _seconds: None)
    provider_config = _ai_config(provider="a2a", model=None)
    checkpoints = []

    with pytest.raises(ai_transport.AITransportError) as caught:
        ai_transport.generate(
            provider_config,
            "trusted-token",
            "system",
            {"alert": "data"},
            deadline=time.monotonic() + 30,
            checkpoint=lambda task_id, context_id: checkpoints.append((task_id, context_id)) or True,
        )
    assert caught.value.transient is True
    assert "private provider detail" not in str(caught.value)
    assert ("task-after-chunked-error", "ctx-1") in checkpoints
    assert first_response.close.called
    assert first_session.close.called

    assert (
        ai_transport.generate(
            provider_config,
            "trusted-token",
            "system",
            {"alert": "data"},
            deadline=time.monotonic() + 30,
            checkpoint=lambda _task_id, _context_id: True,
            resume_task_id="task-after-chunked-error",
            resume_context_id="ctx-1",
        )
        == "resumed safely"
    )
    assert [call.kwargs["json"]["method"] for call in first_session.post.call_args_list] == ["message/stream"]
    assert [call.kwargs["json"]["method"] for call in second_session.post.call_args_list] == ["tasks/get"]
    assert second_session.close.called


def test_public_run_serializers_do_not_expose_private_credentials():
    run = {
        **_run(),
        "_encrypted_bearer_token": "ciphertext",
        "_auth_scheme": "Bearer",
        "_prompt": "private prompt",
        "_a2a_task_id": "internal-task",
    }
    public = ai_triage_service.public_run(run)
    rendered = json.dumps(public)
    assert "ciphertext" not in rendered
    assert "private prompt" not in rendered
    assert "internal-task" not in rendered
    assert set(public["results"][0]) == {
        "hit_id",
        "state",
        "attempts",
        "reason",
        "message",
        "started_at",
        "finished_at",
    }


def test_run_status_rechecks_current_classification_access(monkeypatch):
    run = {**_run(), "_owner": "alice", "_expires_at": time.time() + 1000}
    user = SimpleNamespace(uname="alice", is_active=True)
    monkeypatch.setattr(ai_triage_queue, "read_run", lambda _run_id: run)

    monkeypatch.setattr(
        ai_triage_service.hit_service,
        "get_hit",
        lambda *_args, **_kwargs: (SimpleNamespace(classification="SECRET"), "version"),
    )
    monkeypatch.setattr(ai_triage_service, "is_classification_accessible", lambda _user, _classification: False)

    assert ai_triage_service.get_run("run-1", user) is None


def test_save_hit_followup_error_reconciles_committed_run_lead(monkeypatch):
    user = SimpleNamespace(uname="alice", type=["automation_basic"], is_active=True)
    persisted_leads = []
    candidate = ai_triage_service.prepare_candidate("validated answer", "run-1", "source-v1")

    def get_current_hit(_hit_id, _user):
        hit = SimpleNamespace(
            classification=None,
            howler=SimpleNamespace(id="hit-0", status="open", assessment=None, dossier=list(persisted_leads)),
        )
        return hit, "version-1"

    def save_then_raise(_hit_id, hit, version=None, refresh=None):
        del version, refresh
        persisted_leads[:] = hit.howler.dossier
        raise RuntimeError("post-commit read failed")

    monkeypatch.setattr(ai_triage_service, "get_current_hit", get_current_hit)
    monkeypatch.setattr(
        ai_triage_service, "datastore", lambda: SimpleNamespace(hit=SimpleNamespace(save=save_then_raise))
    )

    saved, reason = ai_triage_service.save_ai_lead("hit-0", user, candidate)

    assert saved is True
    assert reason is None
    assert ai_triage_service.has_managed_candidate(
        SimpleNamespace(howler=SimpleNamespace(dossier=persisted_leads)), candidate
    )


def test_unknown_write_with_failed_immediate_reads_reconciles_without_new_candidate(queue_backend, monkeypatch):
    _redis, now = queue_backend
    ai_triage_queue.create_run(_run())
    job, _ = ai_triage_queue.claim_next()
    ai_triage_queue.begin_provider_attempt(job["run_id"], job["index"], job["nonce"])
    candidate = ai_triage_service.prepare_candidate("canonical answer", job["run_id"], "source-v1")
    assert ai_triage_queue.store_candidate(job["run_id"], job["index"], job["nonce"], candidate)
    assert ai_triage_queue.set_commit_phase(job["run_id"], job["index"], job["nonce"], "write_pending")

    user = SimpleNamespace(uname="alice", type=["automation_basic"], is_active=True)
    persisted_leads = []

    def hit_record():
        return SimpleNamespace(
            classification=None,
            howler=SimpleNamespace(id="hit-0", status="open", assessment=None, dossier=list(persisted_leads)),
        )

    reads = [0]

    def unavailable_reads(_hit_id, _user):
        reads[0] += 1
        if reads[0] >= 3:
            raise ConnectionError("temporary read outage")
        return hit_record(), "version-1"

    hit_store = SimpleNamespace(
        save=MagicMock(side_effect=RuntimeError("ambiguous write response")),
        get_if_exists=MagicMock(return_value=({"howler": {"id": "hit-0"}}, "version-2")),
    )
    monkeypatch.setattr(ai_triage_service, "get_current_hit", unavailable_reads)
    monkeypatch.setattr(ai_triage_service, "datastore", lambda: SimpleNamespace(hit=hit_store))
    monkeypatch.setattr(ai_triage_service.comms_service, "emit", MagicMock())

    saved, reason = ai_triage_service.save_ai_lead("hit-0", user, candidate)
    assert saved is False
    assert reason == "write_reconciliation_pending"
    pending = ai_triage_queue.defer_candidate_reconciliation(job["run_id"], job["index"], job["nonce"])
    assert pending["state"] == "running"
    assert pending["results"][0]["reason"] == "write_reconciliation_pending"

    now[0] = 101
    reconciliation, _changed = ai_triage_queue.claim_reconciliation()
    assert reconciliation is not None
    monkeypatch.setattr(ai_triage_service, "get_current_hit", lambda _id, _user: (hit_record(), "version-2"))
    monkeypatch.setattr(
        hit_store, "save", lambda _key, hit, **_kwargs: persisted_leads.__setitem__(slice(None), hit.howler.dossier)
    )
    state, _reason = ai_triage_service.reconcile_candidate(
        "hit-0",
        candidate,
        user_loader=lambda: user,
        lease_check=lambda: ai_triage_queue.reconciliation_is_current(
            reconciliation["run_id"], reconciliation["index"], reconciliation["nonce"]
        ),
        write_intent_check=lambda: ai_triage_queue.mark_reconciliation_write_intent(
            reconciliation["run_id"], reconciliation["index"], reconciliation["nonce"]
        ),
        allow_write=True,
        write_intent=bool(reconciliation["write_intent"]),
        active_deadline=time.monotonic() + max(0, reconciliation["deadline_at"] - ai_triage_queue._now()),
    )
    assert state == "saved"
    completed = ai_triage_queue.finish_reconciliation(
        reconciliation["run_id"], reconciliation["index"], reconciliation["nonce"], state="succeeded"
    )
    assert completed["state"] == "completed"
    assert ai_triage_service.has_managed_candidate(hit_record(), candidate)
    assert completed["results"][0]["attempts"] == 1


def test_stale_worker_read_cannot_save_after_lease_recovery(queue_backend, monkeypatch):
    _redis, now = queue_backend
    ai_triage_queue.create_run(_run())
    stale_job, _ = ai_triage_queue.claim_next()
    current_job = []
    user = SimpleNamespace(uname="alice", type=["automation_basic"], is_active=True)
    candidate = ai_triage_service.prepare_candidate("candidate", "run-1", "source-v1")

    def delayed_read(_hit_id, _user):
        now[0] = 104
        recovered, _ = ai_triage_queue.claim_next()
        current_job.append(recovered)
        hit = SimpleNamespace(
            classification=None,
            howler=SimpleNamespace(id="hit-0", status="open", assessment=None, dossier=[]),
        )
        return hit, "version-1"

    save_hit = MagicMock()
    monkeypatch.setattr(ai_triage_service, "get_current_hit", delayed_read)
    monkeypatch.setattr(ai_triage_service, "datastore", lambda: SimpleNamespace(hit=SimpleNamespace(save=save_hit)))

    saved, reason = ai_triage_service.save_ai_lead(
        "hit-0",
        user,
        candidate,
        lease_check=lambda: ai_triage_queue.lease_is_current(
            stale_job["run_id"], stale_job["index"], stale_job["nonce"]
        ),
    )

    assert current_job[0]["nonce"] != stale_job["nonce"]
    assert saved is False
    assert reason == "lease_lost"
    save_hit.assert_not_called()


def test_save_boundary_reloads_roles_before_versioned_hit_write(monkeypatch):
    first_user = SimpleNamespace(uname="alice", type=["automation_basic"], classification="SECRET", is_active=True)
    revoked_user = SimpleNamespace(uname="alice", type=["user"], classification="UNRESTRICTED", is_active=True)
    loads = iter((first_user, revoked_user))
    hit = SimpleNamespace(
        classification="SECRET",
        howler=SimpleNamespace(id="hit-0", status="open", assessment=None, dossier=[]),
    )
    monkeypatch.setattr(ai_triage_service, "get_current_hit", lambda *_args, **_kwargs: (hit, "version-1"))
    save_hit = MagicMock()
    monkeypatch.setattr(ai_triage_service, "datastore", lambda: SimpleNamespace(hit=SimpleNamespace(save=save_hit)))

    saved, reason = ai_triage_service.save_ai_lead(
        "hit-0",
        first_user,
        ai_triage_service.prepare_candidate("candidate", "run-1", "source-v1"),
        user_loader=lambda: next(loads),
    )

    assert saved is False
    assert reason == "initiator_access_revoked"
    save_hit.assert_not_called()
