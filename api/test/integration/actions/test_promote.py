import json
import time
from uuid import uuid4

import pytest

from howler.datastore.howler_store import HowlerDatastore
from howler.odm.models.howler_data import Assessment, Escalation
from howler.odm.random_data import create_hits, wipe_hits
from test.conftest import get_api_data

# Assessments that map to the "evidence" escalation
EVIDENCE_ASSESSMENTS = [a for a in Assessment.list() if a in ("attempt", "compromise", "mitigated", "recon", "trivial")]


def _execute(session, host, query: str, escalation: str, assessment: str | None = None):
    data: dict = {"escalation": escalation}
    if assessment is not None:
        data["assessment"] = assessment

    req = {
        "request_id": str(uuid4()),
        "query": query,
        "operations": [
            {
                "operation_id": "promote",
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


def test_promote_to_alert(datastore: HowlerDatastore, login_session):
    """Hits are promoted to the 'alert' escalation successfully."""
    session, host = login_session

    resp = _execute(session, host, query="howler.id:*", escalation=Escalation.ALERT)

    for report in resp.values():
        outcomes = {e["outcome"] for e in report}
        assert "success" in outcomes

        for entry in report:
            assert "query" in entry
            assert "title" in entry
            assert "message" in entry

    datastore.hit.commit()
    time.sleep(1)

    promoted = datastore.hit.search(f"howler.escalation:{Escalation.ALERT}")["total"]
    assert promoted > 0


def test_promote_to_hit_escalation(datastore: HowlerDatastore, login_session):
    """Hits can be promoted to the 'hit' escalation (i.e. reset)."""
    session, host = login_session

    resp = _execute(session, host, query="howler.id:*", escalation=Escalation.HIT)

    for report in resp.values():
        outcomes = {e["outcome"] for e in report}
        assert "success" in outcomes or "skipped" in outcomes


def test_promote_to_evidence_with_assessment(datastore: HowlerDatastore, login_session):
    """Hits are promoted to 'evidence' when a valid evidence-mapped assessment is supplied."""
    session, host = login_session

    resp = _execute(
        session,
        host,
        query="howler.id:*",
        escalation=Escalation.EVIDENCE,
        assessment=EVIDENCE_ASSESSMENTS[0],
    )

    for report in resp.values():
        outcomes = {e["outcome"] for e in report}
        assert "success" in outcomes


# ---------------------------------------------------------------------------
# Already-at-target escalation is skipped
# ---------------------------------------------------------------------------


def test_promote_already_at_escalation_skipped(datastore: HowlerDatastore, login_session):
    """Hits already at the target escalation produce a skipped outcome."""
    session, host = login_session

    # First promote to alert
    _execute(session, host, query="howler.id:*", escalation=Escalation.ALERT)
    datastore.hit.commit()
    time.sleep(1)

    # Second call with same escalation — all hits already there
    resp = _execute(session, host, query=f"howler.escalation:{Escalation.ALERT}", escalation=Escalation.ALERT)

    for report in resp.values():
        outcomes = {e["outcome"] for e in report}
        assert "skipped" in outcomes


# ---------------------------------------------------------------------------
# Invalid inputs
# ---------------------------------------------------------------------------


def test_promote_invalid_escalation(datastore: HowlerDatastore, login_session):
    """An unknown escalation value returns an error outcome."""
    session, host = login_session

    resp = _execute(session, host, query="howler.id:*", escalation="not_a_real_escalation")

    for report in resp.values():
        assert len(report) == 1
        entry = report[0]
        assert entry["outcome"] == "error"
        assert "not_a_real_escalation" in entry["message"]


def test_promote_to_evidence_missing_assessment(datastore: HowlerDatastore, login_session):
    """Promoting to 'evidence' without an assessment returns an error outcome."""
    session, host = login_session

    resp = _execute(session, host, query="howler.id:*", escalation=Escalation.EVIDENCE)

    for report in resp.values():
        assert len(report) == 1
        entry = report[0]
        assert entry["outcome"] == "error"
        assert "assessment" in entry["message"].lower()


def test_promote_miss_is_invalid(datastore: HowlerDatastore, login_session):
    """'miss' is not a valid target escalation for promote and returns an error."""
    session, host = login_session

    resp = _execute(session, host, query="howler.id:*", escalation=Escalation.MISS)

    for report in resp.values():
        assert len(report) == 1
        entry = report[0]
        assert entry["outcome"] == "error"
