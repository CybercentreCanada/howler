import json
import time
from uuid import uuid4

import pytest

from howler.datastore.howler_store import HowlerDatastore
from howler.odm.models.howler_data import Assessment, Escalation
from howler.odm.random_data import create_hits, wipe_hits
from test.conftest import get_api_data

# Assessments that map to the "miss" escalation
MISS_ASSESSMENTS = [
    a for a in Assessment.list() if a in ("ambiguous", "development", "false-positive", "legitimate", "security")
]


def _execute(session, host, query: str, escalation: str, assessment: str | None = None):
    data: dict = {"escalation": escalation}
    if assessment is not None:
        data["assessment"] = assessment

    req = {
        "request_id": str(uuid4()),
        "query": query,
        "operations": [
            {
                "operation_id": "demote",
                "data_json": json.dumps(data),
            }
        ],
    }
    return get_api_data(
        session,
        f"{host}/api/v1/action/execute",
        method="POST",
        data=json.dumps(req),
    )


def _promote_to_alert(session, host, query: str):
    req = {
        "request_id": str(uuid4()),
        "query": query,
        "operations": [
            {
                "operation_id": "promote",
                "data_json": json.dumps({"escalation": Escalation.ALERT}),
            }
        ],
    }
    get_api_data(
        session,
        f"{host}/api/v1/action/execute",
        method="POST",
        data=json.dumps(req),
    )


@pytest.fixture(scope="module")
def datastore(datastore_connection):
    ds = datastore_connection

    try:
        wipe_hits(ds)
        create_hits(ds, hit_count=5)

        ds.hit.commit()

        time.sleep(1)

        yield ds
    finally:
        wipe_hits(ds)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_demote_to_hit(datastore: HowlerDatastore, login_session):
    """Hits at 'alert' escalation are demoted to 'hit' successfully."""
    session, host = login_session

    # Ensure hits are at alert first
    _promote_to_alert(session, host, query="howler.id:*")
    datastore.hit.commit()
    time.sleep(1)

    resp = _execute(session, host, query="howler.id:*", escalation=Escalation.HIT)

    for report in resp.values():
        outcomes = {e["outcome"] for e in report}
        assert "success" in outcomes

        for entry in report:
            assert "query" in entry
            assert "title" in entry
            assert "message" in entry

    datastore.hit.commit()
    time.sleep(1)

    demoted = datastore.hit.search(f"howler.escalation:{Escalation.HIT}")["total"]
    assert demoted > 0


def test_demote_to_alert(datastore: HowlerDatastore, login_session):
    """Hits can be demoted to the 'alert' escalation."""
    session, host = login_session

    resp = _execute(session, host, query="howler.id:*", escalation=Escalation.ALERT)

    for report in resp.values():
        outcomes = {e["outcome"] for e in report}
        assert "success" in outcomes or "skipped" in outcomes


def test_demote_to_miss_with_assessment(datastore: HowlerDatastore, login_session):
    """Hits are demoted to 'miss' when a valid miss-mapped assessment is supplied."""
    session, host = login_session

    resp = _execute(
        session,
        host,
        query="howler.id:*",
        escalation=Escalation.MISS,
        assessment=MISS_ASSESSMENTS[0],
    )

    for report in resp.values():
        outcomes = {e["outcome"] for e in report}
        assert "success" in outcomes


# ---------------------------------------------------------------------------
# Already-at-target escalation is skipped
# ---------------------------------------------------------------------------


def test_demote_already_at_escalation_skipped(datastore: HowlerDatastore, login_session):
    """Hits already at the target escalation produce a skipped outcome."""
    session, host = login_session

    # Ensure all hits are at hit escalation
    _execute(session, host, query="howler.id:*", escalation=Escalation.HIT)
    datastore.hit.commit()
    time.sleep(1)

    # Second call with same target — already there
    resp = _execute(session, host, query=f"howler.escalation:{Escalation.HIT}", escalation=Escalation.HIT)

    for report in resp.values():
        outcomes = {e["outcome"] for e in report}
        assert "skipped" in outcomes


# ---------------------------------------------------------------------------
# Invalid inputs
# ---------------------------------------------------------------------------


def test_demote_invalid_escalation(datastore: HowlerDatastore, login_session):
    """An unknown escalation value returns an error outcome."""
    session, host = login_session

    resp = _execute(session, host, query="howler.id:*", escalation="not_a_real_escalation")

    for report in resp.values():
        assert len(report) == 1
        entry = report[0]
        assert entry["outcome"] == "error"
        assert "not_a_real_escalation" in entry["message"]


def test_demote_to_miss_missing_assessment(datastore: HowlerDatastore, login_session):
    """Demoting to 'miss' without an assessment returns an error outcome."""
    session, host = login_session

    resp = _execute(session, host, query="howler.id:*", escalation=Escalation.MISS)

    for report in resp.values():
        assert len(report) == 1
        entry = report[0]
        assert entry["outcome"] == "error"
        assert "assessment" in entry["message"].lower()


def test_demote_evidence_is_invalid(datastore: HowlerDatastore, login_session):
    """'evidence' is not a valid target escalation for demote and returns an error."""
    session, host = login_session

    resp = _execute(session, host, query="howler.id:*", escalation=Escalation.EVIDENCE)

    for report in resp.values():
        assert len(report) == 1
        entry = report[0]
        assert entry["outcome"] == "error"
