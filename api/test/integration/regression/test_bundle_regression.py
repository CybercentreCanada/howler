"""Regression tests for bundle backward compatibility.

These tests validate that the deprecated bundle API endpoints and the tool-based
bundle ingestion path produce responses that are structurally identical to the
legacy bundle behaviour.  Under the hood, bundles are now backed by cases, but
external callers should not need to know that.
"""

import json
import time
from uuid import uuid4

import pytest

from howler.datastore.howler_store import HowlerDatastore
from howler.odm.random_data import create_hits, wipe_cases, wipe_hits
from test.conftest import get_api_data

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_hit_data(analytic: str = "regression-analytic", detection: str = "regression-detection") -> dict:
    """Return a minimal hit dict suitable for the bundle API."""
    return {
        "howler": {
            "id": str(uuid4()),
            "analytic": analytic,
            "detection": detection,
            "hash": "ab" * 32,
            "score": "0",
        },
    }


def _create_child_hits(session, host, count: int = 3) -> list[str]:
    """Create ``count`` standalone hits via POST /api/v1/hit/ and return their IDs."""
    hits = [_make_hit_data(analytic=f"child-{i}") for i in range(count)]
    resp = get_api_data(
        session,
        f"{host}/api/v1/hit/",
        method="POST",
        data=json.dumps(hits),
    )
    return [h["howler"]["id"] for h in resp["valid"]]


def _create_bundle(session, host, bundle_data: dict | None = None, child_ids: list[str] | None = None):
    """Call POST /api/v1/hit/bundle and return the raw requests.Response."""
    if bundle_data is None:
        bundle_data = _make_hit_data()
    if child_ids is None:
        child_ids = []

    return get_api_data(
        session,
        f"{host}/api/v1/hit/bundle",
        method="POST",
        data=json.dumps({"bundle": bundle_data, "hits": child_ids}),
        raw=True,
    )


def _create_bundle_via_tool(session, host, child_count: int = 2):
    """Submit a bundle + children through the tool API and return the raw response."""
    tool_name = "bundle-regression-tool"
    field_map = {
        "analytic": ["howler.analytic"],
        "detection": ["howler.detection"],
        "hash": ["howler.hash"],
        "is_bundle": ["howler.is_bundle"],
    }

    bundle_row = {
        "analytic": "tool-bundle-analytic",
        "detection": "tool-bundle-detection",
        "hash": "cd" * 32,
        "is_bundle": True,
    }
    children = [
        {
            "analytic": f"tool-child-{i}",
            "detection": f"tool-child-detection-{i}",
            "hash": "ef" * 32,
        }
        for i in range(child_count)
    ]

    return get_api_data(
        session,
        f"{host}/api/v1/tools/{tool_name}/hits",
        method="POST",
        data=json.dumps({"map": field_map, "hits": [bundle_row, *children]}),
        raw=True,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def datastore(datastore_connection: HowlerDatastore):
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


# ---------------------------------------------------------------------------
#  1. POST /api/v1/hit/bundle - create bundle
# ---------------------------------------------------------------------------


class TestCreateBundle:
    """Creating a bundle via POST /api/v1/hit/bundle."""

    def test_create_bundle_returns_201(self, datastore: HowlerDatastore, login_session):
        """The endpoint must return HTTP 201 Created."""
        session, host = login_session
        child_ids = _create_child_hits(session, host, count=1)
        datastore.hit.commit()
        time.sleep(1)
        resp = _create_bundle(session, host, child_ids=child_ids)
        assert resp.status_code == 201

    def test_create_bundle_deprecation_headers(self, datastore: HowlerDatastore, login_session):
        """Deprecation and Sunset headers must be present."""
        session, host = login_session
        child_ids = _create_child_hits(session, host, count=1)
        datastore.hit.commit()
        time.sleep(1)
        resp = _create_bundle(session, host, child_ids=child_ids)
        assert resp.headers.get("Deprecation") == "true"
        assert "2027" in resp.headers.get("Sunset", "")

    def test_create_bundle_response_shape(self, datastore: HowlerDatastore, login_session):
        """Response must include the legacy bundle fields: is_bundle, hits, bundle_size."""
        session, host = login_session
        child_ids = _create_child_hits(session, host, count=2)
        datastore.hit.commit()
        time.sleep(1)

        resp = _create_bundle(session, host, child_ids=child_ids)
        body = resp.json()["api_response"]

        # Legacy fields injected into the synthesized response
        assert body["howler"]["is_bundle"] is True
        assert isinstance(body["howler"]["hits"], list)
        assert body["howler"]["bundle_size"] == len(child_ids)
        assert set(body["howler"]["hits"]) == set(child_ids)

        # Deprecation notice and case back-reference
        assert "_deprecation" in body
        assert "_case_id" in body

    def test_create_bundle_root_hit_persisted(self, datastore: HowlerDatastore, login_session):
        """The root hit must be persisted and retrievable."""
        session, host = login_session
        child_ids = _create_child_hits(session, host, count=1)
        datastore.hit.commit()
        time.sleep(1)
        bundle_data = _make_hit_data(analytic="root-persist-test")
        resp = _create_bundle(session, host, bundle_data=bundle_data, child_ids=child_ids)
        body = resp.json()["api_response"]
        datastore.hit.commit()

        root_id = body["howler"]["id"]
        assert datastore.hit.exists(root_id)

    def test_create_bundle_case_created(self, datastore: HowlerDatastore, login_session):
        """A case must be created and linked to the root hit."""
        session, host = login_session
        child_ids = _create_child_hits(session, host, count=1)
        datastore.hit.commit()
        time.sleep(1)

        resp = _create_bundle(session, host, child_ids=child_ids)
        body = resp.json()["api_response"]
        case_id = body["_case_id"]
        datastore.case.commit()

        case = datastore.case.get(case_id)
        assert case is not None

        # Root hit should be one of the case items
        item_values = [item.value for item in case.items]
        assert body["howler"]["id"] in item_values

        # Child hits should also be items
        for child_id in child_ids:
            assert child_id in item_values

    def test_create_bundle_root_hit_has_related(self, datastore: HowlerDatastore, login_session):
        """The root hit must have the case in howler.related."""
        session, host = login_session
        child_ids = _create_child_hits(session, host, count=1)
        datastore.hit.commit()
        time.sleep(1)
        resp = _create_bundle(session, host, child_ids=child_ids)
        body = resp.json()["api_response"]
        case_id = body["_case_id"]

        datastore.hit.commit()
        root_hit = datastore.hit.get(body["howler"]["id"], as_obj=True)
        assert case_id in root_hit.howler.related

    def test_create_bundle_children_have_related(self, datastore: HowlerDatastore, login_session):
        """Each child hit must have the case in howler.related."""
        session, host = login_session
        child_ids = _create_child_hits(session, host, count=2)
        datastore.hit.commit()
        time.sleep(1)

        resp = _create_bundle(session, host, child_ids=child_ids)
        body = resp.json()["api_response"]
        case_id = body["_case_id"]
        datastore.hit.commit()
        time.sleep(1)

        for child_id in child_ids:
            child = datastore.hit.get(child_id, as_obj=True)
            assert case_id in child.howler.related

    def test_create_bundle_no_children(self, datastore: HowlerDatastore, login_session):
        """Creating a bundle with zero children should return 400."""
        session, host = login_session
        resp = _create_bundle(session, host, child_ids=[])
        assert resp.status_code == 400

    def test_create_bundle_missing_bundle_key(self, datastore: HowlerDatastore, login_session):
        """Omitting the 'bundle' key returns 400."""
        session, host = login_session
        resp = get_api_data(
            session,
            f"{host}/api/v1/hit/bundle",
            method="POST",
            data=json.dumps({"hits": []}),
            raw=True,
        )
        assert resp.status_code == 400

    def test_create_bundle_case_title_format(self, datastore: HowlerDatastore, login_session):
        """The auto-created case should have title '{analytic} - {detection}'."""
        session, host = login_session
        child_ids = _create_child_hits(session, host, count=1)
        datastore.hit.commit()
        time.sleep(1)
        bundle_data = _make_hit_data(analytic="MyAnalytic", detection="MyDetection")
        resp = _create_bundle(session, host, bundle_data=bundle_data, child_ids=child_ids)
        body = resp.json()["api_response"]
        case_id = body["_case_id"]
        datastore.case.commit()

        case = datastore.case.get(case_id)
        assert case.title == "MyAnalytic - MyDetection"


# ---------------------------------------------------------------------------
#  2. PUT /api/v1/hit/bundle/<id> - add hits to bundle
# ---------------------------------------------------------------------------


class TestUpdateBundle:
    """Adding hits to an existing bundle via PUT /api/v1/hit/bundle/<id>."""

    @pytest.fixture()
    def bundle(self, datastore: HowlerDatastore, login_session):
        """Create a bundle with one initial child."""
        session, host = login_session
        child_ids = _create_child_hits(session, host, count=1)
        datastore.hit.commit()
        time.sleep(1)
        resp = _create_bundle(session, host, child_ids=child_ids)
        body = resp.json()["api_response"]
        datastore.hit.commit()
        datastore.case.commit()
        time.sleep(1)
        return body

    def test_add_hits_to_bundle(self, datastore: HowlerDatastore, login_session, bundle):
        """Adding child hits increases bundle_size and lists them in hits."""
        session, host = login_session
        new_ids = _create_child_hits(session, host, count=2)
        datastore.hit.commit()
        time.sleep(1)

        resp = get_api_data(
            session,
            f"{host}/api/v1/hit/bundle/{bundle['howler']['id']}",
            method="PUT",
            data=json.dumps(new_ids),
            raw=True,
        )
        assert resp.status_code == 200

        body = resp.json()["api_response"]
        assert body["howler"]["is_bundle"] is True
        assert body["howler"]["bundle_size"] == 3
        assert set(new_ids).issubset(set(body["howler"]["hits"]))

    def test_add_hits_deprecation_headers(self, datastore: HowlerDatastore, login_session, bundle):
        """PUT bundle endpoint returns deprecation headers."""
        session, host = login_session
        resp = get_api_data(
            session,
            f"{host}/api/v1/hit/bundle/{bundle['howler']['id']}",
            method="PUT",
            data=json.dumps([]),
            raw=True,
        )
        assert resp.headers.get("Deprecation") == "true"

    def test_add_hits_nonexistent_bundle(self, datastore: HowlerDatastore, login_session):
        """Adding to a bundle that doesn't exist returns 404."""
        session, host = login_session
        resp = get_api_data(
            session,
            f"{host}/api/v1/hit/bundle/does-not-exist",
            method="PUT",
            data=json.dumps(["some-id"]),
            raw=True,
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
#  3. DELETE /api/v1/hit/bundle/<id> - remove hits from bundle
# ---------------------------------------------------------------------------


class TestRemoveFromBundle:
    """Removing hits from an existing bundle via DELETE /api/v1/hit/bundle/<id>."""

    @pytest.fixture()
    def bundle_with_children(self, datastore: HowlerDatastore, login_session):
        """Create a bundle with 3 children."""
        session, host = login_session
        child_ids = _create_child_hits(session, host, count=3)
        datastore.hit.commit()
        time.sleep(1)

        resp = _create_bundle(session, host, child_ids=child_ids)
        body = resp.json()["api_response"]
        datastore.hit.commit()
        datastore.case.commit()
        time.sleep(1)
        return body, child_ids

    def test_remove_specific_children(self, datastore: HowlerDatastore, login_session, bundle_with_children):
        """Removing specific children by ID updates the bundle."""
        session, host = login_session
        bundle, child_ids = bundle_with_children
        to_remove = child_ids[:1]
        remaining = child_ids[1:]

        resp = get_api_data(
            session,
            f"{host}/api/v1/hit/bundle/{bundle['howler']['id']}",
            method="DELETE",
            data=json.dumps(to_remove),
            raw=True,
        )
        assert resp.status_code == 200

        body = resp.json()["api_response"]
        assert body["howler"]["is_bundle"] is True
        assert body["howler"]["bundle_size"] == len(remaining)
        assert set(body["howler"]["hits"]) == set(remaining)

    def test_remove_all_with_wildcard(self, datastore: HowlerDatastore, login_session, bundle_with_children):
        """Passing ['*'] removes all children."""
        session, host = login_session
        bundle, _ = bundle_with_children

        resp = get_api_data(
            session,
            f"{host}/api/v1/hit/bundle/{bundle['howler']['id']}",
            method="DELETE",
            data=json.dumps(["*"]),
            raw=True,
        )
        assert resp.status_code == 200

        body = resp.json()["api_response"]
        assert body["howler"]["hits"] == []
        assert body["howler"]["bundle_size"] == 0

    def test_remove_deprecation_headers(self, datastore: HowlerDatastore, login_session, bundle_with_children):
        """DELETE bundle endpoint returns deprecation headers."""
        session, host = login_session
        bundle, _ = bundle_with_children

        resp = get_api_data(
            session,
            f"{host}/api/v1/hit/bundle/{bundle['howler']['id']}",
            method="DELETE",
            data=json.dumps([]),
            raw=True,
        )
        assert resp.headers.get("Deprecation") == "true"

    def test_remove_from_nonexistent_bundle(self, datastore: HowlerDatastore, login_session):
        """Removing from a bundle that doesn't exist returns 404."""
        session, host = login_session
        resp = get_api_data(
            session,
            f"{host}/api/v1/hit/bundle/does-not-exist",
            method="DELETE",
            data=json.dumps(["some-id"]),
            raw=True,
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
#  4. Tool API - batch ingestion with is_bundle flag
# ---------------------------------------------------------------------------


class TestToolBundleIngestion:
    """Bundle creation through the tool API (POST /api/v1/tools/<name>/hits)."""

    def test_tool_bundle_returns_201(self, datastore: HowlerDatastore, login_session):
        """Tool API returns 201 when ingesting a bundle with children."""
        session, host = login_session
        resp = _create_bundle_via_tool(session, host, child_count=2)
        assert resp.status_code == 201

    def test_tool_bundle_creates_case(self, datastore: HowlerDatastore, login_session):
        """A case must be created when a bundle hit is submitted via the tool API."""
        session, host = login_session
        resp = _create_bundle_via_tool(session, host, child_count=2)
        body = resp.json()["api_response"]
        datastore.hit.commit()
        datastore.case.commit()
        time.sleep(1)

        # At least one entry should have a _case_id
        case_ids = [entry.get("_case_id") for entry in body if entry.get("_case_id")]
        assert len(case_ids) > 0

        case = datastore.case.get(case_ids[0])
        assert case is not None
        # The case should have items (root + children)
        assert len(case.items) >= 3  # 1 root + 2 children

    def test_tool_bundle_deprecation_warning(self, datastore: HowlerDatastore, login_session):
        """The tool API response should include a deprecation warning."""
        session, host = login_session
        resp = _create_bundle_via_tool(session, host)
        body = resp.json()

        # Warnings appear as api_warning or similar depending on the wrapper
        warnings = body.get("api_warning", [])
        assert any("deprecated" in w.lower() or "bundle" in w.lower() for w in warnings), (
            f"Expected deprecation warning in response, got: {warnings}"
        )

    def test_tool_bundle_response_entries(self, datastore: HowlerDatastore, login_session):
        """Each hit in the tool response should have id, error, warn keys."""
        session, host = login_session
        resp = _create_bundle_via_tool(session, host, child_count=2)
        body = resp.json()["api_response"]

        # 1 bundle + 2 children = 3 entries
        assert len(body) == 3
        for entry in body:
            assert "id" in entry
            assert "error" in entry
            assert entry["error"] is None
            assert isinstance(entry["id"], str)

    def test_tool_bundle_only_one_bundle_allowed(self, datastore: HowlerDatastore, login_session):
        """Submitting two bundle rows in one request should fail."""
        session, host = login_session
        tool_name = "bundle-multi-test"
        field_map = {
            "analytic": ["howler.analytic"],
            "hash": ["howler.hash"],
            "is_bundle": ["howler.is_bundle"],
        }

        hits_payload = [
            {"analytic": "bundle-1", "hash": "ab" * 32, "is_bundle": True},
            {"analytic": "bundle-2", "hash": "cd" * 32, "is_bundle": True},
        ]

        resp = get_api_data(
            session,
            f"{host}/api/v1/tools/{tool_name}/hits",
            method="POST",
            data=json.dumps({"map": field_map, "hits": hits_payload}),
            raw=True,
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
#  5. Action: add_to_bundle
# ---------------------------------------------------------------------------


class TestAddToBundleAction:
    """The deprecated add_to_bundle action executes through the standard action API."""

    @pytest.fixture()
    def bundle(self, datastore: HowlerDatastore, login_session):
        """Create a bundle to which we will add hits via the action."""
        session, host = login_session
        child_ids = _create_child_hits(session, host, count=1)
        datastore.hit.commit()
        time.sleep(1)
        resp = _create_bundle(session, host, child_ids=child_ids)
        body = resp.json()["api_response"]
        datastore.hit.commit()
        datastore.case.commit()
        time.sleep(1)
        return body

    def _execute_add(self, session, host, query: str, bundle_id: str):
        req = {
            "request_id": str(uuid4()),
            "query": query,
            "operations": [
                {
                    "operation_id": "add_to_bundle",
                    "data_json": json.dumps({"bundle_id": bundle_id}),
                }
            ],
        }
        return get_api_data(
            session,
            f"{host}/api/v1/action/execute",
            method="POST",
            data=json.dumps(req),
        )

    def test_add_to_bundle_success(self, datastore: HowlerDatastore, login_session, bundle):
        session, host = login_session
        child_ids = _create_child_hits(session, host, count=2)
        datastore.hit.commit()
        time.sleep(1)

        query = f"howler.id:({' OR '.join(child_ids)})"
        resp = self._execute_add(session, host, query, bundle["howler"]["id"])

        # Flatten all reports
        all_entries = [entry for report in resp.values() for entry in report]
        outcomes = {e["outcome"] for e in all_entries}
        assert "success" in outcomes

        # Verify the case has new items
        datastore.case.commit()
        time.sleep(1)
        case = datastore.case.get(bundle["_case_id"])
        case_hit_values = {item.value for item in case.items if item.type == "hit"}
        for child_id in child_ids:
            assert child_id in case_hit_values

    def test_add_to_bundle_missing_bundle_id(self, datastore: HowlerDatastore, login_session):
        session, host = login_session
        resp = self._execute_add(session, host, "howler.id:*", "")

        all_entries = [entry for report in resp.values() for entry in report]
        assert all(e["outcome"] == "error" for e in all_entries)

    def test_add_to_bundle_nonexistent_bundle(self, datastore: HowlerDatastore, login_session):
        session, host = login_session
        resp = self._execute_add(session, host, "howler.id:*", "does-not-exist-bundle")

        all_entries = [entry for report in resp.values() for entry in report]
        assert all(e["outcome"] == "error" for e in all_entries)


# ---------------------------------------------------------------------------
#  6. Action: remove_from_bundle
# ---------------------------------------------------------------------------


class TestRemoveFromBundleAction:
    """The deprecated remove_from_bundle action executes through the standard action API."""

    @pytest.fixture()
    def bundle_with_children(self, datastore: HowlerDatastore, login_session):
        """Create a bundle with children so we can test removal."""
        session, host = login_session
        child_ids = _create_child_hits(session, host, count=3)
        datastore.hit.commit()
        time.sleep(1)

        resp = _create_bundle(session, host, child_ids=child_ids)
        body = resp.json()["api_response"]
        datastore.hit.commit()
        datastore.case.commit()
        time.sleep(1)
        return body, child_ids

    def _execute_remove(self, session, host, query: str, bundle_id: str):
        req = {
            "request_id": str(uuid4()),
            "query": query,
            "operations": [
                {
                    "operation_id": "remove_from_bundle",
                    "data_json": json.dumps({"bundle_id": bundle_id}),
                }
            ],
        }
        return get_api_data(
            session,
            f"{host}/api/v1/action/execute",
            method="POST",
            data=json.dumps(req),
        )

    def test_remove_from_bundle_success(self, datastore: HowlerDatastore, login_session, bundle_with_children):
        session, host = login_session
        bundle, child_ids = bundle_with_children
        to_remove = child_ids[:1]

        query = f"howler.id:{to_remove[0]}"
        resp = self._execute_remove(session, host, query, bundle["howler"]["id"])

        all_entries = [entry for report in resp.values() for entry in report]
        outcomes = {e["outcome"] for e in all_entries}
        assert "success" in outcomes

        # Verify child was removed from case
        datastore.case.commit()
        time.sleep(1)
        case = datastore.case.get(bundle["_case_id"])
        case_hit_values = {item.value for item in case.items if item.type == "hit"}
        assert to_remove[0] not in case_hit_values

    def test_remove_from_bundle_missing_bundle_id(self, datastore: HowlerDatastore, login_session):
        session, host = login_session
        resp = self._execute_remove(session, host, "howler.id:*", "")

        all_entries = [entry for report in resp.values() for entry in report]
        assert all(e["outcome"] == "error" for e in all_entries)

    def test_remove_from_bundle_nonexistent_bundle(self, datastore: HowlerDatastore, login_session):
        session, host = login_session
        resp = self._execute_remove(session, host, "howler.id:*", "does-not-exist-bundle")

        all_entries = [entry for report in resp.values() for entry in report]
        assert all(e["outcome"] == "error" for e in all_entries)


# ---------------------------------------------------------------------------
#  7. End-to-end lifecycle: create → add → remove → verify
# ---------------------------------------------------------------------------


class TestBundleLifecycle:
    """Full lifecycle: create a bundle, add children, remove children, verify state."""

    def test_full_lifecycle(self, datastore: HowlerDatastore, login_session):
        session, host = login_session

        # --- Step 1: Create standalone children ---
        initial_children = _create_child_hits(session, host, count=2)
        datastore.hit.commit()
        time.sleep(1)

        # --- Step 2: Create bundle with initial children ---
        resp = _create_bundle(session, host, child_ids=initial_children)
        assert resp.status_code == 201
        body = resp.json()["api_response"]
        bundle_id = body["howler"]["id"]
        case_id = body["_case_id"]

        assert body["howler"]["is_bundle"] is True
        assert body["howler"]["bundle_size"] == 2
        assert set(body["howler"]["hits"]) == set(initial_children)

        datastore.hit.commit()
        datastore.case.commit()
        time.sleep(1)

        # --- Step 3: Add more children via PUT ---
        extra_children = _create_child_hits(session, host, count=2)
        datastore.hit.commit()
        time.sleep(1)

        resp = get_api_data(
            session,
            f"{host}/api/v1/hit/bundle/{bundle_id}",
            method="PUT",
            data=json.dumps(extra_children),
            raw=True,
        )
        assert resp.status_code == 200
        body = resp.json()["api_response"]
        all_children = initial_children + extra_children
        assert body["howler"]["bundle_size"] == 4
        assert set(body["howler"]["hits"]) == set(all_children)

        datastore.hit.commit()
        datastore.case.commit()
        time.sleep(1)

        # --- Step 4: Verify case items ---
        case = datastore.case.get(case_id)
        assert case is not None
        case_hit_values = {item.value for item in case.items if item.type == "hit"}
        # Should contain root + 4 children
        assert bundle_id in case_hit_values
        for child_id in all_children:
            assert child_id in case_hit_values

        # --- Step 5: Remove some children via DELETE ---
        to_remove = initial_children[:1]
        resp = get_api_data(
            session,
            f"{host}/api/v1/hit/bundle/{bundle_id}",
            method="DELETE",
            data=json.dumps(to_remove),
            raw=True,
        )
        assert resp.status_code == 200
        body = resp.json()["api_response"]
        expected_remaining = [c for c in all_children if c not in to_remove]
        assert body["howler"]["bundle_size"] == len(expected_remaining)
        assert set(body["howler"]["hits"]) == set(expected_remaining)

        datastore.case.commit()
        time.sleep(1)

        # Removed child should no longer be in the case
        case = datastore.case.get(case_id)
        case_hit_values = {item.value for item in case.items if item.type == "hit"}
        assert to_remove[0] not in case_hit_values

        # --- Step 6: Remove all remaining with wildcard ---
        resp = get_api_data(
            session,
            f"{host}/api/v1/hit/bundle/{bundle_id}",
            method="DELETE",
            data=json.dumps(["*"]),
            raw=True,
        )
        assert resp.status_code == 200
        body = resp.json()["api_response"]
        assert body["howler"]["bundle_size"] == 0
        assert body["howler"]["hits"] == []

        # Root hit should still exist
        datastore.hit.commit()
        assert datastore.hit.exists(bundle_id)

    def test_bundle_idempotent_add(self, datastore: HowlerDatastore, login_session):
        """Adding the same child twice should not create duplicates."""
        session, host = login_session
        child_ids = _create_child_hits(session, host, count=1)
        datastore.hit.commit()
        time.sleep(1)

        resp = _create_bundle(session, host, child_ids=child_ids)
        body = resp.json()["api_response"]
        bundle_id = body["howler"]["id"]
        datastore.hit.commit()
        datastore.case.commit()
        time.sleep(1)

        # Try adding the same child again — should return 409 conflict
        resp = get_api_data(
            session,
            f"{host}/api/v1/hit/bundle/{bundle_id}",
            method="PUT",
            data=json.dumps(child_ids),
            raw=True,
        )
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
#  8. GET /api/v1/hit/<id> - fetching a bundle root hit
# ---------------------------------------------------------------------------


class TestFetchBundleRootHit:
    """Verify the root hit of a bundle is fetchable via the normal GET hit API."""

    def test_get_bundle_root_via_hit_api(self, datastore: HowlerDatastore, login_session):
        """GET /api/v1/hit/<id> should return the hit, even though it was created as a bundle root."""
        session, host = login_session
        child_ids = _create_child_hits(session, host, count=1)
        datastore.hit.commit()
        time.sleep(1)
        resp = _create_bundle(session, host, child_ids=child_ids)
        body = resp.json()["api_response"]
        root_id = body["howler"]["id"]
        datastore.hit.commit()
        time.sleep(1)

        hit = get_api_data(session, f"{host}/api/v1/hit/{root_id}")
        assert hit["howler"]["id"] == root_id
        # howler.related should contain the case back-reference
        assert len(hit["howler"]["related"]) > 0


# ---------------------------------------------------------------------------
#  9. Edge cases
# ---------------------------------------------------------------------------


class TestBundleEdgeCases:
    """Edge cases and error handling."""

    def test_invalid_data_format_post(self, datastore: HowlerDatastore, login_session):
        """Sending a non-dict body to POST /hit/bundle returns 400."""
        session, host = login_session
        resp = get_api_data(
            session,
            f"{host}/api/v1/hit/bundle",
            method="POST",
            data=json.dumps([1, 2, 3]),
            raw=True,
        )
        assert resp.status_code == 400

    def test_invalid_data_format_put(self, datastore: HowlerDatastore, login_session):
        """Sending a non-list body to PUT /hit/bundle/<id> returns 400."""
        session, host = login_session
        resp = get_api_data(
            session,
            f"{host}/api/v1/hit/bundle/some-id",
            method="PUT",
            data=json.dumps({"not": "a list"}),
            raw=True,
        )
        assert resp.status_code == 400

    def test_invalid_data_format_delete(self, datastore: HowlerDatastore, login_session):
        """Sending a non-list body to DELETE /hit/bundle/<id> returns 400."""
        session, host = login_session
        resp = get_api_data(
            session,
            f"{host}/api/v1/hit/bundle/some-id",
            method="DELETE",
            data=json.dumps("not a list"),
            raw=True,
        )
        assert resp.status_code == 400

    def test_create_bundle_with_nonexistent_child(self, datastore: HowlerDatastore, login_session):
        """Creating a bundle referencing a nonexistent child should still succeed (child is skipped)."""
        session, host = login_session
        resp = _create_bundle(session, host, child_ids=["nonexistent-child-id"])
        # The endpoint should succeed - the nonexistent child is logged and skipped
        assert resp.status_code == 201
        body = resp.json()["api_response"]
        # The nonexistent child was skipped, so no children were added
        assert "nonexistent-child-id" not in body["howler"]["hits"]
        assert body["howler"]["bundle_size"] == 0
