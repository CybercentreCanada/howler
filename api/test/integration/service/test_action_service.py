import json
import logging
import time

from howler.common import loader
from howler.datastore.howler_store import HowlerDatastore
from howler.helper.hit import HitStatusTransition, Status
from howler.odm.helper import generate_useful_hit
from howler.odm.models.action import VALID_TRIGGERS, Action
from howler.odm.models.howler_data import Assessment
from howler.odm.random_data import create_users, wipe_users
from howler.services import action_service, hit_service


def _drain_action_queues():
    """Pop all pending items from every per-trigger action queue."""
    for trigger in VALID_TRIGGERS:
        queue = action_service.get_action_queue(trigger)
        while queue.pop(blocking=False) is not None:
            pass


def _wait_for_hit_label(ds: HowlerDatastore, hit_id: str, label: str, timeout: float = 15) -> bool:
    """Poll until the expected label appears on a hit or timeout elapses."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        ds.hit.commit()
        hit = ds.hit.get(hit_id)
        if hit and label in (hit.howler.labels.generic or []):
            return True
        time.sleep(0.5)
    return False


def test_execute_action(datastore_connection: HowlerDatastore):
    lookups = loader.get_lookups()
    wipe_users(datastore_connection)
    create_users(datastore_connection)
    users = datastore_connection.user.search("*:*")["items"]

    test_hit_promote = generate_useful_hit(lookups, users, False)
    test_hit_promote.howler.assessment = None
    test_hit_promote.howler.escalation = "alert"
    test_hit_promote.howler.status = Status.OPEN
    test_hit_promote.howler.analytic = "test_triage_assess_promote"
    datastore_connection.hit.save(test_hit_promote.howler.id, test_hit_promote)

    test_hit_demote = generate_useful_hit(lookups, users, False)
    test_hit_promote.howler.assessment = None
    test_hit_promote.howler.status = Status.OPEN
    test_hit_promote.howler.escalation = "alert"
    test_hit_demote.howler.analytic = "test_triage_assess_demote"
    datastore_connection.hit.save(test_hit_demote.howler.id, test_hit_demote)

    datastore_connection.action.wipe()

    # Create actions
    action_demote = Action(
        {
            "triggers": ["demote"],
            "name": "Test demote on triage",
            "owner": "admin",
            "query": "howler.id:*",
            "operations": [
                {
                    "operation_id": "add_label",
                    "data_json": json.dumps({"category": "generic", "label": "demoted"}),
                }
            ],
        }
    )

    datastore_connection.action.save(action_demote.action_id, action_demote)

    # Create actions
    action_promote = Action(
        {
            "triggers": ["promote"],
            "name": "Test promote on triage",
            "owner": "admin",
            "query": "howler.id:*",
            "operations": [
                {
                    "operation_id": "add_label",
                    "data_json": json.dumps({"category": "generic", "label": "promoted"}),
                }
            ],
        }
    )

    datastore_connection.action.save(action_promote.action_id, action_promote)

    datastore_connection.action.commit()

    assert datastore_connection.action.exists(action_demote.action_id)
    assert datastore_connection.action.exists(action_promote.action_id)

    assert datastore_connection.action.search("action_id:*")["total"] == 2

    user = next(user for user in users if "automation_basic" in user["type"])

    # Clear any stale items from all trigger queues
    _drain_action_queues()

    hit_service.transition_hit(
        test_hit_demote.howler.id, HitStatusTransition.ASSESS, user=user, assessment=Assessment.FALSE_POSITIVE
    )

    hit_service.transition_hit(
        test_hit_promote.howler.id, HitStatusTransition.ASSESS, user=user, assessment=Assessment.COMPROMISE
    )

    # Wait for the background worker to process the queued actions
    assert _wait_for_hit_label(datastore_connection, test_hit_demote.howler.id, "demoted"), (
        "Label 'demoted' was not applied by the action queue worker within the timeout"
    )

    assert _wait_for_hit_label(datastore_connection, test_hit_promote.howler.id, "promoted"), (
        "Label 'promoted' was not applied by the action queue worker within the timeout"
    )

    datastore_connection.hit.delete(test_hit_demote.howler.id)
    datastore_connection.action.delete(action_demote.action_id)

    datastore_connection.hit.delete(test_hit_promote.howler.id)
    datastore_connection.action.delete(action_promote.action_id)


def test_execute_action_no_results(datastore_connection: HowlerDatastore):
    lookups = loader.get_lookups()
    users = datastore_connection.user.search("*:*")["items"]

    test_hit = generate_useful_hit(lookups, users, False)
    test_hit.howler.analytic = "test_triage_assess_promote"
    datastore_connection.hit.save(test_hit.howler.id, test_hit)

    datastore_connection.action.wipe()

    # Create action
    test_action = Action(
        {
            "triggers": ["promote"],
            "name": "Test promote on triage",
            "owner": "admin",
            "query": "howler.id:jiksdfrhhbjnksdcfhbjnk",
            "operations": [
                {
                    "operation_id": "add_label",
                    "data_json": json.dumps({"category": "generic", "label": "promoted"}),
                }
            ],
        }
    )

    datastore_connection.action.save(test_action.action_id, test_action)
    datastore_connection.action.commit()
    assert datastore_connection.action.exists(test_action.action_id)

    # Clear stale items and enqueue via transition
    _drain_action_queues()

    hit_service.transition_hit(
        test_hit.howler.id, HitStatusTransition.ASSESS, user=users[0], assessment=Assessment.FALSE_POSITIVE
    )

    # Wait long enough for the worker to process
    time.sleep(3)

    # The non-matching action should not have added a label
    datastore_connection.hit.commit()
    updated_hit = datastore_connection.hit.get(test_hit.howler.id)
    assert "promoted" not in (updated_hit.howler.labels.generic or [])

    datastore_connection.hit.delete(test_hit.howler.id)
    datastore_connection.action.delete(test_action.action_id)


def test_process_action_batch_create_trigger(datastore_connection: HowlerDatastore, caplog):
    """process_action_batch should execute matching actions on a batch of hits."""
    lookups = loader.get_lookups()
    wipe_users(datastore_connection)
    create_users(datastore_connection)
    users = datastore_connection.user.search("*:*")["items"]
    user = next(u for u in users if "automation_basic" in u["type"])

    test_hit = generate_useful_hit(lookups, users, False)
    test_hit.howler.assessment = None
    test_hit.howler.escalation = "alert"
    test_hit.howler.status = Status.OPEN
    test_hit.howler.analytic = "test_batch_create"
    datastore_connection.hit.save(test_hit.howler.id, test_hit)

    datastore_connection.action.wipe()

    action = Action(
        {
            "triggers": ["create"],
            "name": "Test batch create action",
            "owner": "admin",
            "query": "howler.id:*",
            "operations": [
                {
                    "operation_id": "add_label",
                    "data_json": json.dumps({"category": "generic", "label": "batch_created"}),
                }
            ],
        }
    )
    datastore_connection.action.save(action.action_id, action)
    datastore_connection.action.commit()
    datastore_connection.hit.commit()

    batch = [
        {"hit_ids": [test_hit.howler.id], "uname": user["uname"]},
    ]

    with caplog.at_level(logging.INFO):
        action_service.process_action_batch("create", batch)

    assert f"Running action {action.action_id} on bulk query" in caplog.text

    datastore_connection.hit.commit()
    updated_hit = datastore_connection.hit.get(test_hit.howler.id)
    assert "batch_created" in updated_hit.howler.labels.generic

    datastore_connection.hit.delete(test_hit.howler.id)
    datastore_connection.action.delete(action.action_id)


def test_process_action_batch_no_matching_action(datastore_connection: HowlerDatastore, caplog):
    """Batch with no matching actions should produce no errors."""
    lookups = loader.get_lookups()
    wipe_users(datastore_connection)
    create_users(datastore_connection)
    users = datastore_connection.user.search("*:*")["items"]
    user = next(u for u in users if "automation_basic" in u["type"])

    test_hit = generate_useful_hit(lookups, users, False)
    test_hit.howler.analytic = "test_batch_no_match"
    datastore_connection.hit.save(test_hit.howler.id, test_hit)

    datastore_connection.action.wipe()

    action = Action(
        {
            "triggers": ["promote"],
            "name": "Test batch no match",
            "owner": "admin",
            "query": "howler.id:nonexistent_id_12345",
            "operations": [
                {
                    "operation_id": "add_label",
                    "data_json": json.dumps({"category": "generic", "label": "should_not_appear"}),
                }
            ],
        }
    )
    datastore_connection.action.save(action.action_id, action)
    datastore_connection.action.commit()
    datastore_connection.hit.commit()

    batch = [
        {"hit_ids": [test_hit.howler.id], "uname": user["uname"]},
    ]

    with caplog.at_level(logging.DEBUG):
        action_service.process_action_batch("create", batch)

    # promote trigger action should not fire on a create trigger batch
    assert f"Running action {action.action_id}" not in caplog.text

    datastore_connection.hit.commit()
    updated_hit = datastore_connection.hit.get(test_hit.howler.id)
    assert "should_not_appear" not in (updated_hit.howler.labels.generic or [])

    datastore_connection.hit.delete(test_hit.howler.id)
    datastore_connection.action.delete(action.action_id)


def test_process_action_batch_coalesces_duplicates(datastore_connection: HowlerDatastore, caplog):
    """Two queue items for same trigger/user should be coalesced into one bulk call."""
    lookups = loader.get_lookups()
    wipe_users(datastore_connection)
    create_users(datastore_connection)
    users = datastore_connection.user.search("*:*")["items"]
    user = next(u for u in users if "automation_basic" in u["type"])

    hit1 = generate_useful_hit(lookups, users, False)
    hit1.howler.assessment = None
    hit1.howler.escalation = "alert"
    hit1.howler.status = Status.OPEN
    hit1.howler.analytic = "test_coalesce_1"
    datastore_connection.hit.save(hit1.howler.id, hit1)

    hit2 = generate_useful_hit(lookups, users, False)
    hit2.howler.assessment = None
    hit2.howler.escalation = "alert"
    hit2.howler.status = Status.OPEN
    hit2.howler.analytic = "test_coalesce_2"
    datastore_connection.hit.save(hit2.howler.id, hit2)

    datastore_connection.action.wipe()

    action = Action(
        {
            "triggers": ["create"],
            "name": "Test coalesce action",
            "owner": "admin",
            "query": "howler.id:*",
            "operations": [
                {
                    "operation_id": "add_label",
                    "data_json": json.dumps({"category": "generic", "label": "coalesced"}),
                }
            ],
        }
    )
    datastore_connection.action.save(action.action_id, action)
    datastore_connection.action.commit()
    datastore_connection.hit.commit()

    # Simulate two separate queue items that get coalesced into one batch
    batch = [
        {"hit_ids": [hit1.howler.id], "uname": user["uname"]},
        {"hit_ids": [hit2.howler.id], "uname": user["uname"]},
    ]

    with caplog.at_level(logging.INFO):
        action_service.process_action_batch("create", batch)

    # Only one "Running action" log line should appear (coalesced)
    running_lines = [r for r in caplog.records if "Running action" in r.message]
    assert len(running_lines) == 1

    datastore_connection.hit.commit()
    assert "coalesced" in datastore_connection.hit.get(hit1.howler.id).howler.labels.generic
    assert "coalesced" in datastore_connection.hit.get(hit2.howler.id).howler.labels.generic

    datastore_connection.hit.delete(hit1.howler.id)
    datastore_connection.hit.delete(hit2.howler.id)
    datastore_connection.action.delete(action.action_id)
