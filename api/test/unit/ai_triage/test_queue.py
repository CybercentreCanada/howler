"""Focused Redis-queue index behavior without external services."""

import json
from unittest.mock import Mock

from howler.services import ai_triage_queue as queue


def test_owner_page_prunes_stale_runs_and_adjusts_scan_offset(monkeypatch):
    owner = "queue-index-test"
    live = {"run_id": "live", "state": "running", "_created_at_epoch": 10}
    expired = {"run_id": "expired", "state": "completed", "_expires_at": 99}
    client = Mock()
    client.zrevrange.return_value = [b"missing", b"live", b"expired"]
    client.get.side_effect = [None, json.dumps(live), json.dumps(expired)]
    locked = Mock(side_effect=AssertionError("list_runs must not acquire the global lock"))
    fenced_pipeline = Mock(side_effect=AssertionError("list_runs must not create a fenced pipeline"))

    monkeypatch.setattr(queue, "redis_client", lambda: client)
    monkeypatch.setattr(queue, "_locked", locked)
    monkeypatch.setattr(queue, "_fenced_pipeline", fenced_pipeline)
    monkeypatch.setattr(queue, "_now", lambda: 100)
    runs, progress = queue.list_runs(owner, offset=4, rows=3)

    assert runs == [live]
    assert progress == queue.OwnerRunScan(fetched_count=3, next_offset=5, exhausted=False)
    client.zrem.assert_any_call(queue._owner_key(owner), "missing", "expired")
    client.zrem.assert_any_call(queue._active_key(), "missing", "expired")
    locked.assert_not_called()
    fenced_pipeline.assert_not_called()


def test_queue_lock_uses_nonce_set_and_compare_delete():
    client = Mock()
    client.set.return_value = True

    with queue._locked(client, "queue-lock"):
        token = client.set.call_args.args[1]
        assert queue._LOCK_FENCES.get()[-1].token == token

    client.set.assert_called_once_with("queue-lock", token, nx=True, ex=queue.QUEUE_LOCK_TTL)
    client.eval.assert_called_once_with(queue._LOCK_RELEASE_SCRIPT, 1, "queue-lock", token)
