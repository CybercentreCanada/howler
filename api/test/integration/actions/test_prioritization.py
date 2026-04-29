import json
import time
from uuid import uuid4

import pytest

from howler.datastore.howler_store import HowlerDatastore
from howler.odm.random_data import create_hits, wipe_hits
from test.conftest import get_api_data

VALID_FIELDS = ["reliability", "severity", "volume", "confidence", "score"]


def _execute(session, host, query: str, field: str, value: str):
    req = {
        "request_id": str(uuid4()),
        "query": query,
        "operations": [
            {
                "operation_id": "prioritization",
                "data_json": json.dumps({"field": field, "value": value}),
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


def test_prioritization_happy_path(datastore: HowlerDatastore, login_session):
    """A valid prioritization field is updated on all matching hits."""
    session, host = login_session

    resp = _execute(session, host, query="howler.id:*", field="score", value="7.5")

    for report in resp.values():
        assert len(report) == 1
        entry = report[0]
        assert entry["outcome"] == "success"
        assert "howler.score" in entry["message"]
        assert "7.5" in entry["message"]

    datastore.hit.commit()
    time.sleep(1)

    updated = datastore.hit.search("howler.score:[7 TO 8]")["total"]
    assert updated > 0


@pytest.mark.parametrize("field", VALID_FIELDS)
def test_prioritization_all_valid_fields(datastore: HowlerDatastore, login_session, field):
    """Each valid prioritization field can be set without error."""
    session, host = login_session

    resp = _execute(session, host, query="howler.id:*", field=field, value="5.0")

    for report in resp.values():
        assert len(report) == 1
        assert report[0]["outcome"] == "success"


# ---------------------------------------------------------------------------
# Invalid inputs
# ---------------------------------------------------------------------------


def test_prioritization_invalid_field(datastore: HowlerDatastore, login_session):
    """An unsupported field name returns an error outcome."""
    session, host = login_session

    resp = _execute(session, host, query="howler.id:*", field="bogus_field", value="1.0")

    for report in resp.values():
        assert len(report) == 1
        entry = report[0]
        assert entry["outcome"] == "error"
        assert "bogus_field" in entry["message"]


def test_prioritization_non_float_value(datastore: HowlerDatastore, login_session):
    """A non-numeric value string returns an error outcome."""
    session, host = login_session

    resp = _execute(session, host, query="howler.id:*", field="score", value="not_a_number")

    for report in resp.values():
        assert len(report) == 1
        entry = report[0]
        assert entry["outcome"] == "error"
        assert "not_a_number" in entry["message"]
