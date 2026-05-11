import base64
import json
import re
import time
import warnings
from typing import Any
from uuid import uuid4

import pytest
import requests

from howler.common import loader
from howler.config import CLASSIFICATION
from howler.datastore.howler_store import HowlerDatastore
from howler.odm.helper import generate_useful_hit
from howler.odm.models.action import Action
from howler.odm.models.howler_data import Assessment, HitStatusTransition
from howler.odm.random_data import create_actions, create_hits, wipe_actions, wipe_hits
from howler.services import hit_service
from test.conftest import APIError, get_api_data


@pytest.fixture(scope="module")
def datastore(datastore_connection):
    ds = datastore_connection

    try:
        wipe_hits(ds)
        wipe_actions(ds)
        create_hits(ds, hit_count=10)
        create_actions(ds)

        ds.hit.commit()
        ds.action.commit()

        time.sleep(1)

        yield ds
    finally:
        wipe_hits(ds)
        wipe_actions(ds)


# noinspection PyUnusedLocal
def test_get_operations(datastore: HowlerDatastore, login_session):
    session, host = login_session

    resp = get_api_data(
        session,
        f"{host}/api/v1/action/operations",
    )

    for operation in resp:
        assert operation["id"]
        assert operation["title"]

        if not operation.get("i18nKey", None):
            warnings.warn(f"{operation['id']} is missing an i18nKey! Suggested: 'action.{operation['id']}'")

        assert "description" in operation

        if not operation["description"].get("short", None):
            warnings.warn(f"{operation['id']} is missing a short description!")

        if not operation["description"].get("long", None):
            warnings.warn(f"{operation['id']} is missing a long description!")

        assert "steps" in operation

        for step in operation["steps"]:
            assert "args" in step
            assert len(list(step["args"].keys())) > 0

            for conditions in step["args"].values():
                assert isinstance(conditions, list)

                if len(conditions) > 0:
                    assert all(isinstance(c, str) for c in conditions)

            assert "options" in step

            for options in step["options"].values():
                assert isinstance(options, dict) or isinstance(options, list)


def test_execute_bogus_action(datastore: HowlerDatastore, login_session):
    session, host = login_session

    req = {
        "request_id": str(uuid4()),
        "query": "howler.id:*",
        "operations": [
            {
                "operation_id": "bogus_action_that_doesntexist",
                "data_json": "{}",
            },
        ],
    }

    resp = get_api_data(
        session,
        f"{host}/api/v1/action/execute",
        method="POST",
        data=json.dumps(req),
    )

    for report in resp.values():
        assert len(report) == 1
        report = report[0]

        assert "query" in report
        assert report["query"] == "howler.id:*"

        assert "outcome" in report
        assert report["outcome"] == "error"

        assert "message" in report
        assert "bogus_action_that_doesntexist" in report["message"]


def test_execute_action_labels(datastore: HowlerDatastore, login_session):
    session, host = login_session

    req = {
        "request_id": str(uuid4()),
        "query": "howler.id:*",
        "operations": [
            {
                "operation_id": "add_label",
                "data_json": json.dumps({"category": "generic", "label": "potato"}),
            },
            {
                "operation_id": "remove_label",
                "data_json": json.dumps({"category": "generic", "label": "potato"}),
            },
        ],
    }

    resp = get_api_data(
        session,
        f"{host}/api/v1/action/execute",
        method="POST",
        data=json.dumps(req),
    )

    for report in resp.values():
        report = report[0]

        assert "query" in report
        assert report["query"] == "(howler.id:*)" or report["outcome"] == "skipped"

        assert "outcome" in report
        assert report["outcome"] in ["success", "skipped"]


def test_execute_action_labels_fail(datastore: HowlerDatastore, login_session):
    session, host = login_session

    req = {
        "request_id": str(uuid4()),
        "query": "howler.id:*",
        "operations": [
            {
                "operation_id": "add_label",
                "data_json": json.dumps({"category": "doesnexistandneverwill", "label": "potato"}),
            },
            {
                "operation_id": "remove_label",
                "data_json": json.dumps({"category": "doesnexistandneverwill", "label": "potato"}),
            },
        ],
    }

    resp = get_api_data(
        session,
        f"{host}/api/v1/action/execute",
        method="POST",
        data=json.dumps(req),
    )

    for report in resp.values():
        assert len(report) == 1
        report = report[0]

        assert "query" in report
        assert report["query"] == "(howler.id:*)"

        assert "outcome" in report
        assert report["outcome"] == "error"

        assert "message" in report
        assert "'doesnexistandneverwill'" in report["message"]


def test_execute_transition_basic(datastore: HowlerDatastore, login_session):
    session, host = login_session

    req = {
        "request_id": str(uuid4()),
        "query": "howler.status:open",
        "operations": [
            {
                "operation_id": "transition",
                "data_json": json.dumps(
                    {
                        "status": "open",
                        "transition": "assign_to_other",
                        "assignee": "user",
                    }
                ),
            }
        ],
    }

    resp = get_api_data(
        session,
        f"{host}/api/v1/action/execute",
        method="POST",
        data=json.dumps(req),
    )

    for report in resp.values():
        assert len(report) == 1
        report = report[0]

        assert "query" in report
        assert report["query"].startswith("(howler.id:(")

        assert "outcome" in report
        assert report["outcome"] == "success"

        assert "message" in report
        assert report["message"].startswith("The transition assign_to_other successfully executed on ")
        assert report["message"].endswith(" hits.")

        total = int(re.sub(r"^.+?(\d+).+$", r"\1", report["message"]))

        # Wait for updates to be applied across the server
        time.sleep(5)

        assert datastore.hit.search("howler.assignment:user")["total"] >= total


def test_valid_action_on_triage(datastore: HowlerDatastore, login_session):
    session, host = login_session

    lookups = loader.get_lookups()
    users = [user.uname for user in datastore.user.search("*:*")["items"]]

    test_hit_promote = generate_useful_hit(lookups, users, False)
    test_hit_promote.classification = CLASSIFICATION.UNRESTRICTED
    test_hit_promote.howler.analytic = "test_triage_assess_promote"
    datastore.hit.save(test_hit_promote.howler.id, test_hit_promote)

    test_hit_demote = generate_useful_hit(lookups, users, False)
    test_hit_demote.classification = CLASSIFICATION.UNRESTRICTED
    test_hit_demote.howler.analytic = "test_triage_assess_demote"
    datastore.hit.save(test_hit_demote.howler.id, test_hit_demote)

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

    datastore.action.save(action_demote.action_id, action_demote)
    datastore.action.commit()
    assert datastore.action.exists(action_demote.action_id)

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

    datastore.action.save(action_promote.action_id, action_promote)
    datastore.action.commit()
    assert datastore.action.exists(action_promote.action_id)

    get_api_data(
        session=session,
        url=f"{host}/api/v1/hit/{test_hit_demote.howler.id}/transition/",
        method="POST",
        data=json.dumps(
            {
                "transition": HitStatusTransition.ASSESS,
                "data": {"assessment": Assessment.FALSE_POSITIVE},
            }
        ),
        headers={
            "content-type": "application/json",
        },
    )

    assert "demoted" in datastore.hit.get(test_hit_demote.howler.id).howler.labels.generic

    get_api_data(
        session=session,
        url=f"{host}/api/v1/hit/{test_hit_promote.howler.id}/transition/",
        method="POST",
        data=json.dumps(
            {
                "transition": HitStatusTransition.ASSESS,
                "data": {"assessment": Assessment.COMPROMISE},
            }
        ),
        headers={
            "content-type": "application/json",
        },
    )

    assert "promoted" in datastore.hit.get(test_hit_promote.howler.id).howler.labels.generic


@pytest.mark.skip(reason="Unstable Test")
def test_execute_transition_skipped(datastore: HowlerDatastore, login_session):
    session, host = login_session

    if datastore.hit.search("-howler.status:open")["total"] < 1:
        hit = datastore.hit.search("howler.status:open AND -howler.assignment:goose", rows=1)["items"][0]

        hit_service.transition_hit(
            hit["howler"]["id"],
            HitStatusTransition.ASSESS,
            datastore.user.search("*:*", rows=1)["items"][0],
            assessment=Assessment.ATTEMPT,
        )

    req = {
        "request_id": str(uuid4()),
        "query": "-howler.assignment:goose",
        "operations": [
            {
                "operation_id": "transition",
                "data_json": json.dumps(
                    {
                        "status": "open",
                        "transition": "assign_to_other",
                        "assignee": "goose",
                    }
                ),
            }
        ],
    }

    resp = get_api_data(
        session,
        f"{host}/api/v1/action/execute",
        method="POST",
        data=json.dumps(req),
    )

    for report in resp.values():
        assert len(report) == 2

        # First report
        assert "query" in report[0]
        assert (report[0]["query"].startswith("((") and report[0]["query"].endswith(") AND -howler.status:open)")) or (
            report[0]["query"].startswith("(howler.id") and report[0]["query"].endswith(")")
        )

        assert "outcome" in report[0]
        assert report[0]["outcome"] == "skipped"

        assert "message" in report[0]

        # Second report
        assert "query" in report[1]
        assert report[1]["query"].startswith("(howler.id:(")

        assert "outcome" in report[1]
        assert report[1]["outcome"] == "success"

        assert "message" in report[1]


def test_execute_transition_multiple(datastore: HowlerDatastore, login_session):
    session, host = login_session

    reqs = [
        {
            "request_id": str(uuid4()),
            "query": "howler.id:*",
            "operations": [
                {
                    "operation_id": "transition",
                    "data_json": json.dumps(
                        {
                            "status": "open",
                            "transition": "assign_to_me",
                            "assignee": "admin",
                        }
                    ),
                }
            ],
        },
        {
            "request_id": str(uuid4()),
            "query": "howler.id:*",
            "operations": [
                {
                    "operation_id": "transition",
                    "data_json": json.dumps(
                        {
                            "status": "in-progress",
                            "transition": "assign_to_me",
                            "assignee": "admin",
                        }
                    ),
                }
            ],
        },
        {
            "request_id": str(uuid4()),
            "query": "howler.id:*",
            "operations": [
                {
                    "operation_id": "transition",
                    "data_json": json.dumps({"status": "in-progress", "transition": "release"}),
                }
            ],
        },
        {
            "request_id": str(uuid4()),
            "query": "howler.id:*",
            "operations": [
                {
                    "operation_id": "transition",
                    "data_json": json.dumps(
                        {
                            "status": "open",
                            "transition": "assess",
                            "assignee": "admin",
                            "assessment": "legitimate",
                        }
                    ),
                }
            ],
        },
        {
            "request_id": str(uuid4()),
            "query": "howler.id:*",
            "operations": [
                {
                    "operation_id": "transition",
                    "data_json": json.dumps(
                        {
                            "status": "on-hold",
                            "transition": "assess",
                            "assignee": "admin",
                            "assessment": "legitimate",
                        }
                    ),
                }
            ],
        },
        {
            "request_id": str(uuid4()),
            "query": "howler.id:*",
            "operations": [
                {
                    "operation_id": "transition",
                    "data_json": json.dumps(
                        {
                            "status": "in-progress",
                            "transition": "assess",
                            "assignee": "admin",
                            "assessment": "legitimate",
                        }
                    ),
                }
            ],
        },
        {
            "request_id": str(uuid4()),
            "query": "howler.id:*",
            "operations": [
                {
                    "operation_id": "transition",
                    "data_json": json.dumps({"status": "resolved", "transition": "re_evaluate"}),
                }
            ],
        },
        {
            "request_id": str(uuid4()),
            "query": "howler.id:*",
            "operations": [
                {
                    "operation_id": "transition",
                    "data_json": json.dumps(
                        {
                            "status": "in-progress",
                            "transition": "promote",
                        }
                    ),
                }
            ],
        },
        {
            "request_id": str(uuid4()),
            "query": "howler.id:*",
            "operations": [
                {
                    "operation_id": "transition",
                    "data_json": json.dumps({"status": "in-progress", "transition": "release"}),
                }
            ],
        },
    ]

    for req in reqs:
        resp = get_api_data(
            session,
            f"{host}/api/v1/action/execute",
            method="POST",
            data=json.dumps(req),
        )

        for report in resp.values():
            for entry in report:
                assert entry["outcome"] in ["skipped", "success"]

                assert "query" in entry
                assert "title" in entry
                assert "message" in entry

    assert datastore.hit.search("howler.status:open")["total"] == datastore.hit.search("howler.id:*")["total"]

    assert datastore.hit.search("howler.escalation:alert")["total"] == datastore.hit.search("howler.id:*")["total"]


def test_create_action_fails(datastore: HowlerDatastore, login_session):
    session, host = login_session

    req: dict[str, Any] = {}

    with pytest.raises(APIError) as err:
        get_api_data(
            session,
            f"{host}/api/v1/action",
            method="POST",
            data=json.dumps(req),
        )

    assert err.value.args[0] == "400: You must specify a name."

    req["name"] = ""

    with pytest.raises(APIError) as err:
        get_api_data(
            session,
            f"{host}/api/v1/action",
            method="POST",
            data=json.dumps(req),
        )

    assert err.value.args[0] == "400: Name cannot be empty."

    req["name"] = "Test Create action"

    with pytest.raises(APIError) as err:
        get_api_data(
            session,
            f"{host}/api/v1/action",
            method="POST",
            data=json.dumps(req),
        )

    assert err.value.args[0] == "400: You must specify a query."

    req["query"] = ""

    with pytest.raises(APIError) as err:
        get_api_data(
            session,
            f"{host}/api/v1/action",
            method="POST",
            data=json.dumps(req),
        )

    assert err.value.args[0] == "400: Query cannot be empty."

    req["query"] = "howler.id:*"

    with pytest.raises(APIError) as err:
        get_api_data(
            session,
            f"{host}/api/v1/action",
            method="POST",
            data=json.dumps(req),
        )

    assert err.value.args[0] == "400: You must specify a list of operations."

    req["operations"] = "banana"

    with pytest.raises(APIError) as err:
        get_api_data(
            session,
            f"{host}/api/v1/action",
            method="POST",
            data=json.dumps(req),
        )

    assert err.value.args[0] == "400: 'operations' must be a list of operations."

    req["operations"] = []

    with pytest.raises(APIError) as err:
        get_api_data(
            session,
            f"{host}/api/v1/action",
            method="POST",
            data=json.dumps(req),
        )

    assert err.value.args[0] == "400: You must specify at least one operation."


def test_create_action_success(datastore: HowlerDatastore, login_session):
    session, host = login_session

    req = {
        "name": "Test Create action",
        "owner_id": "admin",
        "query": "howler.id:*",
        "operations": [
            {
                "operation_id": "add_label",
                "data_json": json.dumps({"category": "generic", "label": "test"}),
            }
        ],
    }

    resp = get_api_data(
        session,
        f"{host}/api/v1/action",
        method="POST",
        data=json.dumps(req),
    )

    assert resp.get("action_id", None) is not None

    assert datastore.action.exists(resp["action_id"])


def test_update_action_success(datastore: HowlerDatastore, login_session):
    session, host = login_session

    action_id = datastore.action.search("*:*", rows=1)["items"][0]["action_id"]

    req = {
        "name": "Test Update action",
        "query": "howler.id:*",
        "owner_id": "admin",
        "operations": [
            {
                "operation_id": "add_label",
                "data_json": json.dumps({"category": "generic", "label": "test"}),
            }
        ],
    }

    resp = get_api_data(
        session,
        f"{host}/api/v1/action/{action_id}",
        method="PUT",
        data=json.dumps(req),
    )

    assert resp.get("name", None) is not None

    assert resp["name"] == "Test Update action"


def test_update_action_failed(datastore: HowlerDatastore, login_session):
    __, host = login_session

    session = requests.Session()
    session.headers.update({"Authorization": f"Basic {base64.b64encode(b'user:user').decode('utf-8')}"})

    action_id = datastore.action.search("*:*", rows=1)["items"][0]["action_id"]

    req = {"triggers": ["trigger no existy"]}

    with pytest.raises(APIError) as err:
        get_api_data(
            session,
            f"{host}/api/v1/action/{action_id}",
            method="PUT",
            data=json.dumps(req),
        )

    assert "Updating triggers" in str(err)


# region : Testing Permissions

# region : Permission helper


def add_permission_every_role(member_to_add: str, member_requesting, create_res, host, action):
    try:
        for membership in action.get_priviledge_mapping().keys():
            get_api_data(
                member_requesting,
                f"{host}/api/v1/action/{create_res['action_id']}/permission",
                method="PUT",
                data=json.dumps(
                    {
                        "user_id": member_to_add,
                        "priviledge": membership,
                    }
                ),
            )
    # Error is intended sometime.
    except APIError:
        return


def remove_permission_every_role(member_to_remove: str, member_requesting, create_res, host, action):
    try:
        for membership in action.get_priviledge_mapping().keys():
            get_api_data(
                member_requesting,
                f"{host}/api/v1/action/{create_res['action_id']}/permission",
                method="DELETE",
                data=json.dumps(
                    {
                        "user_id": member_to_remove,
                        "priviledge": membership,
                    }
                ),
            )
    # Error is intended sometime.
    except APIError:
        return


def modifying_action(member_requesting, create_res, host, action_name: str = "renamed_action"):
    # GET the action first to see if Huey can even see it
    # current_action = get_api_data(member_requesting, f"{host}/api/v1/action/{action_id}")
    # print(f"DEBUG: Huey can see action: {current_action['name']}")

    req = {
        "name": f"{action_name}",
        "query": "howler.id:*",
        "operations": [
            {
                "operation_id": "add_label",
                "data_json": json.dumps({"category": "generic", "label": "test"}),
            }
        ],
    }

    get_api_data(
        member_requesting,
        f"{host}/api/v1/action/{create_res['action_id']}",
        method="PUT",
        data=json.dumps(req),
    )


# endregion


def test_give_remove_membership(
    datastore: HowlerDatastore,
    user_sessions,
):
    """
    Test adding a user and removing a user from a action
    """
    owner_session, host = user_sessions["user"]
    member_session, _ = user_sessions["huey"]

    member_uname = get_api_data(member_session, f"{host}/api/v1/user/whoami", method="GET")["username"]
    # Create the action
    # TODO : AG : HERE !
    create_res = get_api_data(
        owner_session,
        f"{host}/api/v1/action/",
        method="POST",
        data=json.dumps(
            {
                "name": "My totally awsome and unique action",
                "query": "howler.id:*",
                "classification": "UNRESTRICTED",
                "operations": [
                    {
                        "operation_id": "add_label",
                        "data_json": "{'category': 'generic', 'label': 'assigned'}",
                    }
                ],
            }
        ),
    )
    action: Action = datastore.action.get(create_res["action_id"], as_obj=True)

    # Give|Remove every possible membership
    for request in ("PUT", "DELETE"):
        for membership in action.get_priviledge_mapping().keys():
            get_api_data(
                owner_session,
                f"{host}/api/v1/action/{create_res['action_id']}/permission",
                method=request,
                data=json.dumps(
                    {
                        "user_id": member_uname,
                        "priviledge": membership,
                    }
                ),
            )
            # updating the action for testing
            action: Action = datastore.action.get(create_res["action_id"], as_obj=True)
            if request == "PUT":
                assert member_uname in action.get_priviledge_mapping()[membership]
                continue
            assert member_uname not in action.get_priviledge_mapping()[membership]

    # Delete the action
    get_api_data(owner_session, f"{host}/api/v1/action/{create_res['action_id']}/", method="DELETE")


def test_owner_priviledge(datastore: HowlerDatastore, user_sessions: dict):
    owner_session, host = user_sessions["user"]
    member_session, _ = user_sessions["huey"]

    member_uname = get_api_data(member_session, f"{host}/api/v1/user/whoami", method="GET")["username"]
    owner_uname = get_api_data(owner_session, f"{host}/api/v1/user/whoami", method="GET")["username"]
    # Create the action
    create_res = get_api_data(
        owner_session,
        f"{host}/api/v1/action/",
        method="POST",
        data=json.dumps(
            {
                "name": "My totally awsome and unique action",
                "query": "howler.id:*",
                "classification": "UNRESTRICTED",
                "operations": [
                    {
                        "operation_id": "add_label",
                        "data_json": "{'category': 'generic', 'label': 'assigned'}",
                    }
                ],
            }
        ),
    )
    datastore.action.commit()
    action: Action = datastore.action.get(create_res["action_id"], as_obj=True)
    # adding|remove user to admin, member and owner
    add_permission_every_role(
        member_to_add=member_uname, create_res=create_res, member_requesting=owner_session, host=host, action=action
    )

    action = datastore.action.get(create_res["action_id"], as_obj=True)
    for membership in action.get_priviledge_mapping().keys():
        assert member_uname in action.get_priviledge_mapping()[membership]

    remove_permission_every_role(
        member_to_remove=member_uname, create_res=create_res, member_requesting=owner_session, host=host, action=action
    )

    action = datastore.action.get(create_res["action_id"], as_obj=True)
    for membership in action.get_priviledge_mapping().keys():
        assert member_uname not in action.get_priviledge_mapping()[membership]

    # Owner should be able to modify the action
    modifying_action(member_requesting=owner_session, host=host, create_res=create_res)
    action = datastore.action.get(create_res["action_id"], as_obj=True)
    assert action.name == "renamed_action"

    # Owner should be able to delete the action
    # Create an other temporary action
    total = datastore.action.search("action_id:*")["total"]

    create_res_copy = get_api_data(
        owner_session,
        f"{host}/api/v1/action/",
        method="POST",
        data=json.dumps(
            {
                "name": "test_copy",
                "query": "howler.id:*",
                "classification": "UNRESTRICTED",
                "operations": [
                    {
                        "operation_id": "add_label",
                        "data_json": "{'category': 'generic', 'label': 'assigned'}",
                    }
                ],
            }
        ),
    )
    datastore.action.commit()
    # Verify created properly
    assert total + 1 == datastore.action.search("action_id:*")["total"]

    # Giving ownership to an other user
    get_api_data(
        owner_session,
        f"{host}/api/v1/action/{create_res_copy['action_id']}/permission",
        method="PUT",
        data=json.dumps(
            {
                "user_id": member_uname,
                "priviledge": "owner",
            }
        ),
    )
    datastore.action.commit()
    get_api_data(
        owner_session,
        f"{host}/api/v1/action/{create_res_copy['action_id']}",
        method="DELETE",
    )
    datastore.action.commit()
    assert total == datastore.action.search("action_id:*")["total"]

    # Owner should be able to remove self if other owner exist
    get_api_data(
        owner_session,
        f"{host}/api/v1/action/{create_res['action_id']}/permission",
        method="PUT",
        data=json.dumps(
            {
                "user_id": member_uname,
                "priviledge": "owner",
            }
        ),
    )
    datastore.action.commit()
    get_api_data(
        owner_session,
        f"{host}/api/v1/action/{create_res['action_id']}/permission",
        method="DELETE",
        data=json.dumps(
            {
                "user_id": owner_uname,
                "priviledge": "owner",
            }
        ),
    )
    datastore.action.commit()
    action = datastore.action.get(create_res["action_id"], as_obj=True)
    assert owner_uname not in action.get_priviledge_mapping()["owner"]

    # Owner should not be able to remove self if no other owner exist
    try:
        get_api_data(
            member_session,
            f"{host}/api/v1/action/{create_res['action_id']}/permission",
            method="DELETE",
            data=json.dumps(
                {
                    "user_id": member_uname,
                    "priviledge": "owner",
                }
            ),
        )
    except Exception:
        # The error is intentional
        pass

    datastore.action.commit()

    assert member_uname in action.get_priviledge_mapping()["owner"]

    return


def test_admin(datastore: HowlerDatastore, user_sessions: dict, login_session):
    admin_session, host = user_sessions["user"]
    member_session, _ = user_sessions["huey"]
    owner_session, _ = login_session

    member_uname = get_api_data(member_session, f"{host}/api/v1/user/whoami", method="GET")["username"]
    owner_uname = get_api_data(owner_session, f"{host}/api/v1/user/whoami", method="GET")["username"]
    admin_uname = get_api_data(admin_session, f"{host}/api/v1/user/whoami", method="GET")["username"]
    # Create the action
    create_res = get_api_data(
        owner_session,
        f"{host}/api/v1/action/",
        method="POST",
        data=json.dumps(
            {
                "name": "My totally awsome and unique action",
                "query": "howler.id:*",
                "classification": "UNRESTRICTED",
                "operations": [
                    {
                        "operation_id": "add_label",
                        "data_json": "{'category': 'generic', 'label': 'assigned'}",
                    }
                ],
            }
        ),
    )
    datastore.action.commit()
    action: Action = datastore.action.get(create_res["action_id"], as_obj=True)
    # giving admin to admin
    get_api_data(
        owner_session,
        f"{host}/api/v1/action/{create_res['action_id']}/permission",
        method="PUT",
        data=json.dumps(
            {
                "user_id": admin_uname,
                "priviledge": "administrator",
            }
        ),
    )
    assert owner_uname not in action.get_priviledge_mapping()["administrator"]  # ensure user is admin

    # Admin should be able to add|remove member and other admin
    for method in ["PUT", "DELETE"]:
        get_api_data(
            admin_session,
            f"{host}/api/v1/action/{create_res['action_id']}/permission",
            method=method,
            data=json.dumps(
                {
                    "user_id": member_uname,
                    "priviledge": "administrator",
                }
            ),
        )
        datastore.action.commit()
        action = datastore.action.get(create_res["action_id"], as_obj=True)
        if method == "PUT":
            assert member_uname in action.get_priviledge_mapping()["administrator"]
            continue
        assert member_uname not in action.get_priviledge_mapping()["administrator"]

    # Admin should not be able to add|remove owner
    try:
        get_api_data(
            admin_session,
            f"{host}/api/v1/action/{create_res['action_id']}/permission",
            method="PUT",
            data=json.dumps(
                {
                    "user_id": member_uname,
                    "priviledge": "owner",
                }
            ),
        )
    except Exception:
        # intended to fail
        pass
    datastore.action.commit()
    action = datastore.action.get(create_res["action_id"], as_obj=True)
    assert member_uname not in action.get_priviledge_mapping()["owner"]
    try:
        get_api_data(
            admin_session,
            f"{host}/api/v1/action/{create_res['action_id']}/permission",
            method="DELETE",
            data=json.dumps(
                {
                    "user_id": admin_uname,
                    "priviledge": "owner",
                }
            ),
        )
    except Exception:
        # intended failed
        pass
    datastore.action.commit()
    action = datastore.action.get(create_res["action_id"], as_obj=True)
    assert admin_uname not in action.get_priviledge_mapping()["owner"]

    # Admin should not be able to delete action
    total = datastore.action.search("action_id:*")["total"]
    try:
        get_api_data(
            admin_session,
            f"{host}/api/v1/action/{create_res['action_id']}",
            method="DELETE",
        )
    except Exception:
        # intended fail
        pass
    datastore.action.commit()
    assert total == datastore.action.search("action_id:*")["total"]  # Should not have deleted

    # Admin should be able to modify the action
    modifying_action(
        member_requesting=admin_session,
        host=host,
        action_name="ADMIN_CHANGED_NAME",
        create_res=create_res,
    )
    datastore.action.commit()
    action = datastore.action.get(create_res["action_id"], as_obj=True)
    assert action.name == "ADMIN_CHANGED_NAME"

    # Admin should be able to remove self even if only admin
    get_api_data(
        admin_session,
        f"{host}/api/v1/action/{create_res['action_id']}/permission",
        method="DELETE",
        data=json.dumps(
            {
                "user_id": admin_uname,
                "priviledge": "administrator",
            }
        ),
    )
    datastore.action.commit()
    action = datastore.action.get(create_res["action_id"], as_obj=True)
    assert admin_uname not in action.get_priviledge_mapping()["administrator"]
    assert action.get_priviledge_mapping()["administrator"] == []

    return


def test_member(datastore: HowlerDatastore, user_sessions: dict, login_session):
    global_admin_session, _ = login_session
    owner_session, host = user_sessions["user"]
    member_session, _ = user_sessions["huey"]

    member_uname = get_api_data(member_session, f"{host}/api/v1/user/whoami", method="GET")["username"]
    owner_uname = get_api_data(owner_session, f"{host}/api/v1/user/whoami", method="GET")["username"]
    global_admin_uname = get_api_data(global_admin_session, f"{host}/api/v1/user/whoami", method="GET")["username"]

    # Create the action [unsure why owner can not create it]
    create_res = get_api_data(
        global_admin_session,
        f"{host}/api/v1/action/",
        method="POST",
        data=json.dumps(
            {
                "name": "My totally awsome and unique action",
                "query": "howler.id:*",
                "classification": "UNRESTRICTED",
                "operations": [
                    {
                        "operation_id": "add_label",
                        "data_json": "{'category': 'generic', 'label': 'assigned'}",
                    }
                ],
            }
        ),
    )
    datastore.action.commit()
    # Giving membership to member and ownership to owner

    get_api_data(
        global_admin_session,
        f"{host}/api/v1/action/{create_res['action_id']}/permission",
        method="PUT",
        data=json.dumps(
            {
                "user_id": owner_uname,
                "priviledge": "owner",
            }
        ),
    )
    datastore.action.commit()

    get_api_data(
        owner_session,
        f"{host}/api/v1/action/{create_res['action_id']}/permission",
        method="PUT",
        data=json.dumps(
            {
                "user_id": member_uname,
                "priviledge": "member",
            }
        ),
    )
    datastore.action.commit()
    get_api_data(
        owner_session,
        f"{host}/api/v1/action/{create_res['action_id']}/permission",
        method="DELETE",
        data=json.dumps(
            {
                "user_id": global_admin_uname,
                "priviledge": "owner",
            }
        ),
    )

    action = datastore.action.get(create_res["action_id"], as_obj=True)
    # Ensure the action has everything it should be working as
    assert action.get_priviledge_mapping()["owner"] == ["user"]
    assert action.get_priviledge_mapping()["member"] == ["huey"]
    assert action.get_priviledge_mapping()["administrator"] == []

    action: Action = datastore.action.get(create_res["action_id"], as_obj=True)
    assert member_uname in action.get_priviledge_mapping()["member"]  # ensure the membership was given

    # Member should not be able to add admin/owner/member
    add_permission_every_role(
        create_res=create_res, host=host, member_requesting=member_session, member_to_add=member_uname, action=action
    )
    datastore.action.commit()
    action = datastore.action.get(create_res["action_id"], as_obj=True)
    for membership in ["owner", "administrator"]:
        assert member_uname not in action.get_priviledge_mapping()[membership]

    # Member should not be able to remove admin/owner/member
    # adding owner into every role
    add_permission_every_role(
        create_res=create_res, host=host, member_requesting=owner_session, member_to_add=owner_uname, action=action
    )
    # verify owner is in every role
    datastore.action.commit()
    action = datastore.action.get(create_res["action_id"], as_obj=True)
    for membership in action.get_priviledge_mapping().keys():
        assert owner_uname in action.get_priviledge_mapping()[membership]

    remove_permission_every_role(
        create_res=create_res, host=host, member_requesting=member_session, member_to_remove=member_uname, action=action
    )
    # ensure owner is still in every role
    datastore.action.commit()
    action = datastore.action.get(create_res["action_id"], as_obj=True)
    for membership in action.get_priviledge_mapping().keys():
        assert owner_uname in action.get_priviledge_mapping()[membership]
    # Member should not be able to delete action
    total = datastore.action.search("action_id:*")["total"]
    try:
        get_api_data(
            member_session,
            f"{host}/api/v1/action/{create_res['action_id']}/",
            method="DELETE",
        )
    except Exception:
        # intended fail
        pass

    assert total == datastore.action.search("action_id:*")["total"]  # Should not have deleted

    modifying_action(
        member_requesting=member_session,
        host=host,
        action_name="MEMBER_CHANGED_NAME",
        create_res=create_res,
    )
    datastore.action.commit()
    action = datastore.action.get(create_res["action_id"], as_obj=True)
    assert action.name == "MEMBER_CHANGED_NAME"

    return


# endregion
