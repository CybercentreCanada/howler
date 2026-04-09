import json
import time
from uuid import uuid4

import pytest

from howler.datastore.howler_store import HowlerDatastore
from howler.odm.models.case import Case
from howler.odm.random_data import create_hits, wipe_cases, wipe_hits
from test.conftest import get_api_data


def _make_case(title: str) -> dict:
    return {
        "title": title,
        "summary": "Integration test case for add_to_case action.",
    }


def _execute(session, host, query: str, case_id: str, path: str = "related", title_template: str | None = None):
    data: dict = {"case_id": case_id, "path": path}
    if title_template is not None:
        data["title_template"] = title_template

    req = {
        "request_id": str(uuid4()),
        "query": query,
        "operations": [
            {
                "operation_id": "add_to_case",
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
        wipe_cases(ds)
        create_hits(ds, hit_count=5)

        ds.hit.commit()
        ds.case.commit()

        time.sleep(1)

        yield ds
    finally:
        wipe_hits(ds)
        wipe_cases(ds)


@pytest.fixture()
def test_case(datastore: HowlerDatastore, login_session) -> Case:
    """Create a fresh case for each test and clean it up afterward."""
    session, host = login_session

    resp = get_api_data(
        session,
        f"{host}/api/v2/case",
        method="POST",
        data=json.dumps(_make_case("add_to_case integration test case")),
    )
    case_id = resp["case_id"]

    datastore.case.commit()

    yield datastore.case.get(case_id)

    datastore.case.delete(case_id)
    datastore.case.commit()


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_add_to_case_happy_path(datastore: HowlerDatastore, login_session, test_case: Case):
    """Hits matching the query are successfully added to the case."""
    session, host = login_session

    resp = _execute(session, host, query="howler.id:*", case_id=test_case.case_id)

    reports = list(resp.values())
    assert len(reports) == 1
    report = reports[0]

    # At least one success report
    outcomes = {entry["outcome"] for entry in report}
    assert "success" in outcomes, f"Expected at least one success, got: {report}"

    for entry in report:
        assert "query" in entry
        assert "title" in entry
        assert "message" in entry

    # Case is updated with the expected items
    datastore.case.commit()
    time.sleep(1)

    updated = datastore.case.get(test_case.case_id)
    assert len(updated.items) > 0
    item_values = [item.value for item in updated.items]

    successful_ids = [
        hit_id
        for entry in report
        if entry["outcome"] == "success"
        for hit_id in datastore.hit.search(entry["query"], rows=100)["items"]
    ]
    for hit in successful_ids:
        hit_id = hit.howler.id if hasattr(hit, "howler") else hit["howler"]["id"]
        assert hit_id in item_values


def test_add_to_case_custom_path_and_template(datastore: HowlerDatastore, login_session, test_case: Case):
    """Items are placed at the specified path using the title template."""
    session, host = login_session

    # Take only the first hit to keep things deterministic
    first_hit = datastore.hit.search("howler.id:*", rows=1)["items"][0]
    query = f"howler.id:{first_hit.howler.id}"

    resp = _execute(
        session,
        host,
        query=query,
        case_id=test_case.case_id,
        path="investigations/test",
        title_template="{{howler.id}}",
    )

    reports = list(resp.values())
    assert len(reports) == 1
    report = reports[0]

    success_entries = [e for e in report if e["outcome"] == "success"]
    assert len(success_entries) == 1

    datastore.case.commit()
    time.sleep(1)

    updated = datastore.case.get(test_case.case_id)
    matching = [item for item in updated.items if item.value == first_hit.howler.id]
    assert len(matching) == 1
    assert matching[0].path == f"investigations/test/{first_hit.howler.id}"


# ---------------------------------------------------------------------------
# Missing / invalid case_id
# ---------------------------------------------------------------------------


def test_add_to_case_missing_case_id(datastore: HowlerDatastore, login_session):
    """Omitting case_id returns an error outcome."""
    session, host = login_session

    req = {
        "request_id": str(uuid4()),
        "query": "howler.id:*",
        "operations": [
            {
                "operation_id": "add_to_case",
                "data_json": json.dumps({"path": "related"}),
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
        entry = report[0]
        assert entry["outcome"] == "error"
        assert "case_id" in entry["message"].lower() or "case id" in entry["message"].lower()


def test_add_to_case_invalid_case_id(datastore: HowlerDatastore, login_session):
    """A non-existent case_id returns an error outcome."""
    session, host = login_session

    resp = _execute(session, host, query="howler.id:*", case_id="00000000-0000-0000-0000-000000000000")

    for report in resp.values():
        assert len(report) == 1
        entry = report[0]
        assert entry["outcome"] == "error"
        assert "00000000-0000-0000-0000-000000000000" in entry["message"]


# ---------------------------------------------------------------------------
# Duplicate hit handling
# ---------------------------------------------------------------------------


def test_add_to_case_duplicate_hit(datastore: HowlerDatastore, login_session, test_case: Case):
    """Adding the same hit twice results in a skipped outcome on the second call."""
    session, host = login_session

    first_hit = datastore.hit.search("howler.id:*", rows=1)["items"][0]
    query = f"howler.id:{first_hit.howler.id}"

    # First add — should succeed
    resp1 = _execute(session, host, query=query, case_id=test_case.case_id)
    for report in resp1.values():
        outcomes = {e["outcome"] for e in report}
        assert "success" in outcomes

    datastore.case.commit()
    time.sleep(1)

    # Second add — same hit should be skipped
    resp2 = _execute(session, host, query=query, case_id=test_case.case_id)
    for report in resp2.values():
        outcomes = {e["outcome"] for e in report}
        assert "success" not in outcomes
        assert "skipped" in outcomes or "error" in outcomes
