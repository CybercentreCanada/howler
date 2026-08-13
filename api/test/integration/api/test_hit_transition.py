import datetime
import json
from typing import Any, Literal, Optional

import pytest

from howler.config import CLASSIFICATION
from howler.datastore.howler_store import HowlerDatastore
from howler.odm.helper import create_users_with_username
from howler.odm.models.howler_data import Assessment, HitStatusTransition, Status
from howler.odm.random_data import wipe_hits
from test.conftest import get_api_data

usernames = ["donald", "huey", "louie", "dewey"]
HIT_ID = "transition_test"
transition_test_hit = {
    "howler": {
        "id": "transition_test",
        "analytic": "transition_test-on-hold",
        "assignment": "unassigned",
        "hash": "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bc",
        "score": "0",
        "classification": CLASSIFICATION.UNRESTRICTED,
    },
}


@pytest.fixture(scope="module")
def datastore(datastore_connection: HowlerDatastore):
    try:
        wipe_hits(datastore_connection)
        create_users_with_username(datastore_connection, usernames)

        # Create hits for get_hit test
        datastore_connection.hit.save("transition_test", transition_test_hit)

        # Commit changes to DataStore
        datastore_connection.hit.commit()

        yield datastore_connection
    finally:
        wipe_hits(datastore_connection)


@pytest.fixture(scope="module")
def transition_data(datastore: HowlerDatastore) -> list[dict[str, Any]]:

    def check_assignment(username: str):
        def check():
            assert datastore.hit.get(HIT_ID).howler.assignment == username

        return check

    def check_assessment(assessment: Optional[str]):
        def check():
            assert datastore.hit.get(HIT_ID).howler.assessment == assessment

        return check

    def check_vote(email: str):
        def check():
            assert email in datastore.hit.get(HIT_ID).howler.votes.benign

        return check

    def check_triaged(assessment_time: Literal["NOW"] | None):
        def check():
            tolerance = datetime.timedelta(seconds=10)

            triaged_timestamp = datastore.hit.get(HIT_ID).howler.triaged
            if assessment_time is None:
                assert triaged_timestamp is None
            else:
                assert triaged_timestamp is not None
                assert abs(triaged_timestamp - datetime.datetime.now(datetime.timezone.utc)) < tolerance

        return check

    return [
        {
            "transition": HitStatusTransition.ASSESS,
            "data": {"assessment": Assessment.AMBIGUOUS},
            "dest": Status.RESOLVED,
            "check": [check_assignment("admin"), check_triaged("NOW")],
        },
        {
            "transition": HitStatusTransition.RE_EVALUATE,
            "dest": Status.IN_PROGRESS,
            "check": [check_assessment(None), check_assignment("admin"), check_triaged(None)],
        },
        {
            "transition": HitStatusTransition.RELEASE,
            "dest": Status.OPEN,
            "check": [check_assessment(None), check_assignment("unassigned")],
        },
        {
            "transition": HitStatusTransition.ASSIGN_TO_ME,
            "dest": Status.IN_PROGRESS,
            "check": [check_assessment(None), check_assignment("admin")],
        },
        {
            "transition": HitStatusTransition.RELEASE,
            "dest": Status.OPEN,
            "check": [check_assessment(None), check_assignment("unassigned")],
        },
        {
            "transition": HitStatusTransition.ASSIGN_TO_OTHER,
            "data": {"assignee": "user"},
            "dest": Status.OPEN,
            "check": [check_assessment(None), check_assignment("user")],
        },
        {
            "transition": HitStatusTransition.ASSIGN_TO_ME,
            "dest": Status.IN_PROGRESS,
            "check": [check_assessment(None), check_assignment("admin")],
        },
        {
            "transition": HitStatusTransition.ASSIGN_TO_OTHER,
            "data": {"assignee": "user"},
            "dest": Status.IN_PROGRESS,
            "check": [check_assessment(None), check_assignment("user")],
        },
        {
            "transition": HitStatusTransition.ASSIGN_TO_ME,
            "dest": Status.IN_PROGRESS,
            "check": [check_assessment(None), check_assignment("admin")],
        },
        {
            "transition": HitStatusTransition.PAUSE,
            "dest": Status.ON_HOLD,
        },
        {
            "transition": HitStatusTransition.RESUME,
            "dest": Status.IN_PROGRESS,
        },
        {
            "transition": HitStatusTransition.ASSIGN_TO_ME,
            "dest": Status.IN_PROGRESS,
            "check": [check_assessment(None), check_assignment("admin")],
        },
        {
            "transition": HitStatusTransition.RELEASE,
            "dest": Status.OPEN,
            "check": [check_assessment(None), check_assignment("unassigned")],
        },
        {
            "transition": HitStatusTransition.ASSIGN_TO_ME,
            "dest": Status.IN_PROGRESS,
            "check": [check_assessment(None), check_assignment("admin")],
        },
        {
            "transition": HitStatusTransition.ASSESS,
            "data": {"assessment": Assessment.AMBIGUOUS},
            "dest": Status.RESOLVED,
            "check": [
                check_assessment(Assessment.AMBIGUOUS),
                check_assignment("admin"),
                check_triaged("NOW"),
            ],
        },
        {
            "transition": HitStatusTransition.RE_EVALUATE,
            "dest": Status.IN_PROGRESS,
            "check": [check_assessment(None), check_assignment("admin"), check_triaged(None)],
        },
        {
            "transition": HitStatusTransition.RELEASE,
            "dest": Status.OPEN,
            "check": [check_assessment(None), check_assignment("unassigned")],
        },
        {
            "transition": HitStatusTransition.VOTE,
            "data": {"vote": "benign", "email": "user@user.com"},
            "dest": Status.OPEN,
            "check": [check_assessment(None), check_vote("user@user.com")],
        },
    ]


def test_full_transition_flow(transition_data, datastore, login_session):
    """Test that /api/v1/hit/<id>/transitions/start endpoint performs the correct transition"""
    session, host = login_session

    assert datastore.hit.get(HIT_ID).howler.status == Status.OPEN

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

        assert datastore.hit.get(HIT_ID).howler.status == data["dest"]

    # hit: Hit = datastore.hit.get(HIT_ID, as_obj=False)
    # assert hit["howler"]["status"] == Status.IN_PROGRESS
    # assert hit["howler"]["assignment"] == "admin"
