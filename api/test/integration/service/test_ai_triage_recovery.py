"""Real Redis/Elasticsearch checks. Missing infrastructure fails rather than skips.

Use disposable local services and set AI_TRIAGE_TEST_REDIS_URL and
AI_TRIAGE_TEST_ES_URL. Only unique test-owned Redis keys and ES indices are removed.
"""

import json
import os
import runpy
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import Mock
from urllib.parse import urlparse
from uuid import uuid4

import pytest
import requests
from flask import Flask
from redis import Redis, WatchError

from howler.api import socket as socket_api
from howler.api.v1.action import action_api
from howler.common.loader import DATASTORE_INDEX_PREFIX
from howler.datastore.store import ESStore
from howler.odm.models.config import AITriage, Host, config
from howler.odm.models.hit import Hit
from howler.odm.models.user import User
from howler.security import login
from howler.security import socket as socket_auth
from howler.services import ai_transport, hit_service
from howler.services import ai_triage_queue as queue
from howler.services import ai_triage_service as service
from howler.services import ai_triage_worker as worker


class Clock:
    def __init__(self):
        self.now = time.time()

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def lead(content="old opinion", owner="howler.ai_triage"):
    return {
        "label": {"en": "AI Triage", "fr": "Triage IA"},
        "format": "markdown",
        "content": content,
        "metadata": json.dumps({"owner": owner}),
    }


def hit(**howler):
    return Hit(
        {
            "classification": "U",
            "event": {"original": "enqueue-time data"},
            "howler": {"analytic": "QA triage", "hash": "123abc", **howler},
        }
    )


def analyst(name="qa-analyst", roles=None):
    return User(
        {
            "uname": name,
            "name": name,
            "password": "qa-hash",
            "classification": "U",
            "type": roles or ["user", "actionrunner_basic"],
            "access_control": "classification:UNRESTRICTED",
        }
    )


@pytest.fixture
def redis_client():
    url = os.environ.get("AI_TRIAGE_TEST_REDIS_URL", "redis://127.0.0.1:6379/15")
    client = Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)
    assert client.ping(), "AI triage integration requires a real, disposable Redis server"
    try:
        yield client
    finally:
        client.close()


@pytest.fixture
def es_hits(monkeypatch):
    url = urlparse(os.environ.get("AI_TRIAGE_TEST_ES_URL", "http://127.0.0.1:9200"))
    assert url.scheme in ("http", "https") and url.netloc
    isolated_config = config.model_copy(deep=True)
    isolated_config.datastore.hosts = [Host(name="qa_ai_triage", scheme=url.scheme, host=url.netloc)]
    store = ESStore(isolated_config)
    assert store.ping(), "AI triage integration requires a real, disposable Elasticsearch server"
    name = f"ai-triage-qa-{uuid4().hex}"
    store.register(name, Hit)
    hits = store[name]
    monkeypatch.setattr(hit_service, "datastore", lambda: SimpleNamespace(hit=hits))
    monkeypatch.setattr(hit_service.comms_service, "emit", Mock())
    try:
        yield hits
    finally:
        store.client.indices.delete(index=hits.index_name)
        store.close()


@pytest.fixture
def stack(redis_client, es_hits, monkeypatch):
    settings = AITriage(enabled=True, endpoint="https://ai.invalid/triage", model="qa-model")
    monkeypatch.setattr(config.core, "ai", settings)
    monkeypatch.setattr(config.system, "encryption_key", "0123456789abcdef0123456789abcdef")
    prefix = f"howler.ai_triage.qa:{{{uuid4().hex}}}"
    monkeypatch.setattr(queue, "_KEY_PREFIX", prefix)
    monkeypatch.setattr(queue, "redis_client", lambda: redis_client)
    clock = Clock()
    monkeypatch.setattr(queue, "_now", clock)
    monkeypatch.setattr(worker, "time", SimpleNamespace(time=clock, monotonic=clock, sleep=clock.advance))
    monkeypatch.setattr(service, "time", SimpleNamespace(time=clock, monotonic=clock))
    monkeypatch.setattr(ai_transport, "time", SimpleNamespace(monotonic=clock, sleep=clock.advance))
    monkeypatch.setattr(worker, "_sleep", clock.advance)
    monkeypatch.setattr(worker.gevent, "sleep", clock.advance)
    user_collection = f"ai-triage-users-qa-{uuid4().hex}"
    es_hits.datastore.register(user_collection, User)
    users = es_hits.datastore[user_collection]
    storage = SimpleNamespace(hit=es_hits, user=users)
    monkeypatch.setattr(service, "datastore", lambda: storage)
    events = []

    def emit(event, data):
        if event == "action":
            persisted = queue.read_run(data["run_id"])
            assert persisted is not None and persisted["revision"] >= data["revision"]
        events.append((event, deepcopy(data)))

    monkeypatch.setattr(service.comms_service, "emit", emit)

    def no_http(_self, method, url, **_kwargs):
        pytest.fail(f"Unscripted provider HTTP in integration test: {method} {url}")

    monkeypatch.setattr(requests.sessions.Session, "request", no_http)
    owner = analyst()
    users.save(owner.uname, owner)

    def seed(*records):
        for record in records:
            es_hits.save(record.howler.id, record, refresh="true")

    def enqueue(query="*:*", user=None, **kwargs):
        return service.enqueue_run(query, user or owner, bearer_token="qa-real-bearer", **kwargs)

    context = SimpleNamespace(
        redis=redis_client,
        hits=es_hits,
        users=users,
        owner=owner,
        clock=clock,
        config=settings,
        seed=seed,
        enqueue=enqueue,
        events=events,
        prefix=prefix,
        hit_collection=next(name for name, model in es_hits.datastore._models.items() if model is Hit),
        user_collection=user_collection,
    )
    try:
        yield context
    finally:
        keys = list(redis_client.scan_iter(match=f"{prefix}:*"))
        if keys:
            redis_client.delete(*keys)
        es_hits.datastore.client.indices.delete(index=users.index_name)


def claim():
    job, _ = queue.claim_next()
    assert job is not None
    return job


def finish(job, **kwargs):
    return queue.finish_item(job["run_id"], job["index"], job["nonce"], **kwargs)


def begin_attempt(job):
    result = queue.begin_provider_attempt(job["run_id"], job["index"], job["nonce"])
    assert result is not None
    job["attempts"] = result["attempts"]
    job["run"] = result["run"]
    return result


def current_leads(stack, record):
    return stack.hits.get(record.howler.id).as_primitives()["howler"]["dossier"]


@pytest.mark.parametrize(
    "roles,limit", [(["actionrunner_basic", "user"], 10), (["actionrunner_advanced", "user"], 50), (["admin"], 50)]
)
def test_real_selection_limit_and_atomic_oversize_rejection(stack, roles, limit):
    owner = analyst(roles=roles)
    stack.seed(*(hit() for _ in range(limit)))
    accepted = stack.enqueue(user=owner)
    assert accepted["counts"]["total"] == limit
    before = {key: stack.redis.dump(key) for key in stack.redis.scan_iter(match=f"{stack.prefix}:*")}
    stack.seed(hit())
    with pytest.raises(service.AIQueueValidationError, match="limit"):
        stack.enqueue(user=owner)
    after = {key: stack.redis.dump(key) for key in stack.redis.scan_iter(match=f"{stack.prefix}:*")}
    assert after == before, "An oversized request must not create a partial run or queue entries"


def test_real_search_excludes_resolved_assessed_and_inaccessible_before_count(stack):
    eligible = [hit() for _ in range(10)]
    inaccessible = hit()
    inaccessible.classification = "R"
    stack.seed(*eligible, hit(status="resolved"), hit(assessment="legitimate"), inaccessible)
    run = stack.enqueue()
    assert {item["hit_id"] for item in run["results"]} == {record.howler.id for record in eligible}
    raw = queue.read_run(run["run_id"])
    assert raw["_encrypted_bearer_token"] != "qa-real-bearer"
    assert "qa-real-bearer" not in json.dumps(raw)
    assert "enqueue-time data" not in json.dumps(raw)


def test_claim_persists_running_state_and_start_timestamps(stack):
    stack.seed(hit())
    queued = stack.enqueue()
    job = claim()
    running = queue.read_run(job["run_id"])
    assert running["state"] == "running"
    assert running["started_at"] and running["results"][0]["started_at"]
    assert running["revision"] > queued["revision"]
    assert running["counts"] == {"total": 1, "queued": 0, "running": 1, "succeeded": 0, "failed": 0, "skipped": 0}


def test_redis_concurrent_claimers_share_exactly_four_global_permits(stack):
    stack.seed(hit())
    for index in range(12):
        stack.enqueue(user=analyst(name=f"owner-{index}"))
    with ThreadPoolExecutor(max_workers=12) as pool:
        jobs = [job for job, _ in pool.map(lambda _: queue.claim_next(), range(12)) if job]
    assert len(jobs) == 4
    assert len({job["nonce"] for job in jobs}) == 4
    assert len({job["run"]["_owner"] for job in jobs}) == 4
    assert stack.redis.zcard(queue._lease_key()) == 4
    assert queue.claim_next()[0] is None
    finish(jobs[0], state="succeeded")
    assert claim()["run_id"] not in {job["run_id"] for job in jobs}
    assert stack.redis.zcard(queue._lease_key()) == 4


def test_recovery_retains_task_checkpoint_deadline_and_rejects_stale_owner(stack):
    stack.seed(hit())
    stack.enqueue()
    first = claim()
    begin_attempt(first)
    assert first["deadline_at"] == pytest.approx(stack.clock() + 600)
    assert queue.checkpoint(first["run_id"], first["index"], first["nonce"], "task-qa", "context-qa")
    stack.clock.advance(stack.config.lease_seconds + 1)
    recovered = claim()
    assert recovered["run_id"] == first["run_id"]
    assert recovered["attempts"] == 1 and recovered["nonce"] != first["nonce"]
    assert recovered["deadline_at"] == first["deadline_at"]
    assert recovered["run"]["results"][0]["_a2a_task_id"] == "task-qa"
    assert recovered["run"]["results"][0]["_a2a_context_id"] == "context-qa"
    assert not queue.heartbeat(first["run_id"], first["index"], first["nonce"])
    assert not queue.checkpoint(first["run_id"], first["index"], first["nonce"], "stale-task", None)
    assert not queue.lease_is_current(first["run_id"], first["index"], first["nonce"])
    assert finish(first, state="succeeded") is None
    assert queue.lease_is_current(recovered["run_id"], recovered["index"], recovered["nonce"])
    assert stack.redis.zcard(queue._lease_key()) == 1


def test_heartbeat_is_nonce_fenced_and_never_extends_absolute_deadline(stack):
    stack.seed(hit())
    stack.enqueue()
    job = claim()
    for _ in range(59):
        stack.clock.advance(10)
        assert queue.heartbeat(job["run_id"], job["index"], job["nonce"])
    raw = queue.read_run(job["run_id"])
    assert raw["results"][job["index"]]["_deadline_at"] == job["deadline_at"]
    assert raw["results"][0]["_lease_expires_at"] <= job["deadline_at"]
    stack.clock.advance(10)
    assert not queue.heartbeat(job["run_id"], job["index"], job["nonce"])


@pytest.mark.parametrize("crash", [False, True])
def test_three_total_attempts_including_crash_recovery_and_terminal_scrubbing(stack, crash):
    stack.seed(hit())
    run = stack.enqueue(prompt="private analyst instruction")
    deadline = None
    for attempt in range(1, 4):
        job = claim()
        begin_attempt(job)
        assert job["attempts"] == attempt
        deadline = deadline or job["deadline_at"]
        assert job["deadline_at"] == deadline
        if crash:
            stack.clock.advance(stack.config.lease_seconds + 1)
        else:
            finish(job, state="failed", transient=True, reason="provider_transient_error")
    assert queue.claim_next()[0] is None
    raw = queue.read_run(run["run_id"])
    assert raw["state"] == "completed" and raw["counts"]["failed"] == 1
    assert raw["results"][0]["attempts"] == 3
    assert "_encrypted_bearer_token" not in raw and "_prompt" not in raw
    assert stack.redis.zcard(queue._lease_key()) == 0


def test_absolute_deadline_survives_requeue_without_expiring_unclaimed_alerts(stack):
    stack.seed(hit(), hit())
    run = stack.enqueue()
    job = claim()
    finish(job, state="failed", transient=True)
    stack.clock.advance(601)
    second = claim()
    assert second["hit_id"] != job["hit_id"]
    assert second["deadline_at"] == pytest.approx(stack.clock() + 600)
    finish(second, state="succeeded")
    assert queue.claim_next()[0] is None
    raw = queue.read_run(run["run_id"])
    assert raw["counts"]["failed"] == raw["counts"]["succeeded"] == 1
    assert raw["state"] == "completed"
    assert raw["results"][job["index"]]["reason"] == "run_deadline_exceeded"
    assert "_encrypted_bearer_token" not in raw


def test_real_cas_retry_preserves_concurrent_analyst_edit_and_leads(stack, monkeypatch):
    record = hit(dossier=[lead(), lead("human", "analyst")])
    stack.seed(record)
    original_save = stack.hits.save
    versions = []

    def conflict_once(key, updated, *, version):
        versions.append(version)
        if len(versions) == 1:
            concurrent, current_version = stack.hits.get(record.howler.id, version=True)
            concurrent.howler.assignment = "another-analyst"
            concurrent.howler.dossier.append(lead("new human note", "analyst"))
            original_save(key, concurrent, version=current_version)
        return original_save(key, updated, version=version)

    monkeypatch.setattr(stack.hits, "save", conflict_once)
    candidate = service.prepare_candidate("new opinion", "run-qa", "0")
    assert service.save_ai_lead(record.howler.id, stack.owner, candidate) == (True, None)
    assert len(versions) == 2 and versions[0] != versions[1]
    fresh = stack.hits.get(record.howler.id)
    assert fresh.howler.assignment == "another-analyst"
    assert [item.content for item in fresh.howler.dossier] == ["human", "new human note", "new opinion"]


@pytest.mark.parametrize("failure", ["http", "save", "conflict"])
def test_failed_provider_or_write_retains_old_opinion(stack, monkeypatch, failure):
    record = hit(dossier=[lead(), lead("human", "analyst")])
    stack.seed(record)
    run = stack.enqueue()
    original = current_leads(stack, record)
    original_save = stack.hits.save

    def generate(*_args, **kwargs):
        assert kwargs["begin_attempt"]()
        return "new"

    if failure == "save":
        monkeypatch.setattr(stack.hits, "save", Mock(side_effect=RuntimeError("private datastore details")))
    elif failure == "conflict":

        def conflict(key, updated, *, version):
            fresh, current_version = stack.hits.get(record.howler.id, version=True)
            original_save(key, fresh, version=current_version)
            return original_save(key, updated, version=version)

        monkeypatch.setattr(stack.hits, "save", conflict)
    generated = Mock(
        side_effect=(
            ai_transport.AITransportError("Provider rejected the authorization token")
            if failure == "http"
            else generate
        )
    )
    monkeypatch.setattr(ai_transport, "generate", generated)
    worker._process(claim())
    assert current_leads(stack, record) == original
    final = queue.read_run(run["run_id"])
    if failure == "http":
        assert final["counts"]["failed"] == 1
    else:
        assert final["results"][0]["state"] == "queued"
        assert final["results"][0]["reason"] == "save_transient_error"
        assert final["results"][0]["_candidate"]
        assert final["results"][0]["attempts"] == 1
        if failure == "save":
            monkeypatch.setattr(stack.hits, "save", original_save)
            worker._process(claim())
            final = queue.read_run(run["run_id"])
            assert final["counts"]["succeeded"] == 1
            assert generated.call_count == 1
            assert [item["content"] for item in current_leads(stack, record)] == ["human", "new"]
    assert "private datastore details" not in json.dumps(service.public_run(final))


@pytest.fixture
def api_client(stack, monkeypatch):
    auth = Mock()
    auth.bearer_auth.return_value = (stack.owner, ["R", "E"])
    monkeypatch.setattr(login, "auth_service", auth)
    monkeypatch.setattr(login, "QUOTA_TRACKER", Mock(begin=Mock(return_value=True)))
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="qa-not-secret")
    app.register_blueprint(action_api)
    client = app.test_client()
    client.environ_base["HTTP_AUTHORIZATION"] = "Bearer qa-token"
    return client, auth


def test_run_routes_real_owner_classification_gate_and_public_schema(stack, api_client):
    record = hit()
    stack.seed(record)
    run = stack.enqueue(request_id="qa-request", action_id="qa-action")
    client, auth = api_client
    url = f"/api/v1/action/runs/{run['run_id']}"
    result = client.get(url)
    assert result.status_code == 200 and result.headers["Cache-Control"] == "no-store"
    public = result.get_json()["api_response"]
    assert set(public) == {
        "run_id",
        "operation_id",
        "request_id",
        "action_id",
        "trigger",
        "state",
        "revision",
        "created_at",
        "started_at",
        "updated_at",
        "finished_at",
        "expires_at",
        "counts",
        "results",
    }
    assert set(public["results"][0]) == {
        "hit_id",
        "state",
        "attempts",
        "reason",
        "message",
        "started_at",
        "finished_at",
    }
    assert all(type(count) is int for count in public["counts"].values())
    assert "_owner" not in json.dumps(public) and "qa-real-bearer" not in json.dumps(public)
    auth.bearer_auth.return_value = (analyst("not-the-owner", roles=["admin"]), ["R", "E"])
    denied = client.get(url)
    missing = client.get("/api/v1/action/runs/missing")
    assert denied.status_code == missing.status_code == 404
    assert denied.get_json()["api_error_message"] == missing.get_json()["api_error_message"]
    assert denied.headers["Cache-Control"] == "no-store"
    assert client.get("/api/v1/action/runs").get_json()["api_response"]["items"] == []
    auth.bearer_auth.return_value = (stack.owner, ["R", "E"])
    record.classification = "R"
    stack.seed(record)
    assert client.get(url).status_code == 404
    assert client.get("/api/v1/action/runs").get_json()["api_response"]["items"] == []


def test_run_list_filters_before_pagination_and_remains_readable_disabled(stack, api_client):
    stack.seed(hit())
    ids = []
    for index in range(5):
        run = stack.enqueue(action_id="matching" if index % 2 == 0 else "other", request_id="request")
        ids.append(run["run_id"])
        stack.clock.advance(1)
    stack.config.enabled = False
    client, _ = api_client
    result = client.get(
        "/api/v1/action/runs?operation_id=ai_triage&action_id=matching&request_id=request&rows=1&offset=1"
    )
    assert result.status_code == 200 and result.headers["Cache-Control"] == "no-store"
    page = result.get_json()["api_response"]
    assert page["offset"] == 1 and page["rows"] == 1 and page["has_more"] is True
    assert [item["run_id"] for item in page["items"]] == [ids[2]]
    assert "results" not in page["items"][0]
    assert client.get(f"/api/v1/action/runs/{ids[0]}").status_code == 200


class SimulatedCrash(BaseException):
    pass


@pytest.mark.parametrize("crash_after_save", [False, True])
def test_worker_reuses_candidate_after_crash_without_second_provider_call(stack, monkeypatch, crash_after_save):
    record = hit(dossier=[lead()])
    stack.seed(record)
    stack.enqueue()
    generate = Mock(return_value="durable candidate")
    monkeypatch.setattr(ai_transport, "generate", generate)
    boundary_owner = queue if crash_after_save else service
    boundary_name = "finish_item" if crash_after_save else "save_ai_lead"
    original = getattr(boundary_owner, boundary_name)
    monkeypatch.setattr(boundary_owner, boundary_name, Mock(side_effect=SimulatedCrash))
    with pytest.raises(SimulatedCrash):
        worker._process(claim())
    monkeypatch.setattr(boundary_owner, boundary_name, original)
    stack.clock.advance(stack.config.lease_seconds + 1)
    worker._process(claim())
    assert generate.call_count == 1, "A completed candidate must be durable across save/ack crash windows"
    assert [item["content"] for item in current_leads(stack, record)] == ["durable candidate"]


def test_worker_rechecks_current_classification_before_provider(stack, monkeypatch):
    record = hit(dossier=[lead()])
    stack.seed(record)
    run = stack.enqueue()
    record.classification = "R"
    stack.seed(record)
    generate = Mock()
    monkeypatch.setattr(ai_transport, "generate", generate)
    worker._process(claim())
    generate.assert_not_called()
    assert queue.read_run(run["run_id"])["counts"]["skipped"] == 1
    assert current_leads(stack, record)[0]["content"] == "old opinion"


def test_real_ai_http_dispatch_durably_queues_and_returns_async_reference(stack, api_client, monkeypatch):
    record = hit()
    stack.seed(record)
    client, _ = api_client
    monkeypatch.setattr("howler.api.v1.action.audit", Mock())
    result = client.post(
        "/api/v1/action/execute",
        json={
            "query": "*:*",
            "request_id": "qa-manual",
            "operations": [{"operation_id": "ai_triage", "data_json": json.dumps({"prompt": "concise"})}],
        },
    )
    assert result.status_code == 200
    report = result.get_json()["api_response"]["ai_triage"][0]
    assert report["outcome"] == "success" and report["status"] == "queued"
    persisted = queue.read_run(report["run_id"])
    assert persisted["results"][0]["hit_id"] == record.howler.id
    assert persisted["request_id"] == "qa-manual"
    assert persisted["_prompt"] == "concise"
    assert stack.redis.llen(queue._queue_key()) == 1


def test_cas_conflict_rechecks_new_resolution_instead_of_overwriting(stack, monkeypatch):
    record = hit(dossier=[lead()])
    stack.seed(record)
    original_save = stack.hits.save

    def resolve_before_save(key, updated, *, version):
        fresh, current_version = stack.hits.get(record.howler.id, version=True)
        fresh.howler.status = "resolved"
        original_save(key, fresh, version=current_version)
        return original_save(key, updated, version=version)

    save = Mock(side_effect=resolve_before_save)
    monkeypatch.setattr(stack.hits, "save", save)
    candidate = service.prepare_candidate("new", "run-qa", "0")
    assert service.save_ai_lead(record.howler.id, stack.owner, candidate) == (
        False,
        "alert_no_longer_eligible",
    )
    assert save.call_count == 1
    assert current_leads(stack, record)[0]["content"] == "old opinion"
    assert stack.hits.get(record.howler.id).howler.status == "resolved"


def test_real_redis_transaction_aborts_when_lock_fence_is_replaced(stack):
    lock_key = queue._global_lock_key()
    result_key = f"{stack.prefix}:must-not-be-written"
    with queue._locked(stack.redis, lock_key):
        with queue._fenced_pipeline(stack.redis) as pipeline:
            pipeline.set(result_key, "stale writer")
            stack.redis.set(lock_key, "replacement-owner")
            with pytest.raises(WatchError):
                pipeline.execute()
    assert stack.redis.get(result_key) is None


def test_postcommit_notification_read_failure_acks_saved_lead_without_resubmission(stack, monkeypatch):
    record = hit(dossier=[lead()])
    stack.seed(record)
    run = stack.enqueue()
    generate = Mock(return_value="committed opinion")
    monkeypatch.setattr(ai_transport, "generate", generate)
    original_get = stack.hits.get_if_exists
    failed_reads = []

    def fail_followup_read_once(*args, **kwargs):
        if kwargs.get("as_obj") is False and kwargs.get("version") is True and not failed_reads:
            failed_reads.append(kwargs["key"])
            raise ConnectionError("postcommit datastore read unavailable")
        return original_get(*args, **kwargs)

    monkeypatch.setattr(stack.hits, "get_if_exists", fail_followup_read_once)
    worker._process(claim())
    assert failed_reads == [record.howler.id]
    assert generate.call_count == 1
    assert queue.read_run(run["run_id"])["counts"]["succeeded"] == 1
    assert current_leads(stack, record)[0]["content"] == "committed opinion"
    assert queue.claim_next()[0] is None


def test_status_uses_realtime_classification_even_when_search_has_not_refreshed(stack, api_client):
    record = hit()
    stack.seed(record)
    run = stack.enqueue()
    client, _ = api_client
    stack.hits.datastore.client.indices.put_settings(index=stack.hits.index_name, settings={"refresh_interval": "-1"})
    record.classification = "R"
    stack.hits.save(record.howler.id, record, refresh="false")
    assert str(stack.hits.search("*:*", as_obj=True)["items"][0].classification) == "UNRESTRICTED"
    assert str(stack.hits.get(record.howler.id).classification) == "RESTRICTED"
    assert client.get(f"/api/v1/action/runs/{run['run_id']}").status_code == 404
    assert client.get("/api/v1/action/runs").get_json()["api_response"]["items"] == []


@pytest.mark.parametrize("revocation", ["role", "clearance", "disabled", "deleted"])
def test_worker_refreshes_initiator_revoked_during_provider_latency(stack, monkeypatch, revocation):
    record = hit(dossier=[lead()])
    if revocation == "clearance":
        stack.owner.classification = "R"
        stack.owner.access_control = "*:*"
        record.classification = "R"
        stack.users.save(stack.owner.uname, stack.owner)
    stack.seed(record)
    run = stack.enqueue()

    def provider(*_args, **_kwargs):
        fresh = stack.users.get(stack.owner.uname)
        if revocation == "deleted":
            stack.users.delete(fresh.uname)
        else:
            if revocation == "role":
                fresh.type = ["user"]
            elif revocation == "clearance":
                fresh.classification = "U"
            else:
                fresh.is_active = False
            stack.users.save(fresh.uname, fresh, refresh="false")
        return "must not be saved after revocation"

    monkeypatch.setattr(ai_transport, "generate", provider)
    worker._process(claim())
    final = queue.read_run(run["run_id"])
    assert final["counts"]["skipped"] == 1
    assert "_encrypted_bearer_token" not in final
    assert current_leads(stack, record)[0]["content"] == "old opinion"


@pytest.mark.parametrize("revocation", ["clearance", "disabled", "deleted", "hit_classification"])
def test_existing_authenticated_socket_rechecks_current_user_and_hit(stack, monkeypatch, revocation):
    record = hit()
    if revocation == "clearance":
        stack.owner.classification = "R"
        stack.owner.access_control = "*:*"
        record.classification = "R"
        stack.users.save(stack.owner.uname, stack.owner)
    stack.seed(record)
    run = stack.enqueue()
    payload = next(data for event, data in stack.events if event == "action")
    callbacks = {}
    ws = Mock(connected=False)
    ws.receive.return_value = "qa-socket-token"
    monkeypatch.setattr(socket_auth, "Server", lambda *_args, **_kwargs: ws)
    monkeypatch.setattr(socket_auth.auth_service, "bearer_auth", Mock(return_value=(stack.owner, ["R"])))
    monkeypatch.setattr(socket_api.comms_service, "on", lambda event, callback: callbacks.update({event: callback}))
    monkeypatch.setattr(socket_api.comms_service, "off", Mock())
    app = Flask(__name__)
    app.config.update(SECRET_KEY="qa-not-secret", TESTING=True)
    with app.test_request_context("/socket/v1/connect"):
        socket_api.connect()
    ws.send.reset_mock()
    callbacks["action"](payload)
    assert ws.send.call_count == 1
    assert json.loads(ws.send.call_args.args[0])["run_id"] == run["run_id"]
    if revocation == "hit_classification":
        record.classification = "R"
        stack.hits.save(record.howler.id, record, refresh="false")
    elif revocation == "deleted":
        stack.users.delete(stack.owner.uname)
    else:
        fresh = stack.users.get(stack.owner.uname)
        if revocation == "clearance":
            fresh.classification = "U"
        else:
            fresh.is_active = False
        stack.users.save(fresh.uname, fresh, refresh="false")
    ws.send.reset_mock()
    callbacks["action"](payload)
    ws.send.assert_not_called()


def test_active_run_outlives_sixty_second_retention_and_terminal_gets_full_ttl(stack):
    stack.config.retention_seconds = 60
    stack.seed(hit())
    run = stack.enqueue()
    run_key = queue._run_key(run["run_id"])
    assert stack.redis.ttl(run_key) == -1
    assert run["expires_at"] is None
    stack.clock.advance(61)
    job = claim()
    assert job["deadline_at"] == pytest.approx(stack.clock() + 600)
    for _ in range(50):
        stack.clock.advance(10)
        assert queue.heartbeat(job["run_id"], job["index"], job["nonce"])
    assert stack.redis.ttl(run_key) == -1
    assert service.get_run(run["run_id"], stack.owner) is not None
    final = finish(job, state="succeeded")
    assert final["expires_at"] is not None
    assert 59 <= stack.redis.ttl(run_key) <= 60
    assert "_encrypted_bearer_token" not in final


def test_disabled_worker_fails_queued_then_expired_work_and_scrubs_secrets(stack):
    stack.seed(hit(), hit())
    run = stack.enqueue()
    active = claim()
    stack.config.enabled = False
    _, still_active = queue.fail_pending_when_unavailable()
    interim = queue.read_run(run["run_id"])
    assert still_active is True
    assert interim["counts"]["running"] == 1 and interim["counts"]["failed"] == 1
    assert queue.lease_is_current(active["run_id"], active["index"], active["nonce"])
    stack.clock.advance(stack.config.lease_seconds + 1)
    _, still_active = queue.fail_pending_when_unavailable()
    final = queue.read_run(run["run_id"])
    assert still_active is False and final["counts"]["failed"] == 2
    assert final["state"] == "completed"
    assert "_encrypted_bearer_token" not in final
    assert stack.redis.llen(queue._queue_key()) == stack.redis.zcard(queue._lease_key()) == 0
    assert service.get_run(run["run_id"], stack.owner) is not None


def run_probe(stack, record, run, *, mode="gevent", settings=None, **options):
    probe = Path(__file__).parents[2] / "unit" / "ai_triage" / "worker_probe.py"
    payload = {
        "redis_url": os.environ.get("AI_TRIAGE_TEST_REDIS_URL", "redis://127.0.0.1:6379/15"),
        "es_url": os.environ.get("AI_TRIAGE_TEST_ES_URL", "http://127.0.0.1:9200"),
        "prefix": stack.prefix,
        "hit_collection": stack.hit_collection,
        "user_collection": stack.user_collection,
        "settings": settings or stack.config.model_dump(),
        "run_id": run["run_id"] if run else None,
        "owner": stack.owner.uname,
        "hit_id": record.howler.id,
        **options,
    }
    subprocess_support = runpy.run_path(str(probe.with_name("subprocess_support.py")))
    redis_url = urlparse(payload["redis_url"])
    es_url = urlparse(payload["es_url"])
    # Inert, explicitly isolated configuration for imports before the probe
    # installs its unique Redis namespace and datastore collection substitutions.
    bootstrap_settings = {
        "ui": {"debug": False},
        "auth": {"oauth": {"enabled": False}},
        "core": {
            "ai": {"enabled": False},
            "plugins": [],
            "telemetry": {"enabled": False},
            "redis": {
                kind: {"host": redis_url.hostname, "port": redis_url.port} for kind in ("persistent", "nonpersistent")
            },
        },
        "system": {name: {"enabled": False} for name in ("action_queue", "correlation", "retention", "view_cleanup")},
        "datastore": {"hosts": [{"name": "qa_probe", "scheme": es_url.scheme, "host": es_url.netloc}]},
    }
    env = subprocess_support["controlled_environment"](
        Path(service.__file__).resolve().parents[2],
        bootstrap_settings,
        TESTING="true",
        HWL_START_BACKGROUND_SERVICES="false",
        HWL_USE_JOB_SYSTEM="false",
        HWL_USE_REST_API="true",
        HWL_USE_WEBSOCKET_API="false",
        HWL_PLUGIN_DIRECTORY=str(probe.parent / "empty-plugins"),
        HWL_DATASTORE_INDEX_PREFIX=DATASTORE_INDEX_PREFIX,
    )
    result = subprocess.run(
        [sys.executable, str(probe), f"--mode={mode}", "--payload", json.dumps(payload)],
        capture_output=True,
        text=True,
        timeout=25,
        check=False,
        env=env,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(
        next(line.removeprefix("QA_RESULT=") for line in result.stdout.splitlines() if line.startswith("QA_RESULT="))
    )


@pytest.mark.parametrize("runtime", ["lease_loss", "slow_user_read"])
def test_patched_worker_cancels_http_and_preprovider_reads_at_real_boundaries(stack, runtime):
    record = hit()
    stack.seed(record)
    run = stack.enqueue()
    evidence = run_probe(stack, record, run, runtime=runtime)
    assert evidence["provider_calls"] == (1 if runtime == "lease_loss" else 0)


@pytest.mark.parametrize("provider,response_mode", [("openai", "json"), ("a2a", "json"), ("a2a", "sse")])
def test_real_transport_timeout_closes_trickling_response(stack, provider, response_mode):
    record = hit()
    stack.seed(record)
    run = stack.enqueue()
    settings = stack.config.model_dump()
    settings.update(provider=provider, timeout_seconds=1)
    evidence = run_probe(
        stack,
        record,
        run,
        settings=settings,
        runtime="provider_timeout",
        response_mode=response_mode,
    )
    assert evidence["response_closed"] and evidence["session_closed"]
    assert evidence["response_mode"] == response_mode


def test_worker_interrupted_a2a_stream_retries_by_polling_persisted_task(stack, monkeypatch):
    record = hit(dossier=[lead()])
    stack.seed(record)
    stack.config.provider = "a2a"
    run = stack.enqueue()
    methods = []

    def post(_session, _url, **kwargs):
        method = kwargs["json"]["method"]
        methods.append(method)
        task_result = {
            "kind": "task",
            "id": "accepted-task",
            "contextId": "accepted-context",
            "status": {"state": "working"},
        }
        result = requests.Response()
        result.status_code = 200
        result._content_consumed = True
        result._content = b""
        if method == "message/stream":
            assert len(methods) == 1, "An accepted task must never be submitted again"
            result.headers["Content-Type"] = "text/event-stream"

            def interrupted(**_kwargs):
                yield (
                    b"data: "
                    + json.dumps({"jsonrpc": "2.0", "id": kwargs["json"]["id"], "result": task_result}).encode()
                    + b"\n\n"
                )
                raise requests.exceptions.ChunkedEncodingError("connection broke after acceptance")

            result.iter_content = interrupted
        else:
            assert method == "tasks/get"
            assert kwargs["json"]["params"]["id"] == "accepted-task"
            result.headers["Content-Type"] = "application/json"
            cast(dict[str, str], task_result["status"])["state"] = "completed"
            task_result["artifacts"] = [
                {"artifactId": "opinion", "parts": [{"kind": "text", "text": "recovered opinion"}]}
            ]
            result._content = json.dumps({"jsonrpc": "2.0", "id": kwargs["json"]["id"], "result": task_result}).encode()
        return result

    monkeypatch.setattr(requests.Session, "post", post)
    worker._process(claim())
    persisted = queue.read_run(run["run_id"])
    assert persisted["results"][0]["_a2a_task_id"] == "accepted-task"
    assert persisted["results"][0]["state"] == "queued", (
        "A recoverable stream disconnect must not terminalize the accepted task"
    )
    assert current_leads(stack, record)[0]["content"] == "old opinion"
    worker._process(claim())
    assert methods == ["message/stream", "tasks/get"]
    assert queue.read_run(run["run_id"])["counts"]["succeeded"] == 1
    assert current_leads(stack, record)[0]["content"] == "recovered opinion"
