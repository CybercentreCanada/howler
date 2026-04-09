import json
import time
from uuid import uuid4

import pytest

from howler.datastore.howler_store import HowlerDatastore
from howler.odm.random_data import create_hits, wipe_hits
from test.conftest import get_api_data


def _execute(session, host, query: str, category: str, label: str):
    req = {
        "request_id": str(uuid4()),
        "query": query,
        "operations": [
            {
                "operation_id": "add_label",
                "data_json": json.dumps({"category": category, "label": label}),
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


def test_add_label_happy_path(datastore: HowlerDatastore, login_session):
    """Label is applied to all matching hits and reports success."""
    session, host = login_session

    resp = _execute(session, host, query="howler.id:*", category="generic", label="test-add-label")

    for report in resp.values():
        outcomes = {e["outcome"] for e in report}
        assert "success" in outcomes

        for entry in report:
            assert "query" in entry
            assert "title" in entry
            assert "message" in entry

    datastore.hit.commit()
    time.sleep(1)

    labelled = datastore.hit.search("howler.labels.generic:test-add-label")["total"]
    assert labelled > 0


# ---------------------------------------------------------------------------
# Already-labelled hits are skipped
# ---------------------------------------------------------------------------


def test_add_label_already_labelled_skipped(datastore: HowlerDatastore, login_session):
    """Hits that already carry the label produce a skipped outcome on the second call."""
    session, host = login_session

    # First call adds the label
    _execute(session, host, query="howler.id:*", category="generic", label="test-skip-label")

    datastore.hit.commit()
    time.sleep(1)

    # Second call — all hits already have the label
    resp = _execute(session, host, query="howler.id:*", category="generic", label="test-skip-label")

    for report in resp.values():
        outcomes = {e["outcome"] for e in report}
        assert "skipped" in outcomes


# ---------------------------------------------------------------------------
# Invalid inputs
# ---------------------------------------------------------------------------


def test_add_label_invalid_category(datastore: HowlerDatastore, login_session):
    """An unknown category returns an error outcome."""
    session, host = login_session

    resp = _execute(session, host, query="howler.id:*", category="not_a_real_category", label="potato")

    for report in resp.values():
        assert len(report) == 1
        entry = report[0]
        assert entry["outcome"] == "error"
        assert "not_a_real_category" in entry["message"]


def test_add_label_empty_label(datastore: HowlerDatastore, login_session):
    """An empty label string returns an error outcome."""
    session, host = login_session

    resp = _execute(session, host, query="howler.id:*", category="generic", label="")

    for report in resp.values():
        assert len(report) == 1
        entry = report[0]
        assert entry["outcome"] == "error"
