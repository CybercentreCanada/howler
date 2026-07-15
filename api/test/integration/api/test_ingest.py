"""Integration tests for the ingestion API (hits and events).

These tests exercise the full ingest path via the API server:
POST /api/v2/ingest/hit, POST /api/v2/ingest/event, DELETE, validate.
"""

import json
import time

import pytest

from howler.datastore.howler_store import HowlerDatastore
from howler.odm.random_data import wipe_events, wipe_hits
from test.conftest import APIError, get_api_data


@pytest.fixture(scope="module")
def datastore(datastore_connection):
    ds: HowlerDatastore = datastore_connection
    try:
        wipe_hits(ds)
        wipe_events(ds)
        ds.hit.commit()
        ds.event.commit()
        time.sleep(1)
        yield ds
    finally:
        wipe_hits(ds)
        wipe_events(ds)


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


def _make_event() -> dict:
    return {
        "howler": {
            "data": ["raw telemetry entry"],
        },
    }


# ---------------------------------------------------------------------------
# POST /api/v2/ingest/hit — alert ingestion
# ---------------------------------------------------------------------------


class TestIngestHit:
    """Integration tests for alert (hit) ingestion."""

    def test_ingest_single_hit(self, datastore: HowlerDatastore, login_session):
        """A single alert is created and retrievable from the datastore."""
        session, host = login_session

        resp = get_api_data(
            session,
            f"{host}/api/v2/ingest/hit",
            method="POST",
            data=json.dumps([_make_hit()]),
        )

        assert isinstance(resp, list)
        assert len(resp) == 1

        hit_id = resp[0]
        datastore.hit.commit()
        time.sleep(1)

        hit = datastore.hit.get(hit_id, as_obj=False)
        assert hit is not None
        assert hit["howler"]["analytic"] == "Test Analytic"
        assert hit["event"]["kind"] == "alert"

    def test_ingest_multiple_hits(self, datastore: HowlerDatastore, login_session):
        """Multiple alerts are created in a single request."""
        session, host = login_session

        hits = [
            _make_hit(analytic="First Analytic", kind="alert"),
            _make_hit(analytic="Second Analytic", kind="event"),
        ]

        resp = get_api_data(
            session,
            f"{host}/api/v2/ingest/hit",
            method="POST",
            data=json.dumps(hits),
        )

        assert len(resp) == 2

        datastore.hit.commit()
        time.sleep(1)

        for hit_id in resp:
            assert datastore.hit.exists(hit_id)

    def test_ingest_hit_assigns_id_and_hash(self, datastore: HowlerDatastore, login_session):
        """Ingested hits receive auto-generated howler.id and howler.hash."""
        session, host = login_session

        resp = get_api_data(
            session,
            f"{host}/api/v2/ingest/hit",
            method="POST",
            data=json.dumps([_make_hit(analytic="Hash Test")]),
        )

        hit_id = resp[0]
        datastore.hit.commit()
        time.sleep(1)

        hit = datastore.hit.get(hit_id, as_obj=False)
        assert hit["howler"]["id"] == hit_id
        assert hit["howler"]["hash"] is not None
        assert len(hit["howler"]["hash"]) == 64  # SHA256 hex digest

    def test_ingest_hit_sets_event_created(self, datastore: HowlerDatastore, login_session):
        """Ingested hits have event.created populated."""
        session, host = login_session

        resp = get_api_data(
            session,
            f"{host}/api/v2/ingest/hit",
            method="POST",
            data=json.dumps([_make_hit(analytic="Event Created Test")]),
        )

        hit_id = resp[0]
        datastore.hit.commit()
        time.sleep(1)

        hit = datastore.hit.get(hit_id, as_obj=False)
        assert hit["event"]["created"] is not None


# ---------------------------------------------------------------------------
# POST /api/v2/ingest/event — event ingestion
# ---------------------------------------------------------------------------


class TestIngestEvent:
    """Integration tests for event ingestion."""

    def test_ingest_single_event(self, datastore: HowlerDatastore, login_session):
        """A single event is created and retrievable from the datastore."""
        session, host = login_session

        resp = get_api_data(
            session,
            f"{host}/api/v2/ingest/event",
            method="POST",
            data=json.dumps([_make_event()]),
        )

        assert isinstance(resp, list)
        assert len(resp) == 1

        obs_id = resp[0]
        datastore.event.commit()
        time.sleep(1)

        obs = datastore.event.get(obs_id, as_obj=False)
        assert obs is not None
        assert obs["howler"]["id"] == obs_id

    def test_ingest_multiple_events(self, datastore: HowlerDatastore, login_session):
        """Multiple events are created in a single request."""
        session, host = login_session

        events = [_make_event(), _make_event()]

        resp = get_api_data(
            session,
            f"{host}/api/v2/ingest/event",
            method="POST",
            data=json.dumps(events),
        )

        assert len(resp) == 2

        datastore.event.commit()
        time.sleep(1)

        for obs_id in resp:
            assert datastore.event.exists(obs_id)

    def test_ingest_event_assigns_hash(self, datastore: HowlerDatastore, login_session):
        """Ingested events receive an auto-generated hash."""
        session, host = login_session

        resp = get_api_data(
            session,
            f"{host}/api/v2/ingest/event",
            method="POST",
            data=json.dumps([_make_event()]),
        )

        obs_id = resp[0]
        datastore.event.commit()
        time.sleep(1)

        obs = datastore.event.get(obs_id, as_obj=False)
        assert obs["howler"]["hash"] is not None
        assert len(obs["howler"]["hash"]) == 64


# ---------------------------------------------------------------------------
# POST /api/v2/ingest/<index>/validate — validation
# ---------------------------------------------------------------------------


class TestIngestValidate:
    """Integration tests for the validate endpoint."""

    def test_validate_valid_hit(self, login_session):
        """A valid hit record passes validation."""
        session, host = login_session

        resp = get_api_data(
            session,
            f"{host}/api/v2/ingest/hit/validate",
            method="POST",
            data=json.dumps([_make_hit()]),
        )

        assert len(resp["valid"]) == 1
        assert len(resp["invalid"]) == 0

    def test_validate_valid_event(self, login_session):
        """A valid event record passes validation."""
        session, host = login_session

        resp = get_api_data(
            session,
            f"{host}/api/v2/ingest/event/validate",
            method="POST",
            data=json.dumps([_make_event()]),
        )

        assert len(resp["valid"]) == 1
        assert len(resp["invalid"]) == 0

    def test_validate_invalid_hit(self, login_session):
        """An invalid hit record is reported in the 'invalid' list."""
        session, host = login_session

        resp = get_api_data(
            session,
            f"{host}/api/v2/ingest/hit/validate",
            method="POST",
            data=json.dumps([{"howler": {"analytic": "Valid"}, "unknown_field": "bad"}]),
        )

        assert len(resp["invalid"]) == 1

    def test_validate_mixed_records(self, login_session):
        """A batch with valid and invalid records categorizes them correctly."""
        session, host = login_session

        records = [
            _make_hit(),
            {"howler": {"analytic": "OK"}, "unknown_field": "invalid"},
        ]

        resp = get_api_data(
            session,
            f"{host}/api/v2/ingest/hit/validate",
            method="POST",
            data=json.dumps(records),
        )

        assert len(resp["valid"]) == 1
        assert len(resp["invalid"]) == 1


# ---------------------------------------------------------------------------
# DELETE /api/v2/ingest/<indexes> — delete
# ---------------------------------------------------------------------------


class TestIngestDelete:
    """Integration tests for the delete endpoint."""

    def test_delete_hit(self, datastore: HowlerDatastore, login_session):
        """A previously ingested hit is deleted and no longer exists."""
        session, host = login_session

        # Ingest first
        resp = get_api_data(
            session,
            f"{host}/api/v2/ingest/hit",
            method="POST",
            data=json.dumps([_make_hit(analytic="To Be Deleted")]),
        )
        hit_id = resp[0]
        datastore.hit.commit()
        time.sleep(1)

        assert datastore.hit.exists(hit_id)

        # Delete
        get_api_data(
            session,
            f"{host}/api/v2/ingest/hit",
            method="DELETE",
            data=json.dumps([hit_id]),
            raw=True,
        )
        datastore.hit.commit()
        time.sleep(1)

        assert not datastore.hit.exists(hit_id)

    def test_delete_nonexistent_returns_404(self, login_session):
        """Attempting to delete a nonexistent record returns a 404 error."""
        session, host = login_session

        with pytest.raises(APIError):
            get_api_data(
                session,
                f"{host}/api/v2/ingest/hit",
                method="DELETE",
                data=json.dumps(["nonexistent-id"]),
            )
