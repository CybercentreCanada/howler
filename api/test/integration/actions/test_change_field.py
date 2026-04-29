import json
import time
from uuid import uuid4

import pytest

from howler.datastore.howler_store import HowlerDatastore
from howler.odm.random_data import create_hits, wipe_hits
from test.conftest import get_api_data


def _execute(session, host, query: str, field: str, value: str):
    req = {
        "request_id": str(uuid4()),
        "query": query,
        "operations": [
            {
                "operation_id": "change_field",
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


def test_change_field_happy_path(datastore: HowlerDatastore, login_session):
    """A valid field is updated on all matching hits and reports success."""
    session, host = login_session

    resp = _execute(
        session,
        host,
        query="howler.id:*",
        field="howler.outline.summary",
        value="integration-test-summary",
    )

    for report in resp.values():
        assert len(report) == 1
        entry = report[0]
        assert entry["outcome"] == "success"
        assert "howler.outline.summary" in entry["message"]
        assert "integration-test-summary" in entry["message"]

    datastore.hit.commit()
    time.sleep(1)

    updated = datastore.hit.search("howler.outline.summary:integration-test-summary")["total"]
    assert updated > 0


def test_change_field_updates_all_matching(datastore: HowlerDatastore, login_session):
    """Only hits matching the query are updated."""
    session, host = login_session

    first_hit = datastore.hit.search("howler.id:*", rows=1)["items"][0]
    query = f"howler.id:{first_hit.howler.id}"

    resp = _execute(
        session,
        host,
        query=query,
        field="howler.outline.summary",
        value="single-hit-summary",
    )

    for report in resp.values():
        assert len(report) == 1
        assert report[0]["outcome"] == "success"

    datastore.hit.commit()
    time.sleep(1)

    updated = datastore.hit.search("howler.outline.summary:single-hit-summary")["total"]
    assert updated == 1


# ---------------------------------------------------------------------------
# Invalid inputs
# ---------------------------------------------------------------------------


def test_change_field_invalid_field(datastore: HowlerDatastore, login_session):
    """A field that does not exist on the Hit model returns an error outcome."""
    session, host = login_session

    resp = _execute(
        session,
        host,
        query="howler.id:*",
        field="howler.does_not_exist_at_all",
        value="whatever",
    )

    for report in resp.values():
        assert len(report) == 1
        entry = report[0]
        assert entry["outcome"] == "error"
        assert "howler.does_not_exist_at_all" in entry["message"]
