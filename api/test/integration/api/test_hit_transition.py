import json
from typing import Any, Optional

import pytest
from conftest import get_api_data

from howler.datastore.howler_store import HowlerDatastore
from howler.odm.helper import create_users_with_username
from howler.odm.models.howler_data import Assessment, HitStatus, HitStatusTransition
from howler.odm.random_data import create_users, wipe_hits

usernames = ["donald", "huey", "louie", "dewey"]
HIT_ID = "transition_test"
transition_test_hit = {
    "howler": {
        "id": "transition_test",
        "analytic": "transition_test-on-hold",
        "assignment": "unassigned",
        "hash": "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bc",
        "score": "0",
    },
}


@pytest.fixture(scope="module")
def datastore(datastore_connection: HowlerDatastore):
    try:
        wipe_hits(datastore_connection)
        create_users(datastore_connection)
        create_users_with_username(datastore_connection, usernames)

        # Create hits for get_hit test
        datastore_connection.hit.save("transition_test", transition_test_hit)

        # Commit changes to DataStore
        datastore_connection.hit.commit()

        yield datastore_connection
    finally:
        wipe_hits(datastore_connection)


def test_full_transition_flow(datastore: HowlerDatastore, login_session):
    """Test that /api/v1/hit/<id>/transitions/start endpoint performs the correct transition"""
    session, host = login_session

    assert datastore.hit.get(HIT_ID).howler.status == HitStatus.OPEN

    def check_assignment(user: str):
        def check():
            assert datastore.hit.get(HIT_ID).howler.assignment == user

        return check

    def check_assessment(assessment: Optional[str]):
        def check():
            assert datastore.hit.get(HIT_ID).howler.assessment == assessment

        return check

    def check_vote(email: str):
        def check():
            assert email in datastore.hit.get(HIT_ID).howler.votes.benign

        return check

    transition_data: list[dict[str, Any]] = [
        {
            "transition": HitStatusTransition.ASSESS,
            "data": {"assessment": Assessment.AMBIGUOUS},
            "dest": HitStatus.RESOLVED,
            "check": [check_assignment("admin")],
        },
        {
            "transition": HitStatusTransition.RE_EVALUATE,
            "dest": HitStatus.IN_PROGRESS,
            "check": [check_assessment(None), check_assignment("admin")],
        },
        {
            "transition": HitStatusTransition.RELEASE,
            "dest": HitStatus.OPEN,
            "check": [check_assessment(None), check_assignment("unassigned")],
        },
        {
            "transition": HitStatusTransition.ASSIGN_TO_ME,
            "dest": HitStatus.IN_PROGRESS,
            "check": [check_assessment(None), check_assignment("admin")],
        },
        {
            "transition": HitStatusTransition.RELEASE,
            "dest": HitStatus.OPEN,
            "check": [check_assessment(None), check_assignment("unassigned")],
        },
        {
            "transition": HitStatusTransition.ASSIGN_TO_OTHER,
            "data": {"assignee": "user"},
            "dest": HitStatus.OPEN,
            "check": [check_assessment(None), check_assignment("user")],
        },
        {
            "transition": HitStatusTransition.ASSIGN_TO_ME,
            "dest": HitStatus.IN_PROGRESS,
            "check": [check_assessment(None), check_assignment("admin")],
        },
        {
            "transition": HitStatusTransition.ASSIGN_TO_OTHER,
            "data": {"assignee": "user"},
            "dest": HitStatus.IN_PROGRESS,
            "check": [check_assessment(None), check_assignment("user")],
        },
        {
            "transition": HitStatusTransition.ASSIGN_TO_ME,
            "dest": HitStatus.IN_PROGRESS,
            "check": [check_assessment(None), check_assignment("admin")],
        },
        {
            "transition": HitStatusTransition.PAUSE,
            "dest": HitStatus.ON_HOLD,
        },
        {
            "transition": HitStatusTransition.RESUME,
            "dest": HitStatus.IN_PROGRESS,
        },
        {
            "transition": HitStatusTransition.ASSIGN_TO_ME,
            "dest": HitStatus.IN_PROGRESS,
            "check": [check_assessment(None), check_assignment("admin")],
        },
        {
            "transition": HitStatusTransition.RELEASE,
            "dest": HitStatus.OPEN,
            "check": [check_assessment(None), check_assignment("unassigned")],
        },
        {
            "transition": HitStatusTransition.ASSIGN_TO_ME,
            "dest": HitStatus.IN_PROGRESS,
            "check": [check_assessment(None), check_assignment("admin")],
        },
        {
            "transition": HitStatusTransition.ASSESS,
            "data": {"assessment": Assessment.AMBIGUOUS},
            "dest": HitStatus.RESOLVED,
            "check": [
                check_assessment(Assessment.AMBIGUOUS),
                check_assignment("admin"),
            ],
        },
        {
            "transition": HitStatusTransition.RE_EVALUATE,
            "dest": HitStatus.IN_PROGRESS,
            "check": [check_assessment(None), check_assignment("admin")],
        },
        {
            "transition": HitStatusTransition.RELEASE,
            "dest": HitStatus.OPEN,
            "check": [check_assessment(None), check_assignment("unassigned")],
        },
        {
            "transition": HitStatusTransition.VOTE,
            "data": {"vote": "benign", "email": "user@user.com"},
            "dest": HitStatus.OPEN,
            "check": [check_assessment(None), check_vote("user@user.com")],
        },
    ]

    for data in transition_data:
        checks = data.pop("check", None)
        _, version = datastore.hit.get(HIT_ID, as_obj=False, version=True)
        get_api_data(
            session=session,
            url=f"{host}/api/v1/hit/{HIT_ID}/transition/",
            method="POST",
            data=json.dumps(data),
            headers={
                "If-Match": version,
                "content-type": "application/json",
            },
        )

        if checks:
            for c in checks:
                c()

        datastore.hit.get(HIT_ID).howler.status == data["dest"]

    # hit: Hit = datastore.hit.get(HIT_ID, as_obj=False)
    # assert hit["howler"]["status"] == HitStatus.IN_PROGRESS
    # assert hit["howler"]["assignment"] == "admin"
