import json
import time

import pytest

from howler.datastore.howler_store import HowlerDatastore
from howler.odm.random_data import wipe_cases
from test.conftest import get_api_data


def _make_case(title: str = "Rule Integration Test Case") -> dict:
    return {
        "title": title,
        "summary": "Integration test case for correlation rule endpoints.",
    }


@pytest.fixture(scope="module")
def datastore(datastore_connection):
    ds = datastore_connection
    try:
        wipe_cases(ds)
        ds.case.commit()
        time.sleep(1)
        yield ds
    finally:
        wipe_cases(ds)


@pytest.fixture()
def test_case(datastore: HowlerDatastore, login_session):
    """Create a fresh case for each test and clean it up afterward."""
    session, host = login_session

    resp = get_api_data(
        session,
        f"{host}/api/v2/case",
        method="POST",
        data=json.dumps(_make_case()),
    )
    case_id = resp["case_id"]
    datastore.case.commit()

    yield case_id, session, host

    datastore.case.delete(case_id)


class TestAddRule:
    """Integration tests for POST /api/v2/case/<id>/rules."""

    def test_add_rule_success(self, test_case):
        case_id, session, host = test_case

        rule_data = {
            "query": "event.kind:alert",
            "destination": "alerts/{{howler.analytic}}",
            "timeframe": "2026-06-01T00:00:00Z",
        }

        resp = get_api_data(
            session,
            f"{host}/api/v2/case/{case_id}/rules",
            method="POST",
            data=json.dumps(rule_data),
        )

        assert "rules" in resp
        assert len(resp["rules"]) == 1
        rule = resp["rules"][0]
        assert rule["query"] == "event.kind:alert"
        assert rule["destination"] == "alerts/{{howler.analytic}}"
        assert rule["author"] is not None
        assert rule["enabled"] is True
        assert rule["rule_id"] is not None

    def test_add_rule_no_expiry(self, test_case):
        case_id, session, host = test_case

        rule_data = {
            "query": "event.kind:alert",
            "destination": "alerts/all",
        }

        resp = get_api_data(
            session,
            f"{host}/api/v2/case/{case_id}/rules",
            method="POST",
            data=json.dumps(rule_data),
        )

        rule = resp["rules"][0]
        assert rule.get("timeframe") is None

    def test_add_rule_missing_query_returns_400(self, test_case):
        case_id, session, host = test_case

        resp = get_api_data(
            session,
            f"{host}/api/v2/case/{case_id}/rules",
            method="POST",
            data=json.dumps({"destination": "alerts/all"}),
            raw=True,
        )

        assert resp.status_code == 400

    def test_add_rule_missing_destination_returns_400(self, test_case):
        case_id, session, host = test_case

        resp = get_api_data(
            session,
            f"{host}/api/v2/case/{case_id}/rules",
            method="POST",
            data=json.dumps({"query": "*:*"}),
            raw=True,
        )

        assert resp.status_code == 400


class TestDeleteRule:
    """Integration tests for DELETE /api/v2/case/<id>/rules/<rule_id>."""

    def test_delete_rule_success(self, test_case):
        case_id, session, host = test_case

        add_resp = get_api_data(
            session,
            f"{host}/api/v2/case/{case_id}/rules",
            method="POST",
            data=json.dumps({"query": "*:*", "destination": "alerts/all"}),
        )
        rule_id = add_resp["rules"][0]["rule_id"]

        del_resp = get_api_data(
            session,
            f"{host}/api/v2/case/{case_id}/rules/{rule_id}",
            method="DELETE",
        )

        assert len(del_resp["rules"]) == 0

    def test_delete_rule_not_found_returns_404(self, test_case):
        case_id, session, host = test_case

        resp = get_api_data(
            session,
            f"{host}/api/v2/case/{case_id}/rules/nonexistent-rule-id",
            method="DELETE",
            raw=True,
        )

        assert resp.status_code == 404


class TestUpdateRule:
    """Integration tests for PUT /api/v2/case/<id>/rules/<rule_id>."""

    def test_update_rule_toggle_enabled(self, test_case):
        case_id, session, host = test_case

        add_resp = get_api_data(
            session,
            f"{host}/api/v2/case/{case_id}/rules",
            method="POST",
            data=json.dumps({"query": "*:*", "destination": "alerts/all"}),
        )
        rule_id = add_resp["rules"][0]["rule_id"]

        put_resp = get_api_data(
            session,
            f"{host}/api/v2/case/{case_id}/rules/{rule_id}",
            method="PUT",
            data=json.dumps({"enabled": False}),
        )

        updated_rule = next(r for r in put_resp["rules"] if r["rule_id"] == rule_id)
        assert updated_rule["enabled"] is False

    def test_update_rule_change_query(self, test_case):
        case_id, session, host = test_case

        add_resp = get_api_data(
            session,
            f"{host}/api/v2/case/{case_id}/rules",
            method="POST",
            data=json.dumps({"query": "old:query", "destination": "alerts/all"}),
        )
        rule_id = add_resp["rules"][0]["rule_id"]

        put_resp = get_api_data(
            session,
            f"{host}/api/v2/case/{case_id}/rules/{rule_id}",
            method="PUT",
            data=json.dumps({"query": "new:query"}),
        )

        updated_rule = next(r for r in put_resp["rules"] if r["rule_id"] == rule_id)
        assert updated_rule["query"] == "new:query"

    def test_update_rule_not_found_returns_404(self, test_case):
        case_id, session, host = test_case

        resp = get_api_data(
            session,
            f"{host}/api/v2/case/{case_id}/rules/nonexistent",
            method="PUT",
            data=json.dumps({"enabled": False}),
            raw=True,
        )

        assert resp.status_code == 404
