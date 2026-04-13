import json
import logging

from howler.common import loader
from howler.datastore.howler_store import HowlerDatastore
from howler.helper.hit import HitStatus, HitStatusTransition
from howler.odm.helper import generate_useful_hit
from howler.odm.models.action import Action
from howler.odm.models.howler_data import Assessment
from howler.odm.random_data import create_users, wipe_users
from howler.services import hit_service


def test_execute_action(datastore_connection: HowlerDatastore, caplog):
    lookups = loader.get_lookups()
    wipe_users(datastore_connection)
    create_users(datastore_connection)
    users = datastore_connection.user.search("*:*")["items"]

    test_hit_promote = generate_useful_hit(lookups, users, False)
    test_hit_promote.howler.assessment = None
    test_hit_promote.howler.escalation = "alert"
    test_hit_promote.howler.status = HitStatus.OPEN
    test_hit_promote.howler.analytic = "test_triage_assess_promote"
    datastore_connection.hit.save(test_hit_promote.howler.id, test_hit_promote)

    test_hit_demote = generate_useful_hit(lookups, users, False)
    test_hit_promote.howler.assessment = None
    test_hit_promote.howler.status = HitStatus.OPEN
    test_hit_promote.howler.escalation = "alert"
    test_hit_demote.howler.analytic = "test_triage_assess_demote"
    datastore_connection.hit.save(test_hit_demote.howler.id, test_hit_demote)

    datastore_connection.action.wipe()

    # Create actions
    action_demote = Action(
        {
            "triggers": ["demote"],
            "name": "Test demote on triage",
            "owner_id": "admin",
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
            "owner_id": "admin",
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

    with caplog.at_level(logging.INFO):
        hit_service.transition_hit(
            test_hit_demote.howler.id, HitStatusTransition.ASSESS, user=user, assessment=Assessment.FALSE_POSITIVE
        )

    assert f"Running action {action_demote.action_id} on bulk query"

    caplog.clear()

    with caplog.at_level(logging.INFO):
        hit_service.transition_hit(
            test_hit_promote.howler.id, HitStatusTransition.ASSESS, user=user, assessment=Assessment.COMPROMISE
        )

    assert f"Running action {action_promote.action_id} on bulk query"

    caplog.clear()

    datastore_connection.hit.commit()

    assert "demoted" in datastore_connection.hit.get(test_hit_demote.howler.id).howler.labels.generic
    assert "promoted" in datastore_connection.hit.get(test_hit_promote.howler.id).howler.labels.generic

    datastore_connection.hit.delete(test_hit_demote.howler.id)
    datastore_connection.action.delete(action_demote.action_id)

    datastore_connection.hit.delete(test_hit_promote.howler.id)
    datastore_connection.action.delete(action_promote.action_id)


def test_execute_action_no_results(datastore_connection: HowlerDatastore, caplog):
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
            "owner_id": "admin",
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

    with caplog.at_level(logging.DEBUG):
        hit_service.transition_hit(
            test_hit.howler.id, HitStatusTransition.ASSESS, user=users[0], assessment=Assessment.FALSE_POSITIVE
        )

    assert f"Running action {test_action.action_id}" not in caplog.text
    assert f"Action {test_action.action_id} does not apply" not in caplog.text

    datastore_connection.hit.delete(test_hit.howler.id)
    datastore_connection.action.delete(test_action.action_id)
