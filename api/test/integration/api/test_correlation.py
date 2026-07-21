"""Integration tests for the correlation pipeline.

These tests exercise the full path: create case → add rule → ingest hit →
correlate it into the case. They cover both direct processing and the
background worker.
"""

import json
import time

import pytest

from howler.datastore.howler_store import HowlerDatastore
from howler.odm.random_data import wipe_cases, wipe_hits
from howler.services import correlation_service
from test.conftest import get_api_data


def _make_case(title: str = "Correlation Integration Test") -> dict:
    return {
        "title": title,
        "summary": "Integration test case for correlation pipeline.",
    }


def _make_hit(analytic: str = "Test Analytic", kind: str = "alert") -> dict:
    return {
        "howler": {
            "analytic": analytic,
            "detection": "Test Detection",
        },
        "event": {
            "kind": kind,
        },
    }


@pytest.fixture(scope="module")
def datastore(datastore_connection):
    ds: HowlerDatastore = datastore_connection
    try:
        wipe_cases(ds)
        wipe_hits(ds)
        ds.case.commit()
        ds.hit.commit()
        time.sleep(1)
        yield ds
    finally:
        wipe_cases(ds)
        wipe_hits(ds)


@pytest.fixture()
def test_case(datastore: HowlerDatastore, login_session):
    """Create a fresh case via the API."""
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


class TestCorrelationPipeline:
    """End-to-end tests for case rule correlation."""

    def test_matching_hit_added_to_case(self, test_case, datastore: HowlerDatastore):
        """A hit matching a case rule is added to the case at the rendered path."""
        case_id, session, host = test_case

        # Add a rule targeting event.kind:alert
        rule_data = {
            "query": "event.kind:alert",
            "destination": "alerts/{{howler.analytic}}",
        }
        get_api_data(
            session,
            f"{host}/api/v2/case/{case_id}/rules",
            method="POST",
            data=json.dumps(rule_data),
        )
        datastore.case.commit()

        # Ingest a hit that matches the rule
        ingest_resp = get_api_data(
            session,
            f"{host}/api/v2/ingest/hit",
            method="POST",
            data=json.dumps([_make_hit(analytic="My Detection", kind="alert")]),
        )
        hit_id = ingest_resp[0]
        datastore.hit.commit()
        time.sleep(1)

        # Run the correlation directly.  The background worker may have
        # already processed the hit from the ingestion queue, so we
        # cannot assert on the return value — just ensure the call runs.
        correlation_service.process_batch([hit_id])

        # Verify the case now contains the hit (added by process_batch
        # or the background worker — either is acceptable).
        datastore.case.commit()
        case = datastore.case.get(case_id)
        assert case is not None
        hit_values = [item.value for item in case.items if item.type == "hit"]
        assert hit_id in hit_values

        # Verify the path was rendered
        matching_item = next(item for item in case.items if item.value == hit_id)
        alerts_folder = next(item for item in case.items if item.type == "folder" and item.name == "alerts")
        assert matching_item.name == "My Detection"
        assert matching_item.parent == alerts_folder.id

    def test_non_matching_hit_not_added(self, test_case, datastore: HowlerDatastore):
        """A hit that does not match the rule's query is not added."""
        case_id, session, host = test_case

        rule_data = {
            "query": "event.kind:signal",
            "destination": "signals",
        }
        get_api_data(
            session,
            f"{host}/api/v2/case/{case_id}/rules",
            method="POST",
            data=json.dumps(rule_data),
        )
        datastore.case.commit()

        # Ingest a hit with event.kind:alert (does NOT match "signal")
        ingest_resp = get_api_data(
            session,
            f"{host}/api/v2/ingest/hit",
            method="POST",
            data=json.dumps([_make_hit(analytic="Other", kind="alert")]),
        )
        hit_id = ingest_resp[0]
        datastore.hit.commit()
        time.sleep(1)

        added = correlation_service.process_batch([hit_id])

        assert added == 0

        case = datastore.case.get(case_id)
        hit_values = [item.value for item in case.items if item.type == "hit"]
        assert hit_id not in hit_values

    def test_disabled_rule_ignored(self, test_case, datastore: HowlerDatastore):
        """A disabled rule does not trigger correlation."""
        case_id, session, host = test_case

        rule_data = {
            "query": "event.kind:alert",
            "destination": "alerts",
        }
        resp = get_api_data(
            session,
            f"{host}/api/v2/case/{case_id}/rules",
            method="POST",
            data=json.dumps(rule_data),
        )
        rule_id = resp["rules"][-1]["rule_id"]
        datastore.case.commit()

        # Disable the rule
        get_api_data(
            session,
            f"{host}/api/v2/case/{case_id}/rules/{rule_id}",
            method="PUT",
            data=json.dumps({"enabled": False}),
        )
        datastore.case.commit()

        # Ingest a matching hit
        ingest_resp = get_api_data(
            session,
            f"{host}/api/v2/ingest/hit",
            method="POST",
            data=json.dumps([_make_hit(kind="alert")]),
        )
        hit_id = ingest_resp[0]
        datastore.hit.commit()
        time.sleep(1)

        added = correlation_service.process_batch([hit_id])

        assert added == 0

    def test_duplicate_hit_skipped(self, test_case, datastore: HowlerDatastore):
        """Running process_batch twice with the same hit only adds it once."""
        case_id, session, host = test_case

        rule_data = {
            "query": "event.kind:alert",
            "destination": "dup-test",
        }
        get_api_data(
            session,
            f"{host}/api/v2/case/{case_id}/rules",
            method="POST",
            data=json.dumps(rule_data),
        )
        datastore.case.commit()

        ingest_resp = get_api_data(
            session,
            f"{host}/api/v2/ingest/hit",
            method="POST",
            data=json.dumps([_make_hit(kind="alert")]),
        )
        hit_id = ingest_resp[0]
        datastore.hit.commit()
        time.sleep(1)

        # The background worker may have already processed the hit from
        # the ingestion queue, so we cannot rely on exact return values.
        first = correlation_service.process_batch([hit_id])
        second = correlation_service.process_batch([hit_id])

        # At most one of the calls (or the worker) should have added the hit.
        assert first + second <= 1

        # The hit must appear exactly once in the case.
        datastore.case.commit()
        case = datastore.case.get(case_id)
        hit_count = sum(1 for item in case.items if item.type == "hit" and item.value == hit_id)
        assert hit_count == 1


class TestCorrelationWorker:
    """End-to-end tests for the background correlation worker."""

    MAX_WAIT = 30
    POLL_INTERVAL = 0.25

    def _wait_for_case_items(self, datastore: HowlerDatastore, case_id: str, hit_ids: list[str]) -> bool:
        """Wait until every expected hit has been added to the case."""
        deadline = time.monotonic() + self.MAX_WAIT
        expected_hit_ids = set(hit_ids)

        while time.monotonic() < deadline:
            datastore.case.commit()
            case = datastore.case.get(case_id)
            if case is not None:
                actual_hit_ids = {item.value for item in case.items if item.type == "hit"}
                if expected_hit_ids <= actual_hit_ids:
                    return True
            time.sleep(self.POLL_INTERVAL)

        return False

    def _add_rule(self, session, host: str, case_id: str, query: str, destination: str) -> None:
        get_api_data(
            session,
            f"{host}/api/v2/case/{case_id}/rules",
            method="POST",
            data=json.dumps({"query": query, "destination": destination}),
        )

    def test_worker_adds_matching_hit(self, test_case, datastore: HowlerDatastore):
        """The worker adds a newly ingested hit that matches an active rule."""
        case_id, session, host = test_case
        self._add_rule(session, host, case_id, "event.kind:alert", "worker")
        datastore.case.commit()

        ingest_resp = get_api_data(
            session,
            f"{host}/api/v2/ingest/hit",
            method="POST",
            data=json.dumps([_make_hit(kind="alert")]),
        )

        assert self._wait_for_case_items(datastore, case_id, ingest_resp)

    def test_worker_renders_destination_path(self, test_case, datastore: HowlerDatastore):
        """The worker renders the matching hit's destination path."""
        case_id, session, host = test_case
        self._add_rule(session, host, case_id, "event.kind:alert", "worker/{{howler.analytic}}")
        datastore.case.commit()

        ingest_resp = get_api_data(
            session,
            f"{host}/api/v2/ingest/hit",
            method="POST",
            data=json.dumps([_make_hit(analytic="Worker Detection", kind="alert")]),
        )

        assert self._wait_for_case_items(datastore, case_id, ingest_resp)
        case = datastore.case.get(case_id)
        assert case is not None
        matching_item = next(item for item in case.items if item.value == ingest_resp[0])
        worker_folder = next(item for item in case.items if item.type == "folder" and item.name == "worker")
        assert matching_item.name == "Worker Detection"
        assert matching_item.parent == worker_folder.id

    def test_worker_handles_multiple_hits(self, test_case, datastore: HowlerDatastore):
        """Multiple hits ingested in sequence are each processed by the worker."""
        case_id, session, host = test_case
        self._add_rule(session, host, case_id, "event.kind:alert", "worker-multi/{{howler.analytic}}")
        datastore.case.commit()

        hit_ids = []
        for index in range(3):
            ingest_resp = get_api_data(
                session,
                f"{host}/api/v2/ingest/hit",
                method="POST",
                data=json.dumps([_make_hit(analytic=f"Multi-{index}", kind="alert")]),
            )
            hit_ids.append(ingest_resp[0])

        assert self._wait_for_case_items(datastore, case_id, hit_ids), (
            f"Worker did not add all hits {hit_ids} to case {case_id} within {self.MAX_WAIT}s"
        )
