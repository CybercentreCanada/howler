"""Real Redis/Elasticsearch checks. Missing infrastructure fails rather than skips.

Use disposable local services and set AI_TRIAGE_TEST_REDIS_URL and
AI_TRIAGE_TEST_ES_URL. Only unique test-owned Redis keys and ES indices are removed.
"""

import hashlib
import json
import os
import runpy
import subprocess
import sys
import threading
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
from howler.datastore.exceptions import VersionConflictException
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


def candidate_with_changed_provenance(candidate, **changes):
    """Independently hash a valid, different canonical opinion with identical text."""
    changed = deepcopy(candidate)
    provenance = json.loads(changed["metadata"])
    provenance.pop("candidate_sha256")
    provenance.update(changes)
    digest = hashlib.sha256(
        json.dumps(
            {key: changed[key] for key in ("content", "label", "format")} | {"metadata": provenance},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    changed.update(
        digest=digest,
        source_version=provenance["source_version"],
        metadata=json.dumps(provenance | {"candidate_sha256": digest}, sort_keys=True, separators=(",", ":")),
    )
    return changed


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


def reconcile(*, allow_write=True):
    job, _ = queue.claim_reconciliation()
    assert job is not None
    worker._process_reconciliation(job, allow_write=allow_write)
    return job


def current_leads(stack, record):
    return stack.hits.get(record.howler.id).as_primitives()["howler"]["dossier"]


def test_real_elasticsearch_rejects_stale_full_record_save(es_hits):
    """Verify the actual datastore CAS primitive used by AI's safe dossier update."""
    hit = Hit({"classification": "U", "howler": {"analytic": "QA triage", "hash": "123abc"}})
    es_hits.save(hit.howler.id, hit)
    stale, stale_version = es_hits.get(hit.howler.id, version=True)
    concurrent, current_version = es_hits.get(hit.howler.id, version=True)
    concurrent.howler.assignment = "another-analyst"
    hit_service.save_hit(concurrent, version=current_version)

    stale.howler.assignment = "must-not-win"
    with pytest.raises(VersionConflictException):
        hit_service.save_hit(stale, version=stale_version)

    assert es_hits.get(hit.howler.id).howler.assignment == "another-analyst"


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


@pytest.mark.parametrize("operation", ["heartbeat", "lease_is_current"])
def test_expired_lease_cannot_be_revived_before_another_worker_claims(stack, operation):
    stack.seed(hit())
    stack.enqueue()
    job = claim()
    stack.clock.advance(stack.config.lease_seconds + 1)
    assert not getattr(queue, operation)(job["run_id"], job["index"], job["nonce"])


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
    assert "_encrypted_bearer_token" not in raw and "_auth_scheme" not in raw and "_prompt" not in raw
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


def test_worker_uses_frozen_ids_current_data_and_preserves_non_ai_fields(stack, monkeypatch):
    record = hit(dossier=[lead(), lead("analyst note", "analyst")])
    stack.seed(record)
    run = stack.enqueue(prompt="concise please")
    record.event.original = "worker-time data"
    stack.seed(record, hit())  # New query match must not enter the frozen run.
    before = stack.hits.get(record.howler.id).as_primitives()
    generate = Mock(return_value="new opinion")
    monkeypatch.setattr(ai_transport, "generate", generate)
    worker._process(claim())
    generate.assert_called_once()
    sent = generate.call_args.args[3]
    assert sent["event"]["original"] == "worker-time data"
    assert "dossier" not in sent["howler"] and "log" not in sent["howler"]
    assert generate.call_args.args[1] == "qa-real-bearer"
    assert "concise please" in generate.call_args.args[2]
    assert queue.claim_next()[0] is None
    after = stack.hits.get(record.howler.id).as_primitives()
    assert [item["content"] for item in after["howler"]["dossier"]] == ["analyst note", "new opinion"]
    before["howler"].pop("dossier")
    after["howler"].pop("dossier")
    assert after == before
    assert queue.read_run(run["run_id"])["counts"]["succeeded"] == 1


def test_worker_converts_epoch_deadline_once_before_delayed_reads_to_distinct_monotonic_origin(stack, monkeypatch):
    record = hit()
    stack.seed(record)
    stack.config.lease_seconds = 120
    run = stack.enqueue()
    job = claim()
    stack.clock.advance(17)  # Time spent claimed before entering the processing greenlet.
    monotonic = SimpleNamespace(now=12_345.0)
    initial_epoch = stack.clock()
    initial_monotonic = monotonic.now
    expected_deadline = initial_monotonic + job["deadline_at"] - initial_epoch

    def advance(seconds):
        stack.clock.advance(seconds)
        monotonic.now += seconds

    clocks = SimpleNamespace(time=stack.clock, monotonic=lambda: monotonic.now, sleep=advance)
    for module in (worker, service, ai_transport):
        monkeypatch.setattr(module, "time", clocks)
    original_user = service.get_current_user
    original_hit = service.get_current_hit
    delayed_reads = []

    def delayed_user(*args):
        result = original_user(*args)
        delayed_reads.append("user")
        advance(3)
        return result

    def delayed_hit(*args):
        result = original_hit(*args)
        delayed_reads.append("hit")
        advance(3)
        return result

    def assert_absolute_budget(*_args, **kwargs):
        assert "remaining" not in kwargs
        assert kwargs["deadline"] == pytest.approx(expected_deadline)
        assert abs(kwargs["deadline"] - job["deadline_at"]) > 1_000_000
        assert delayed_reads.count("user") >= 1 and delayed_reads.count("hit") >= 1
        elapsed = monotonic.now - initial_monotonic
        assert elapsed >= 6
        assert kwargs["deadline"] - monotonic.now == pytest.approx(600 - 17 - elapsed)
        assert kwargs["begin_attempt"]()
        return "absolute monotonic budget verified"

    monkeypatch.setattr(service, "get_current_user", delayed_user)
    monkeypatch.setattr(service, "get_current_hit", delayed_hit)
    generate = Mock(side_effect=assert_absolute_budget)
    monkeypatch.setattr(ai_transport, "generate", generate)
    worker._process(job)
    generate.assert_called_once()
    # Mock-side assertions cannot be swallowed into a provider_error result.
    assert queue.read_run(run["run_id"])["counts"]["succeeded"] == 1
    assert current_leads(stack, record)[0]["content"] == "absolute monotonic budget verified"


@pytest.mark.parametrize("change", [{"status": "resolved"}, {"assessment": "legitimate"}])
@pytest.mark.parametrize("timing", ["before_http", "before_save"])
def test_worker_rechecks_real_eligibility_at_each_race_boundary(stack, monkeypatch, change, timing):
    record = hit(dossier=[lead()])
    stack.seed(record)
    run = stack.enqueue()

    def mutate():
        fresh, version = stack.hits.get(record.howler.id, version=True)
        for key, value in change.items():
            setattr(fresh.howler, key, value)
        stack.hits.save(record.howler.id, fresh, version=version)

    def provider(*_args, **_kwargs):
        mutate()
        return "must not be saved"

    generate = Mock(side_effect=provider if timing == "before_save" else None, return_value="must not be sent")
    monkeypatch.setattr(ai_transport, "generate", generate)
    if timing == "before_http":
        mutate()
    worker._process(claim())
    assert generate.call_count == (1 if timing == "before_save" else 0)
    assert current_leads(stack, record)[0]["content"] == "old opinion"
    assert queue.read_run(run["run_id"])["counts"]["skipped"] == 1


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
    generate = Mock(return_value="new")
    if failure == "http":
        generate.side_effect = ai_transport.AITransportError("Provider rejected the authorization token")
    elif failure == "save":
        monkeypatch.setattr(stack.hits, "save", Mock(side_effect=RuntimeError("private datastore details")))
    else:
        original_save = stack.hits.save

        def conflict(key, updated, *, version):
            fresh, current_version = stack.hits.get(record.howler.id, version=True)
            original_save(key, fresh, version=current_version)
            return original_save(key, updated, version=version)

        monkeypatch.setattr(stack.hits, "save", conflict)
    monkeypatch.setattr(ai_transport, "generate", generate)
    worker._process(claim())
    assert current_leads(stack, record) == original
    final = queue.read_run(run["run_id"])
    if failure == "http":
        assert final["counts"]["failed"] == 1
    else:
        assert final["state"] == "running"
        assert final["results"][0]["reason"] == "write_reconciliation_pending"
        stack.clock.advance(stack.config.retention_seconds + 1)
        assert queue.claim_reconciliation()[0] is None
        final = queue.read_run(run["run_id"])
        assert final["results"][0]["reason"] == "write_outcome_unknown"
    assert queue.claim_next()[0] is None
    assert "private datastore details" not in json.dumps(service.public_run(final))


def test_disabled_after_enqueue_fails_closed_without_provider_call(stack, monkeypatch):
    record = hit(dossier=[lead()])
    stack.seed(record)
    run = stack.enqueue()
    stack.config.enabled = False
    worker._process(claim())  # Real generate refuses disabled config before opening HTTP.
    assert queue.read_run(run["run_id"])["counts"]["failed"] == 1
    assert current_leads(stack, record)[0]["content"] == "old opinion"
    assert service.get_run(run["run_id"], stack.owner) is not None


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


@pytest.mark.parametrize("query", ["rows=0", "offset=-1", "rows=not-a-number", "operation_id=unknown"])
def test_run_list_rejects_invalid_parameters_without_bypassing_auth(stack, api_client, query):
    client, auth = api_client
    assert client.get(f"/api/v1/action/runs?{query}").status_code == 400
    assert auth.bearer_auth.called


def test_deleted_or_expired_run_is_hidden(stack, api_client):
    record = hit()
    stack.seed(record)
    run = stack.enqueue()
    client, _ = api_client
    stack.hits.delete(record.howler.id, refresh="true")
    assert client.get(f"/api/v1/action/runs/{run['run_id']}").status_code == 404
    stack.seed(record)
    raw = queue.read_run(run["run_id"])
    raw["_expires_at"] = 1
    stack.redis.set(queue._run_key(run["run_id"]), json.dumps(raw))
    assert client.get(f"/api/v1/action/runs/{run['run_id']}").status_code == 404


def test_progress_event_is_persisted_first_and_contains_no_target_or_failure_details(stack, monkeypatch):
    stack.seed(hit())
    run = stack.enqueue()
    monkeypatch.setattr(ai_transport, "generate", Mock(side_effect=RuntimeError("provider-secret")))
    worker._process(claim())
    events = [data for event, data in stack.events if event == "action"]
    assert len(events) >= 3  # queued, running, terminal; stack.emit verifies persistence ordering.
    assert all(
        set(data) == {"operation_id", "run_id", "request_id", "revision", "state", "processed", "total", "recipient"}
        for data in events
    )
    assert events[-1]["state"] == "completed" and events[-1]["processed"] == 1
    assert all(data["recipient"] == stack.owner.uname for data in events)
    assert "provider-secret" not in json.dumps(events)
    assert run["results"][0]["hit_id"] not in json.dumps(events)


def test_worker_cannot_save_with_nonce_replaced_during_fresh_read(stack, monkeypatch):
    record = hit(dossier=[lead()])
    stack.seed(record)
    stack.enqueue()
    old_job = claim()
    monkeypatch.setattr(ai_transport, "generate", Mock(return_value="stale worker opinion"))
    original_get = service.get_current_hit
    original_save = service.save_ai_lead
    in_save = False
    new_jobs = []

    def save_with_observed_read(*args, **kwargs):
        nonlocal in_save
        in_save = True
        return original_save(*args, **kwargs)

    def lose_lease_during_read(*args):
        result = original_get(*args)
        if in_save and not new_jobs:
            stack.clock.advance(stack.config.lease_seconds + 1)
            replacement, _ = queue.claim_reconciliation()
            assert replacement is not None
            new_jobs.append(replacement)
        return result

    monkeypatch.setattr(service, "save_ai_lead", save_with_observed_read)
    monkeypatch.setattr(service, "get_current_hit", lose_lease_during_read)
    worker._process(old_job)
    assert new_jobs and new_jobs[0]["nonce"] != old_job["nonce"]
    assert current_leads(stack, record)[0]["content"] == "old opinion"


class SimulatedCrash(BaseException):
    pass


@pytest.mark.parametrize("crash_after_save", [False, True])
def test_worker_recovers_completed_candidate_without_second_provider_call(stack, monkeypatch, crash_after_save):
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
    reconcile()
    assert generate.call_count == 1, "A completed candidate must be durable across save/ack crash windows"
    assert [item["content"] for item in current_leads(stack, record)] == ["durable candidate"]


def test_recovered_a2a_task_polls_checkpoint_instead_of_submitting_again(stack, monkeypatch):
    record = hit()
    stack.seed(record)
    stack.config.provider = "a2a"
    stack.enqueue()
    first = claim()
    assert queue.checkpoint(first["run_id"], first["index"], first["nonce"], "task-qa", "context-qa")
    stack.clock.advance(stack.config.lease_seconds + 1)
    methods = []

    def post(_session, _url, **kwargs):
        methods.append(kwargs["json"]["method"])
        result = requests.Response()
        result.status_code = 200
        result.headers["Content-Type"] = "application/json"
        result._content_consumed = True
        result._content = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": kwargs["json"]["id"],
                "result": {
                    "kind": "task",
                    "id": "task-qa",
                    "contextId": "context-qa",
                    "status": {"state": "completed"},
                    "artifacts": [{"artifactId": "opinion", "parts": [{"kind": "text", "text": "recovered"}]}],
                },
            }
        ).encode()
        return result

    monkeypatch.setattr(requests.Session, "post", post)
    worker._process(claim())
    assert methods == ["tasks/get"]
    assert current_leads(stack, record)[0]["content"] == "recovered"


@pytest.mark.parametrize("http_status,attempts", [(401, 1), (403, 1), (429, 3), (503, 3)])
def test_worker_actual_transport_classifies_auth_and_transient_attempt_budget(
    stack, monkeypatch, caplog, http_status, attempts
):
    record = hit(dossier=[lead()])
    stack.seed(record)
    run = stack.enqueue()
    requests_made = []

    def post(_session, _url, **kwargs):
        requests_made.append(kwargs)
        result = requests.Response()
        result.status_code = http_status
        result._content_consumed = True
        result._content = b'{"error":"private-provider-response"}'
        return result

    monkeypatch.setattr(requests.Session, "post", post)
    for _ in range(attempts):
        worker._process(claim())
    assert queue.claim_next()[0] is None
    final = queue.read_run(run["run_id"])
    assert len(requests_made) == attempts
    assert final["results"][0]["attempts"] == attempts
    assert final["counts"]["failed"] == 1
    assert "_encrypted_bearer_token" not in final
    assert "private-provider-response" not in caplog.text + json.dumps(service.public_run(final))
    assert all(request["headers"]["Authorization"] == "Bearer qa-real-bearer" for request in requests_made)
    assert current_leads(stack, record)[0]["content"] == "old opinion"


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


def test_provider_cannot_save_after_absolute_deadline(stack, monkeypatch):
    record = hit(dossier=[lead()])
    stack.seed(record)
    run = stack.enqueue()

    def too_late(*_args, **_kwargs):
        stack.clock.advance(601)
        return "late response"

    monkeypatch.setattr(ai_transport, "generate", too_late)
    worker._process(claim())
    assert queue.claim_next()[0] is None  # Sweeps the expired lease and terminates the run.
    assert queue.read_run(run["run_id"])["counts"]["failed"] == 1
    assert current_leads(stack, record)[0]["content"] == "old opinion"


def test_run_routes_enforce_read_privilege(stack, api_client):
    stack.seed(hit())
    run = stack.enqueue()
    client, auth = api_client
    auth.bearer_auth.return_value = (stack.owner, ["E"])
    assert client.get("/api/v1/action/runs").status_code == 403
    assert client.get(f"/api/v1/action/runs/{run['run_id']}").status_code == 403


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


@pytest.mark.parametrize("revocation", ["missing_user", "bad_ciphertext", "unproven_auth"])
def test_worker_authentication_failure_is_terminal_and_scrubs_credentials(stack, monkeypatch, revocation, caplog):
    record = hit(dossier=[lead()])
    stack.seed(record)
    run = stack.enqueue()
    raw = queue.read_run(run["run_id"])
    if revocation == "missing_user":
        stack.users.delete(stack.owner.uname)
    elif revocation == "bad_ciphertext":
        raw["_encrypted_bearer_token"] = "invalid-secret-ciphertext"
    else:
        raw["_auth_scheme"] = "Basic"
    stack.redis.set(queue._run_key(run["run_id"]), json.dumps(raw))
    generate = Mock()
    monkeypatch.setattr(ai_transport, "generate", generate)
    worker._process(claim())
    generate.assert_not_called()
    final = queue.read_run(run["run_id"])
    assert final["results"][0]["reason"] == "authentication_unavailable"
    assert final["counts"]["failed"] == 1 and final["results"][0]["attempts"] == 0
    assert "_encrypted_bearer_token" not in final
    assert "invalid-secret-ciphertext" not in caplog.text + json.dumps(service.public_run(final))
    assert current_leads(stack, record)[0]["content"] == "old opinion"


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


def test_heartbeat_loop_cancels_processing_when_nonce_is_replaced(stack):
    stack.seed(hit())
    stack.enqueue()
    old_job = claim()
    stack.clock.advance(stack.config.lease_seconds + 1)
    new_job = claim()
    processing = Mock()
    worker._heartbeat_loop(
        old_job["run_id"],
        old_job["index"],
        old_job["nonce"],
        old_job["lease_expiry"],
        old_job["deadline_at"],
        processing,
    )
    processing.kill.assert_called_once_with(block=False)
    assert queue.lease_is_current(new_job["run_id"], new_job["index"], new_job["nonce"])


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


def test_expired_owner_cannot_checkpoint_or_ack_without_recovery(stack):
    stack.seed(hit())
    stack.enqueue()
    job = claim()
    stack.clock.advance(stack.config.lease_seconds + 1)
    assert not queue.checkpoint(job["run_id"], job["index"], job["nonce"], "stale-task", None)
    assert finish(job, state="succeeded") is None


def test_paused_real_redis_claim_cannot_commit_after_lock_expiry_or_exceed_four(stack, monkeypatch):
    stack.seed(hit())
    for index in range(6):
        stack.enqueue(user=analyst(f"fenced-owner-{index}"))
    monkeypatch.setattr(queue, "QUEUE_LOCK_TTL", 0.5)
    paused = threading.Event()
    resume = threading.Event()
    original_load = queue._load_run

    def pause_old_claim(client, run_id):
        result = original_load(client, run_id)
        if threading.current_thread().name.startswith("qa-paused-claim") and not paused.is_set():
            paused.set()
            assert resume.wait(5), "Test did not release the paused claimer"
        return result

    monkeypatch.setattr(queue, "_load_run", pause_old_claim)
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="qa-paused-claim") as pool:
        stale = pool.submit(queue.claim_next)
        try:
            assert paused.wait(3)
            ttl = stack.redis.pttl(queue._global_lock_key())
            assert ttl > 0
            time.sleep((ttl + 100) / 1000)
            assert stack.redis.get(queue._global_lock_key()) is None
            jobs = [claim() for _ in range(4)]
            assert stack.redis.zcard(queue._lease_key()) == 4
        finally:
            resume.set()
        with pytest.raises(WatchError):
            stale.result(timeout=3)
    assert len({job["nonce"] for job in jobs}) == 4
    assert stack.redis.zcard(queue._lease_key()) == 4
    assert stack.redis.llen(queue._queue_key()) == 2
    assert queue.claim_next()[0] is None
    assert all(queue.lease_is_current(job["run_id"], job["index"], job["nonce"]) for job in jobs)


@pytest.mark.parametrize("paused_read", [2, 4])
def test_cas_commit_read_and_retry_are_fenced_by_current_lease(stack, monkeypatch, paused_read):
    record = hit(dossier=[lead()])
    stack.seed(record)
    stack.enqueue()
    old = claim()
    original_get = service.get_current_hit
    original_save = stack.hits.save
    reads = 0
    replacement = []
    saved_versions = []

    def get_with_takeover(*args):
        nonlocal reads
        result = original_get(*args)
        reads += 1
        if reads == paused_read:
            stack.clock.advance(stack.config.lease_seconds + 1)
            replacement.append(claim())
        return result

    def real_conflict(key, updated, *, version):
        saved_versions.append(version)
        concurrent, current_version = stack.hits.get(record.howler.id, version=True)
        concurrent.howler.assignment = "concurrent-human"
        original_save(key, concurrent, version=current_version)
        return original_save(key, updated, version=version)

    monkeypatch.setattr(service, "get_current_hit", get_with_takeover)
    monkeypatch.setattr(stack.hits, "save", real_conflict)
    result = service.save_ai_lead(
        record.howler.id,
        stack.owner,
        service.prepare_candidate("stale candidate", old["run_id"], "0"),
        lease_check=lambda: queue.lease_is_current(old["run_id"], old["index"], old["nonce"]),
    )
    assert result == (False, "lease_lost")
    assert replacement and replacement[0]["nonce"] != old["nonce"]
    assert len(saved_versions) == (1 if paused_read == 4 else 0)
    assert current_leads(stack, record)[0]["content"] == "old opinion"


def test_postcommit_read_failure_reconciles_actual_saved_lead_without_resubmission(stack, monkeypatch):
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


def test_disabled_reconciler_drains_queued_then_expired_work_and_scrubs_secrets(stack):
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


@pytest.mark.parametrize("mode", ["native", "gevent"])
def test_worker_probe_rejects_hostile_inherited_configuration_before_imports(stack, monkeypatch, tmp_path, mode):
    support_path = Path(__file__).parents[2] / "unit" / "ai_triage" / "subprocess_support.py"
    support = runpy.run_path(str(support_path))
    record = hit()
    stack.seed(record)
    run = stack.enqueue()
    with support["hostile_parent_environment"](monkeypatch, tmp_path):
        evidence = run_probe(stack, record, run, mode=mode)
    assert evidence["provider_calls"] == (1 if mode == "gevent" else 0)
    assert evidence["legacy_workers"] == 0


@pytest.mark.parametrize("mode", ["native", "gevent"])
@pytest.mark.parametrize("scenario", ["enabled", "disabled", "trigger", "late-disabled"])
def test_actual_subprocess_startup_drains_work_without_scheduled_job_system(stack, mode, scenario):
    record = hit()
    stack.seed(record)
    run = stack.enqueue() if scenario != "trigger" else None
    settings = stack.config.model_dump()
    settings["enabled"] = scenario not in {"disabled", "late-disabled"}
    late_run = None
    if scenario == "late-disabled":
        late_run = queue.read_run(run["run_id"])
        keys = list(stack.redis.scan_iter(match=f"{stack.prefix}:*"))
        stack.redis.delete(*keys)
    evidence = run_probe(
        stack, record, run, mode=mode, settings=settings, trigger=scenario == "trigger", late_run=late_run
    )
    if mode == "native" and settings["enabled"]:
        assert evidence["unsupported"] is True
        assert evidence["provider_calls"] == 0
        assert not current_leads(stack, record)
        return
    assert evidence["provider_calls"] == (1 if settings["enabled"] else 0)
    assert evidence["legacy_workers"] == (5 if scenario == "trigger" else 0)
    if settings["enabled"]:
        assert current_leads(stack, record)[0]["content"] == "subprocess opinion"


def test_real_http_slow_json_trickle_cannot_hold_worker_past_absolute_budget(stack):
    record = hit()
    stack.seed(record)
    run = stack.enqueue()
    evidence = run_probe(stack, record, run, runtime="slow_json")
    assert evidence["provider_calls"] == 1 and evidence["cancelled_in"] < 1.2


@pytest.mark.parametrize("provider,response_mode", [("openai", "json"), ("a2a", "json"), ("a2a", "sse")])
def test_real_frequent_byte_trickle_honors_shorter_provider_timeout_and_closes_contexts(stack, provider, response_mode):
    record = hit()
    stack.seed(record)
    stack.config.provider = provider
    run = stack.enqueue()
    evidence = run_probe(stack, record, run, runtime="provider_timeout", response_mode=response_mode)
    assert evidence["provider_calls"] == 1 and 0.75 < evidence["cancelled_in"] < 1.7
    assert evidence["response_closed"] and evidence["session_closed"]
    assert evidence["response_mode"] == response_mode


@pytest.mark.parametrize("runtime", ["lease_loss", "slow_user_read"])
def test_patched_worker_cancels_http_and_preprovider_reads_at_real_boundaries(stack, runtime):
    record = hit()
    stack.seed(record)
    run = stack.enqueue()
    evidence = run_probe(stack, record, run, runtime=runtime)
    assert evidence["provider_calls"] == (1 if runtime == "lease_loss" else 0)


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


def test_candidate_is_set_once_with_fixed_complete_lead_and_independent_digest(stack):
    record = hit(dossier=[lead()])
    stack.seed(record)
    run = stack.enqueue()
    job = claim()
    candidate = service.prepare_candidate("immutable opinion", run["run_id"], "0")
    metadata = json.loads(candidate["metadata"])
    expected_hash = hashlib.sha256(
        json.dumps(
            {
                "content": candidate["content"],
                "label": candidate["label"],
                "format": candidate["format"],
                "metadata": {key: value for key, value in metadata.items() if key != "candidate_sha256"},
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    assert candidate["digest"] == metadata["candidate_sha256"] == expected_hash
    assert metadata["source_version"] == "0" and metadata["generated_at"]
    assert queue.store_candidate(job["run_id"], job["index"], job["nonce"], candidate)
    assert queue.store_candidate(job["run_id"], job["index"], job["nonce"], deepcopy(candidate))
    different = service.prepare_candidate("different output", run["run_id"], "new-source-version")
    assert not queue.store_candidate(job["run_id"], job["index"], job["nonce"], different)
    assert not queue.store_candidate(job["run_id"], job["index"], "stale-nonce", candidate)
    assert queue.read_run(run["run_id"])["results"][0]["_candidate"] == candidate


@pytest.mark.parametrize(
    "metadata_change", [{"source_version": "new-version"}, {"generated_at": "2040-01-01T00:00:00Z"}]
)
def test_candidate_set_once_rejects_same_text_and_run_with_valid_different_provenance(stack, metadata_change):
    stack.seed(hit())
    run = stack.enqueue()
    job = claim()
    candidate = service.prepare_candidate("same immutable text", run["run_id"], "original-version")
    assert queue.store_candidate(job["run_id"], job["index"], job["nonce"], candidate)
    original = stack.redis.dump(queue._run_key(run["run_id"]))
    changed = candidate_with_changed_provenance(candidate, **metadata_change)
    assert service.candidate_is_valid(changed), "This case must exercise set-once identity, not invalid input rejection"
    assert changed["content"] == candidate["content"] and changed["digest"] != candidate["digest"]
    assert json.loads(changed["metadata"])["run_id"] == run["run_id"]
    assert not queue.store_candidate(job["run_id"], job["index"], job["nonce"], changed)
    assert stack.redis.dump(queue._run_key(run["run_id"])) == original
    assert queue.read_run(run["run_id"])["results"][0]["_candidate"] == candidate


@pytest.mark.parametrize("field", ["content", "metadata", "digest", "source_version"])
def test_tampered_canonical_candidate_cannot_write(stack, field):
    record = hit(dossier=[lead()])
    stack.seed(record)
    candidate = service.prepare_candidate("valid", "run-qa", "0")
    candidate[field] = "tampered"
    assert service.save_ai_lead(record.howler.id, stack.owner, candidate) == (False, "candidate_invalid")
    assert current_leads(stack, record)[0]["content"] == "old opinion"


@pytest.mark.parametrize("replacement_first", [False, True])
def test_suspended_committer_after_final_check_can_only_write_identical_candidate_safely(
    stack, monkeypatch, replacement_first
):
    record = hit(dossier=[lead(), lead("human note", "human")])
    stack.seed(record)
    run = stack.enqueue()
    old = claim()
    candidate = service.prepare_candidate("canonical opinion", run["run_id"], "0")
    assert queue.store_candidate(old["run_id"], old["index"], old["nonce"], candidate)
    assert queue.set_commit_phase(old["run_id"], old["index"], old["nonce"], "write_pending")
    entered = threading.Event()
    resume = threading.Event()
    original_save = stack.hits.save
    writes = []

    def paused_after_last_check(key, updated, **kwargs):
        if threading.current_thread().name.startswith("qa-stale-committer"):
            entered.set()
            assert resume.wait(8)
        writes.append(deepcopy(updated.as_primitives()["howler"]["dossier"][-1]))
        return original_save(key, updated, **kwargs)

    monkeypatch.setattr(stack.hits, "save", paused_after_last_check)
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="qa-stale-committer") as pool:
        stale = pool.submit(
            service.save_ai_lead,
            record.howler.id,
            stack.owner,
            candidate,
            lease_check=lambda: queue.lease_is_current(old["run_id"], old["index"], old["nonce"]),
        )
        try:
            assert entered.wait(4)
            stack.clock.advance(stack.config.lease_seconds + 1)
            replacement, _ = queue.claim_reconciliation()
            assert replacement is not None and replacement["nonce"] != old["nonce"]
            assert replacement["candidate"] == candidate
            if replacement_first:
                human, version = stack.hits.get(record.howler.id, version=True)
                human.howler.assignment = "new-human-assignee"
                human.howler.dossier.append(lead("new human note", "human"))
                original_save(record.howler.id, human, version=version)
                worker._process_reconciliation(replacement, allow_write=True)
        finally:
            resume.set()
        outcome = stale.result(timeout=4)
    assert outcome == ((False, "lease_lost") if replacement_first else (True, None))
    assert finish(old, state="succeeded") is None
    if not replacement_first:
        worker._process_reconciliation(replacement, allow_write=True)
    current = stack.hits.get(record.howler.id)
    managed = [entry for entry in current.howler.dossier if json.loads(entry.metadata)["owner"] == service.LEAD_OWNER]
    assert len(managed) == 1
    assert managed[0].content == candidate["content"]
    assert json.loads(managed[0].metadata) == json.loads(candidate["metadata"])
    assert all(
        entry["content"] == candidate["content"] and json.loads(entry["metadata"]) == json.loads(candidate["metadata"])
        for entry in writes
    )
    assert any(entry.content == "human note" for entry in current.howler.dossier)
    if replacement_first:
        assert current.howler.assignment == "new-human-assignee"
        assert any(entry.content == "new human note" for entry in current.howler.dossier)
    assert queue.read_run(run["run_id"])["counts"]["succeeded"] == 1


@pytest.mark.parametrize("after_commit", [False, True])
def test_third_provider_attempt_crash_recovers_candidate_or_save_without_fourth_request(
    stack, monkeypatch, after_commit
):
    record = hit(dossier=[lead()])
    stack.seed(record)
    run = stack.enqueue()
    requests_made = []

    def post(_session, _url, **kwargs):
        requests_made.append(kwargs)
        response = requests.Response()
        response._content_consumed = True
        response.status_code = 503 if len(requests_made) < 3 else 200
        response._content = json.dumps(
            {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "third attempt canonical output"},
                    }
                ]
            }
        ).encode()
        return response

    monkeypatch.setattr(requests.Session, "post", post)
    worker._process(claim())
    worker._process(claim())
    owner = queue if after_commit else service
    boundary = "finish_item" if after_commit else "save_ai_lead"
    original_boundary = getattr(owner, boundary)
    monkeypatch.setattr(owner, boundary, Mock(side_effect=SimulatedCrash))
    with pytest.raises(SimulatedCrash):
        worker._process(claim())
    monkeypatch.setattr(owner, boundary, original_boundary)
    snapshot = queue.read_run(run["run_id"])["results"][0]
    assert snapshot["attempts"] == 3 and len(requests_made) == 3
    canonical = snapshot["_candidate"]
    stack.clock.advance(stack.config.lease_seconds + 1)
    reconcile()
    final = queue.read_run(run["run_id"])
    assert final["counts"]["succeeded"] == 1 and final["results"][0]["attempts"] == 3
    assert len(requests_made) == 3
    saved = current_leads(stack, record)[0]
    assert saved["content"] == canonical["content"]
    assert json.loads(saved["metadata"]) == json.loads(canonical["metadata"])


@pytest.mark.parametrize("restore_reads", [False, True])
@pytest.mark.parametrize("disabled", [False, True])
def test_lost_es_response_and_all_reads_fail_reconcile_readonly_after_deadline(
    stack, monkeypatch, restore_reads, disabled
):
    record = hit(dossier=[lead()])
    stack.seed(record)
    run = stack.enqueue()
    original_save = stack.hits.save
    original_get = service.get_current_hit
    submitted = False
    blocked = True
    writes = []
    read_failures = []

    def lost_response(key, updated, **kwargs):
        nonlocal submitted
        writes.append(deepcopy(updated.as_primitives()))
        original_save(key, updated, **kwargs)
        submitted = True
        raise ConnectionError("lost acknowledgement after ES committed")

    def unavailable_reads(*args):
        if submitted and blocked:
            read_failures.append(True)
            raise ConnectionError("all immediate datastore reads unavailable")
        return original_get(*args)

    def provider(*_args, **kwargs):
        assert kwargs["begin_attempt"]()
        return "persisted but unacknowledged"

    generate = Mock(side_effect=provider)
    monkeypatch.setattr(ai_transport, "generate", generate)
    monkeypatch.setattr(stack.hits, "save", lost_response)
    monkeypatch.setattr(service, "get_current_hit", unavailable_reads)
    worker._process(claim())
    pending = queue.read_run(run["run_id"])
    item = pending["results"][0]
    assert pending["state"] == "running" and item["reason"] == "write_reconciliation_pending"
    assert item["_write_intent"] and item["_candidate"] and len(read_failures) >= service.CAS_RETRIES
    assert len(writes) == generate.call_count == 1
    canonical = item["_candidate"]
    stack.config.enabled = not disabled
    stack.clock.advance(601)
    reconcile(allow_write=not disabled)
    assert queue.read_run(run["run_id"])["state"] == "running"
    if restore_reads:
        blocked = False
        stack.clock.advance(10)
        reconcile(allow_write=not disabled)
        final = queue.read_run(run["run_id"])
        assert final["counts"]["succeeded"] == 1
    else:
        horizon = queue.read_run(run["run_id"])["results"][0]["_reconcile_horizon_at"]
        stack.clock.advance(horizon - stack.clock() + 1)
        assert queue.claim_reconciliation()[0] is None
        final = queue.read_run(run["run_id"])
        assert final["results"][0]["reason"] == "write_outcome_unknown"
        assert "could not be confirmed" in final["results"][0]["message"]
        assert "may have been replaced" in final["results"][0]["message"]
    assert len(writes) == generate.call_count == 1
    assert "_encrypted_bearer_token" not in final
    actual, _ = original_get(record.howler.id, stack.owner)
    assert service.has_managed_candidate(actual, canonical)


def test_postwrite_notification_failure_does_not_undo_confirmed_persistence(stack, monkeypatch):
    record = hit(dossier=[lead()])
    stack.seed(record)
    run = stack.enqueue()
    original_emit = service.comms_service.emit

    def notification_fails(event, data):
        if event == "hits":
            raise ConnectionError("notification connection down after commit")
        original_emit(event, data)

    monkeypatch.setattr(service.comms_service, "emit", notification_fails)
    generate = Mock(return_value="confirmed despite notification failure")
    monkeypatch.setattr(ai_transport, "generate", generate)
    worker._process(claim())
    assert generate.call_count == 1
    assert queue.read_run(run["run_id"])["counts"]["succeeded"] == 1
    assert current_leads(stack, record)[0]["content"] == "confirmed despite notification failure"


def test_third_a2a_attempt_crash_resumes_task_without_fourth_inference(stack, monkeypatch):
    record = hit(dossier=[lead()])
    stack.seed(record)
    stack.config.provider = "a2a"
    run = stack.enqueue()
    methods = []

    def post(_session, _url, **kwargs):
        method = kwargs["json"]["method"]
        methods.append(method)
        response = requests.Response()
        response._content_consumed = True
        response._content = b"{}"
        response.status_code = 503 if len(methods) < 3 else 200
        task = {
            "kind": "task",
            "id": "third-attempt-task",
            "contextId": "fixed-context",
            "status": {"state": "working"},
        }
        if len(methods) == 3:
            assert method == "message/stream"
            response.headers["Content-Type"] = "text/event-stream"

            def checkpoint_then_crash(**_kwargs):
                yield (
                    b"data: "
                    + json.dumps({"jsonrpc": "2.0", "id": kwargs["json"]["id"], "result": task}).encode()
                    + b"\n\n"
                )
                raise SimulatedCrash()

            response.iter_content = checkpoint_then_crash
        elif len(methods) > 3:
            assert method == "tasks/get" and kwargs["json"]["params"]["id"] == task["id"]
            response.headers["Content-Type"] = "application/json"
            cast(dict[str, str], task["status"])["state"] = "completed"
            task["artifacts"] = [{"artifactId": "opinion", "parts": [{"kind": "text", "text": "recovered third task"}]}]
            response._content = json.dumps({"jsonrpc": "2.0", "id": kwargs["json"]["id"], "result": task}).encode()
        return response

    monkeypatch.setattr(requests.Session, "post", post)
    worker._process(claim())
    worker._process(claim())
    with pytest.raises(SimulatedCrash):
        worker._process(claim())
    item = queue.read_run(run["run_id"])["results"][0]
    assert item["attempts"] == 3 and item["_a2a_task_id"] == "third-attempt-task"
    stack.clock.advance(stack.config.lease_seconds + 1)
    worker._process(claim())
    assert methods == ["message/stream", "message/stream", "message/stream", "tasks/get"]
    final = queue.read_run(run["run_id"])
    assert final["counts"]["succeeded"] == 1 and final["results"][0]["attempts"] == 3


@pytest.mark.parametrize("boundary", ["user_read", "initial_read", "final_read", "cas_retry"])
def test_reconciliation_reads_and_cas_retries_cannot_extend_original_alert_deadline(stack, monkeypatch, boundary):
    record = hit(dossier=[lead(), lead("human note", "human")])
    stack.seed(record)
    run = stack.enqueue()
    first = claim()
    candidate = service.prepare_candidate("immutable pending opinion", run["run_id"], "0")
    assert queue.store_candidate(first["run_id"], first["index"], first["nonce"], candidate)
    assert queue.set_commit_phase(first["run_id"], first["index"], first["nonce"], "write_pending")
    stack.clock.advance(first["deadline_at"] - stack.clock() - 1)
    recovery, _ = queue.claim_reconciliation()
    assert recovery is not None and recovery["deadline_at"] == first["deadline_at"]
    assert queue.reconciliation_is_current(recovery["run_id"], recovery["index"], recovery["nonce"])

    original_user = service.get_current_user
    original_get = service.get_current_hit
    original_save = stack.hits.save
    reads = []
    writes = []

    def delayed_user(*args):
        result = original_user(*args)
        if boundary == "user_read" and stack.clock() < first["deadline_at"]:
            stack.clock.advance(2)
        return result

    def delayed_hit(*args):
        result = original_get(*args)
        reads.append(stack.clock())
        # Reconciliation's confirmation read, then the two fresh pre-CAS reads.
        if len(reads) == {"initial_read": 1, "final_read": 3}.get(boundary):
            stack.clock.advance(2)
        return result

    def conflicting_write(key, updated, **kwargs):
        writes.append(stack.clock())
        assert stack.clock() < first["deadline_at"], "Reconciliation initiated a new ES write after the alert deadline"
        assert boundary == "cas_retry", "A blocking read exhausted the budget before any write was allowed"
        human, version = stack.hits.get(key, version=True)
        human.howler.assignment = "concurrent-human"
        original_save(key, human, version=version)
        stack.clock.advance(2)
        return original_save(key, updated, **kwargs)  # Actual Elasticsearch version conflict.

    monkeypatch.setattr(service, "get_current_user", delayed_user)
    monkeypatch.setattr(service, "get_current_hit", delayed_hit)
    monkeypatch.setattr(stack.hits, "save", conflicting_write)
    generate = Mock(side_effect=AssertionError("Reconciliation must never run another inference"))
    monkeypatch.setattr(ai_transport, "generate", generate)
    worker._process_reconciliation(recovery, allow_write=True)
    assert len(writes) == (1 if boundary == "cas_retry" else 0)
    pending = queue.read_run(run["run_id"])
    assert pending["state"] == "running"
    item = pending["results"][0]
    assert item["reason"] == "write_reconciliation_pending" and item["_write_intent"]
    assert item["_deadline_at"] == first["deadline_at"] and item["_candidate"] == candidate
    stack.clock.advance(stack.config.lease_seconds + 1)
    reconcile()
    assert len(writes) == (1 if boundary == "cas_retry" else 0), "After expiry only confirmation reads are allowed"
    assert [entry["content"] for entry in current_leads(stack, record)] == ["old opinion", "human note"]
    if boundary == "cas_retry":
        assert stack.hits.get(record.howler.id).howler.assignment == "concurrent-human"
    generate.assert_not_called()


@pytest.mark.parametrize("change", [{"status": "resolved"}, {"assessment": "legitimate"}])
@pytest.mark.parametrize("timing", ["before_reconcile", "during_commit_read", "after_deadline"])
@pytest.mark.parametrize("opinion_variant", ["stale_digest", "valid_different"])
def test_uncertain_submitted_write_and_changed_eligibility_remain_pending_until_truthful_unknown(
    stack, monkeypatch, change, timing, opinion_variant
):
    record = hit(dossier=[lead()])
    stack.seed(record)
    run = stack.enqueue()
    original_save = stack.hits.save
    original_get = service.get_current_hit
    writes = []
    block_reads = False
    reconcile_reads = 0

    def unacknowledged_write(key, updated, **kwargs):
        nonlocal block_reads
        writes.append(deepcopy(updated.as_primitives()))
        block_reads = True
        # An outstanding submitted request has no known success/failure response.
        raise ConnectionError("connection lost after request submission")

    def change_eligibility():
        current, version = stack.hits.get(record.howler.id, version=True)
        for field, value in change.items():
            setattr(current.howler, field, value)
        # Correct owner, run and content are insufficient evidence of this exact
        # candidate. Include both stale-digest tampering and valid new provenance.
        changed = candidate_with_changed_provenance(candidate, generated_at="2040-01-01T00:00:00Z")
        assert service.candidate_is_valid(changed)
        if opinion_variant == "stale_digest":
            metadata = json.loads(changed["metadata"])
            metadata["candidate_sha256"] = candidate["digest"]
            changed["metadata"] = json.dumps(metadata)
        current.howler.dossier = [{key: changed[key] for key in ("content", "label", "format", "metadata")}]
        original_save(record.howler.id, current, version=version)

    def read_at_boundary(*args):
        nonlocal reconcile_reads
        if block_reads:
            raise ConnectionError("immediate confirmation unavailable")
        if writes:
            reconcile_reads += 1
            if timing == "during_commit_read" and reconcile_reads == 2:
                change_eligibility()
        return original_get(*args)

    generate = Mock(return_value="uncertain opinion")
    monkeypatch.setattr(ai_transport, "generate", generate)
    monkeypatch.setattr(stack.hits, "save", unacknowledged_write)
    monkeypatch.setattr(service, "get_current_hit", read_at_boundary)
    worker._process(claim())
    pending = queue.read_run(run["run_id"])
    item = pending["results"][0]
    assert item["reason"] == "write_reconciliation_pending" and item["_write_intent"]
    candidate = deepcopy(item["_candidate"])
    deadline = item["_deadline_at"]
    block_reads = False
    if timing != "during_commit_read":
        change_eligibility()
    stack.clock.advance(601 if timing == "after_deadline" else 10)
    reconcile()
    pending = queue.read_run(run["run_id"])
    item = pending["results"][0]
    assert pending["state"] == "running" and pending["counts"]["skipped"] == 0
    assert item["reason"] == "write_reconciliation_pending"
    assert item["_write_intent"] and item["_candidate"] == candidate and item["_deadline_at"] == deadline
    assert len(writes) == generate.call_count == 1
    stack.clock.advance(item["_reconcile_horizon_at"] - stack.clock() + 1)
    assert queue.claim_reconciliation()[0] is None
    final = queue.read_run(run["run_id"])
    assert final["state"] == "completed" and final["counts"]["failed"] == 1
    assert final["counts"]["skipped"] == 0 and final["results"][0]["reason"] == "write_outcome_unknown"
    assert "could not be confirmed" in final["results"][0]["message"]
    assert "may have been replaced" in final["results"][0]["message"]
    assert "_encrypted_bearer_token" not in final
    actual = stack.hits.get(record.howler.id)
    assert not service.has_managed_candidate(actual, candidate)
    assert actual.howler.dossier[0].content == "uncertain opinion", "Reconciliation must never roll back analyst data"


@pytest.mark.parametrize("change", [{"status": "resolved"}, {"assessment": "legitimate"}])
def test_exact_candidate_confirmation_succeeds_after_eligibility_change_and_deadline(stack, monkeypatch, change):
    record = hit(dossier=[lead()])
    stack.seed(record)
    run = stack.enqueue()
    job = claim()
    candidate = service.prepare_candidate("saved candidate", run["run_id"], "0")
    assert queue.store_candidate(job["run_id"], job["index"], job["nonce"], candidate)
    assert queue.set_commit_phase(job["run_id"], job["index"], job["nonce"], "write_pending")
    assert service.save_ai_lead(record.howler.id, stack.owner, candidate) == (True, None)
    current, version = stack.hits.get(record.howler.id, version=True)
    for field, value in change.items():
        setattr(current.howler, field, value)
    stack.hits.save(record.howler.id, current, version=version)
    save = Mock(side_effect=AssertionError("Postdeadline reconciliation must be confirmation-only"))
    monkeypatch.setattr(stack.hits, "save", save)
    stack.clock.advance(601)
    reconcile()
    final = queue.read_run(run["run_id"])
    assert final["counts"]["succeeded"] == 1 and final["counts"]["skipped"] == 0
    assert "_encrypted_bearer_token" not in final
    save.assert_not_called()
