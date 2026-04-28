"""Integration tests for the correlation pipeline.

These tests exercise the full path: create case → add rule → ingest hit →
process_batch → verify case items.  They call ``process_batch`` directly
rather than going through the background worker thread, for determinism.
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
        assert matching_item.path == "alerts/My Detection"

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
    """Tests that rely on the background correlation worker processing hits.

    These tests ingest hits via the API and poll the case until the worker
    thread picks them up, without calling ``process_batch`` directly.
    The test config sets ``batch_size=1`` and ``batch_timeout=1`` so the
    worker flushes quickly.
    """

    MAX_WAIT = 15  # seconds to wait for the worker to process a hit

    def _wait_for_case_item(
        self, datastore: HowlerDatastore, case_id: str, hit_id: str, timeout: int = MAX_WAIT
    ) -> bool:
        """Poll until the hit appears in the case's items or timeout is reached."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            datastore.case.commit()
            case = datastore.case.get(case_id)
            if case is not None:
                hit_values = [item.value for item in case.items if item.type == "hit"]
                if hit_id in hit_values:
                    return True
            time.sleep(0.5)
        return False

    def test_worker_processes_ingested_hit(self, test_case, datastore: HowlerDatastore):
        """A hit ingested via the API is automatically correlated by the worker."""
        case_id, session, host = test_case

        rule_data = {
            "query": "event.kind:alert",
            "destination": "worker-test/{{howler.analytic}}",
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
            data=json.dumps([_make_hit(analytic="WorkerDetection", kind="alert")]),
        )
        hit_id = ingest_resp[0]
        datastore.hit.commit()

        assert self._wait_for_case_item(datastore, case_id, hit_id), (
            f"Worker did not add hit {hit_id} to case {case_id} within {self.MAX_WAIT}s"
        )

        case = datastore.case.get(case_id)
        matching_item = next(item for item in case.items if item.value == hit_id)
        assert matching_item.path == "worker-test/WorkerDetection"

    def test_worker_ignores_non_matching_hit(self, test_case, datastore: HowlerDatastore):
        """A hit that doesn't match any rule is not added by the worker."""
        case_id, session, host = test_case

        rule_data = {
            "query": "event.kind:signal",
            "destination": "worker-no-match",
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
            data=json.dumps([_make_hit(analytic="Nope", kind="alert")]),
        )
        hit_id = ingest_resp[0]
        datastore.hit.commit()

        # Wait long enough for the worker to have processed it
        time.sleep(5)
        datastore.case.commit()

        case = datastore.case.get(case_id)
        hit_values = [item.value for item in case.items if item.type == "hit"]
        assert hit_id not in hit_values

    def test_worker_handles_multiple_hits(self, test_case, datastore: HowlerDatastore):
        """Multiple hits ingested in sequence are each processed by the worker."""
        case_id, session, host = test_case

        rule_data = {
            "query": "event.kind:alert",
            "destination": "worker-multi/{{howler.analytic}}",
        }
        get_api_data(
            session,
            f"{host}/api/v2/case/{case_id}/rules",
            method="POST",
            data=json.dumps(rule_data),
        )
        datastore.case.commit()

        hit_ids = []
        for i in range(3):
            ingest_resp = get_api_data(
                session,
                f"{host}/api/v2/ingest/hit",
                method="POST",
                data=json.dumps([_make_hit(analytic=f"Multi-{i}", kind="alert")]),
            )
            hit_ids.append(ingest_resp[0])

        datastore.hit.commit()

        for hit_id in hit_ids:
            assert self._wait_for_case_item(datastore, case_id, hit_id), (
                f"Worker did not add hit {hit_id} to case {case_id} within {self.MAX_WAIT}s"
            )
