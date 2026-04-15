"""Cross-branch API contract tests for bundle endpoints.

These tests validate HTTP status codes, response envelope structure,
and common response fields of the bundle API.  They are designed to pass on
**both** the ``develop`` branch (native bundle ODM) and the feature branch
(case-backed compatibility shim), so they intentionally avoid:

* Case-related assertions (``_case_id``, ``howler.related``, case items).
* Deprecation-header assertions (only present on the feature branch).

The ``TestBundleDiscrepancies`` class pins down develop-specific edge-case
behavior.  One test (``howler.bundles`` back-reference) is marked ``xfail``
on the feature branch because the ODM field has been removed.
"""

import json
import time
from uuid import uuid4

import pytest

from howler.datastore.howler_store import HowlerDatastore
from howler.odm.random_data import create_hits, wipe_hits
from test.conftest import get_api_data

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_hit(
    analytic: str = "contract-analytic",
    detection: str = "contract-detection",
) -> dict:
    """Return a minimal hit dict with a unique ID."""
    return {
        "howler": {
            "id": str(uuid4()),
            "analytic": analytic,
            "detection": detection,
            "hash": "ab" * 32,
            "score": "0",
        },
    }


def _post_children(session, host, count: int = 2) -> list[str]:
    """Create *count* standalone child hits via POST /api/v1/hit/ and return their IDs."""
    hits = [_make_hit(analytic=f"child-{i}") for i in range(count)]
    resp = get_api_data(
        session,
        f"{host}/api/v1/hit/",
        method="POST",
        data=json.dumps(hits),
    )
    return [h["howler"]["id"] for h in resp["valid"]]


def _post_bundle(session, host, bundle_data=None, child_ids=None):
    """POST /api/v1/hit/bundle - return the raw ``requests.Response``."""
    if bundle_data is None:
        bundle_data = _make_hit()
    if child_ids is None:
        child_ids = []
    return get_api_data(
        session,
        f"{host}/api/v1/hit/bundle",
        method="POST",
        data=json.dumps({"bundle": bundle_data, "hits": child_ids}),
        raw=True,
    )


def _post_bundle_via_tool(session, host, child_count: int = 2):
    """Submit a bundle + children through the tool API, return raw response."""
    tool_name = "contract-tool"
    field_map = {
        "analytic": ["howler.analytic"],
        "detection": ["howler.detection"],
        "hash": ["howler.hash"],
        "is_bundle": ["howler.is_bundle"],
    }
    bundle_row = {
        "analytic": "tool-analytic",
        "detection": "tool-detection",
        "hash": "cd" * 32,
        "is_bundle": True,
    }
    children = [
        {
            "analytic": f"tool-child-{i}",
            "detection": f"tool-child-det-{i}",
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
        create_hits(ds, hit_count=5)
        ds.hit.commit()
        time.sleep(1)
        yield ds
    finally:
        wipe_hits(ds)


# ---------------------------------------------------------------------------
#  1. POST /api/v1/hit/bundle - response contract
# ---------------------------------------------------------------------------


class TestCreateBundleContract:
    """POST /api/v1/hit/bundle - response shape & status code."""

    def test_status_code_201(self, datastore: HowlerDatastore, login_session):
        session, host = login_session
        children = _post_children(session, host, count=1)
        datastore.hit.commit()
        time.sleep(1)

        resp = _post_bundle(session, host, child_ids=children)
        assert resp.status_code == 201

    def test_envelope_structure(self, datastore: HowlerDatastore, login_session):
        session, host = login_session
        children = _post_children(session, host, count=1)
        datastore.hit.commit()
        time.sleep(1)

        body = _post_bundle(session, host, child_ids=children).json()
        assert "api_response" in body
        assert "api_error_message" in body
        assert "api_status_code" in body

    def test_howler_core_fields(self, datastore: HowlerDatastore, login_session):
        """The response must contain the standard howler hit fields."""
        session, host = login_session
        children = _post_children(session, host, count=1)
        datastore.hit.commit()
        time.sleep(1)

        hit_data = _make_hit(analytic="core-field-test", detection="core-det")
        resp = _post_bundle(session, host, bundle_data=hit_data, child_ids=children)
        howler = resp.json()["api_response"]["howler"]

        assert isinstance(howler["id"], str)
        assert howler["analytic"] == "core-field-test"
        assert howler["detection"] == "core-det"
        assert "hash" in howler
        assert "status" in howler

    def test_is_bundle_true(self, datastore: HowlerDatastore, login_session):
        session, host = login_session
        children = _post_children(session, host, count=1)
        datastore.hit.commit()
        time.sleep(1)

        howler = _post_bundle(session, host, child_ids=children).json()["api_response"]["howler"]
        assert howler["is_bundle"] is True

    def test_hits_list_matches_children(self, datastore: HowlerDatastore, login_session):
        """howler.hits must be a list containing exactly the supplied child IDs."""
        session, host = login_session
        children = _post_children(session, host, count=3)
        datastore.hit.commit()
        time.sleep(1)

        howler = _post_bundle(session, host, child_ids=children).json()["api_response"]["howler"]
        assert isinstance(howler["hits"], list)
        assert set(howler["hits"]) == set(children)

    def test_bundle_size_is_int(self, datastore: HowlerDatastore, login_session):
        """bundle_size must exist and be an integer (exact value may differ)."""
        session, host = login_session
        children = _post_children(session, host, count=2)
        datastore.hit.commit()
        time.sleep(1)

        howler = _post_bundle(session, host, child_ids=children).json()["api_response"]["howler"]
        assert isinstance(howler["bundle_size"], int)

    def test_missing_bundle_key_400(self, datastore: HowlerDatastore, login_session):
        session, host = login_session
        resp = get_api_data(
            session,
            f"{host}/api/v1/hit/bundle",
            method="POST",
            data=json.dumps({"hits": []}),
            raw=True,
        )
        assert resp.status_code == 400

    def test_invalid_body_400(self, datastore: HowlerDatastore, login_session):
        session, host = login_session
        resp = get_api_data(
            session,
            f"{host}/api/v1/hit/bundle",
            method="POST",
            data=json.dumps([1, 2, 3]),
            raw=True,
        )
        assert resp.status_code == 400

    def test_root_hit_persisted(self, datastore: HowlerDatastore, login_session):
        """The root hit must exist in the datastore after creation."""
        session, host = login_session
        children = _post_children(session, host, count=1)
        datastore.hit.commit()
        time.sleep(1)

        howler = _post_bundle(session, host, child_ids=children).json()["api_response"]["howler"]
        datastore.hit.commit()
        assert datastore.hit.exists(howler["id"])


# ---------------------------------------------------------------------------
#  2. PUT /api/v1/hit/bundle/<id> - response contract
# ---------------------------------------------------------------------------


class TestUpdateBundleContract:
    """PUT /api/v1/hit/bundle/<id> - response shape & status code."""

    @pytest.fixture()
    def bundle_id(self, datastore: HowlerDatastore, login_session):
        """Create a bundle with 1 child and return its root hit ID."""
        session, host = login_session
        children = _post_children(session, host, count=1)
        datastore.hit.commit()
        time.sleep(1)

        resp = _post_bundle(session, host, child_ids=children)
        root_id = resp.json()["api_response"]["howler"]["id"]
        datastore.hit.commit()
        time.sleep(1)
        return root_id

    def test_status_code_200(self, datastore: HowlerDatastore, login_session, bundle_id):
        session, host = login_session
        new_ids = _post_children(session, host, count=1)
        datastore.hit.commit()
        time.sleep(1)

        resp = get_api_data(
            session,
            f"{host}/api/v1/hit/bundle/{bundle_id}",
            method="PUT",
            data=json.dumps(new_ids),
            raw=True,
        )
        assert resp.status_code == 200

    def test_response_has_bundle_fields(self, datastore: HowlerDatastore, login_session, bundle_id):
        session, host = login_session
        new_ids = _post_children(session, host, count=1)
        datastore.hit.commit()
        time.sleep(1)

        howler = get_api_data(
            session,
            f"{host}/api/v1/hit/bundle/{bundle_id}",
            method="PUT",
            data=json.dumps(new_ids),
            raw=True,
        ).json()["api_response"]["howler"]

        assert howler["is_bundle"] is True
        assert isinstance(howler["hits"], list)
        # The newly added ID must be in the hits list
        for nid in new_ids:
            assert nid in howler["hits"]

    def test_nonexistent_bundle_error(self, datastore: HowlerDatastore, login_session):
        """Updating a nonexistent bundle returns an error (400 or 404)."""
        session, host = login_session
        resp = get_api_data(
            session,
            f"{host}/api/v1/hit/bundle/does-not-exist",
            method="PUT",
            data=json.dumps(["some-id"]),
            raw=True,
        )
        assert resp.status_code in (400, 404)

    def test_invalid_body_400(self, datastore: HowlerDatastore, login_session, bundle_id):
        """Sending a non-list body to a valid bundle returns 400."""
        session, host = login_session
        resp = get_api_data(
            session,
            f"{host}/api/v1/hit/bundle/{bundle_id}",
            method="PUT",
            data=json.dumps({"not": "a list"}),
            raw=True,
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
#  3. DELETE /api/v1/hit/bundle/<id> - response contract
# ---------------------------------------------------------------------------


class TestRemoveBundleContract:
    """DELETE /api/v1/hit/bundle/<id> - response shape & status code."""

    @pytest.fixture()
    def bundle_with_children(self, datastore: HowlerDatastore, login_session):
        """Create a bundle with 3 children; return (root_id, child_ids)."""
        session, host = login_session
        children = _post_children(session, host, count=3)
        datastore.hit.commit()
        time.sleep(1)

        resp = _post_bundle(session, host, child_ids=children)
        root_id = resp.json()["api_response"]["howler"]["id"]
        datastore.hit.commit()
        time.sleep(1)
        return root_id, children

    def test_remove_specific_status_200(self, datastore: HowlerDatastore, login_session, bundle_with_children):
        session, host = login_session
        root_id, child_ids = bundle_with_children

        resp = get_api_data(
            session,
            f"{host}/api/v1/hit/bundle/{root_id}",
            method="DELETE",
            data=json.dumps(child_ids[:1]),
            raw=True,
        )
        assert resp.status_code == 200

    def test_remove_specific_updates_hits(self, datastore: HowlerDatastore, login_session, bundle_with_children):
        session, host = login_session
        root_id, child_ids = bundle_with_children
        to_remove = child_ids[:1]

        howler = get_api_data(
            session,
            f"{host}/api/v1/hit/bundle/{root_id}",
            method="DELETE",
            data=json.dumps(to_remove),
            raw=True,
        ).json()["api_response"]["howler"]

        assert isinstance(howler["hits"], list)
        assert to_remove[0] not in howler["hits"]
        # The bundle still has children → is_bundle should be True
        assert howler["is_bundle"] is True

    def test_wildcard_remove_status_200(self, datastore: HowlerDatastore, login_session, bundle_with_children):
        session, host = login_session
        root_id, _ = bundle_with_children

        resp = get_api_data(
            session,
            f"{host}/api/v1/hit/bundle/{root_id}",
            method="DELETE",
            data=json.dumps(["*"]),
            raw=True,
        )
        assert resp.status_code == 200

        howler = resp.json()["api_response"]["howler"]
        assert howler["hits"] == []

    def test_nonexistent_bundle_error(self, datastore: HowlerDatastore, login_session):
        session, host = login_session
        resp = get_api_data(
            session,
            f"{host}/api/v1/hit/bundle/does-not-exist",
            method="DELETE",
            data=json.dumps(["some-id"]),
            raw=True,
        )
        assert resp.status_code in (400, 404)

    def test_invalid_body_400(self, datastore: HowlerDatastore, login_session, bundle_with_children):
        """Sending a non-list body to a valid bundle returns 400."""
        session, host = login_session
        root_id, _ = bundle_with_children
        resp = get_api_data(
            session,
            f"{host}/api/v1/hit/bundle/{root_id}",
            method="DELETE",
            data=json.dumps("not a list"),
            raw=True,
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
#  4. Tool API - POST /api/v1/tools/<name>/hits with is_bundle
# ---------------------------------------------------------------------------


class TestToolBundleContract:
    """Tool API batch ingestion with a bundle row."""

    def test_status_code_201(self, datastore: HowlerDatastore, login_session):
        session, host = login_session
        resp = _post_bundle_via_tool(session, host, child_count=2)
        assert resp.status_code == 201

    def test_response_is_list(self, datastore: HowlerDatastore, login_session):
        session, host = login_session
        body = _post_bundle_via_tool(session, host, child_count=2).json()
        assert isinstance(body["api_response"], list)

    def test_entry_shape(self, datastore: HowlerDatastore, login_session):
        """Each entry must have 'id' (str) and 'error' (None on success)."""
        session, host = login_session
        entries = _post_bundle_via_tool(session, host, child_count=2).json()["api_response"]
        assert len(entries) == 3  # 1 bundle + 2 children
        for entry in entries:
            assert "id" in entry
            assert isinstance(entry["id"], str)
            assert "error" in entry
            assert entry["error"] is None

    def test_two_bundles_rejected(self, datastore: HowlerDatastore, login_session):
        """Submitting two bundle rows in one payload must be rejected."""
        session, host = login_session
        field_map = {
            "analytic": ["howler.analytic"],
            "hash": ["howler.hash"],
            "is_bundle": ["howler.is_bundle"],
        }
        payload = {
            "map": field_map,
            "hits": [
                {"analytic": "b1", "hash": "ab" * 32, "is_bundle": True},
                {"analytic": "b2", "hash": "cd" * 32, "is_bundle": True},
            ],
        }
        resp = get_api_data(
            session,
            f"{host}/api/v1/tools/multi-bundle-test/hits",
            method="POST",
            data=json.dumps(payload),
            raw=True,
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
#  5. GET /api/v1/hit/<id> - fetching a bundle root hit
# ---------------------------------------------------------------------------


class TestGetBundleRootContract:
    """Fetching the root hit via the regular GET hit endpoint."""

    def test_root_hit_fetchable(self, datastore: HowlerDatastore, login_session):
        session, host = login_session
        children = _post_children(session, host, count=1)
        datastore.hit.commit()
        time.sleep(1)

        root_id = _post_bundle(session, host, child_ids=children).json()["api_response"]["howler"]["id"]
        datastore.hit.commit()
        time.sleep(1)

        hit = get_api_data(session, f"{host}/api/v1/hit/{root_id}")
        assert hit["howler"]["id"] == root_id
        assert "analytic" in hit["howler"]
        assert "detection" in hit["howler"]
        assert "status" in hit["howler"]


# ---------------------------------------------------------------------------
#  6. End-to-end lifecycle (response-only)
# ---------------------------------------------------------------------------


class TestBundleLifecycleContract:
    """Create → add → remove via API, checking only response shape & status."""

    def test_create_add_remove(self, datastore: HowlerDatastore, login_session):
        session, host = login_session

        # --- Create children and a bundle ---
        initial = _post_children(session, host, count=2)
        datastore.hit.commit()
        time.sleep(1)

        resp = _post_bundle(session, host, child_ids=initial)
        assert resp.status_code == 201

        body = resp.json()["api_response"]
        bundle_id = body["howler"]["id"]
        assert body["howler"]["is_bundle"] is True
        assert set(body["howler"]["hits"]) == set(initial)

        datastore.hit.commit()
        time.sleep(1)

        # --- Add more children ---
        extra = _post_children(session, host, count=2)
        datastore.hit.commit()
        time.sleep(1)

        resp = get_api_data(
            session,
            f"{host}/api/v1/hit/bundle/{bundle_id}",
            method="PUT",
            data=json.dumps(extra),
            raw=True,
        )
        assert resp.status_code == 200

        howler = resp.json()["api_response"]["howler"]
        assert howler["is_bundle"] is True
        all_children = initial + extra
        assert set(howler["hits"]) == set(all_children)

        datastore.hit.commit()
        time.sleep(1)

        # --- Remove one child ---
        to_remove = initial[:1]
        resp = get_api_data(
            session,
            f"{host}/api/v1/hit/bundle/{bundle_id}",
            method="DELETE",
            data=json.dumps(to_remove),
            raw=True,
        )
        assert resp.status_code == 200

        howler = resp.json()["api_response"]["howler"]
        assert to_remove[0] not in howler["hits"]
        remaining = [c for c in all_children if c not in to_remove]
        assert set(howler["hits"]) == set(remaining)


# ---------------------------------------------------------------------------
#  7. Behavioral discrepancies between develop (native ODM) and feature
#     (case-backed shim).  Each test documents the exact divergence so we
#     can align the feature branch to match develop where needed.
# ---------------------------------------------------------------------------


class TestBundleDiscrepancies:
    """Tests that pin down develop-specific behavior.

    On the feature branch some of these behaviors change.  The tests are
    written to pass on *develop* and are expected to need ``xfail`` or
    adjustment on the feature branch.
    """

    # -- POST /hit/bundle with zero children → develop returns 400 ----------

    def test_create_bundle_zero_children_rejected(self, datastore: HowlerDatastore, login_session):
        """develop: creating a bundle with no children returns 400."""
        session, host = login_session
        resp = _post_bundle(session, host, child_ids=[])
        assert resp.status_code == 400

    # -- PUT duplicate child → develop returns 409 conflict -----------------

    def test_put_duplicate_child_returns_conflict(self, datastore: HowlerDatastore, login_session):
        """develop: adding a child that is already in the bundle returns 409."""
        session, host = login_session
        children = _post_children(session, host, count=1)
        datastore.hit.commit()
        time.sleep(1)

        resp = _post_bundle(session, host, child_ids=children)
        assert resp.status_code == 201
        bundle_id = resp.json()["api_response"]["howler"]["id"]
        datastore.hit.commit()
        time.sleep(1)

        resp = get_api_data(
            session,
            f"{host}/api/v1/hit/bundle/{bundle_id}",
            method="PUT",
            data=json.dumps(children),
            raw=True,
        )
        assert resp.status_code == 409

    # -- DELETE on a non-bundle hit → develop returns 400 -------------------

    def test_delete_on_non_bundle_hit_returns_400(self, datastore: HowlerDatastore, login_session):
        """develop: DELETE /hit/bundle/<id> on a regular (non-bundle) hit returns 400."""
        session, host = login_session
        # Create a plain hit (not a bundle)
        plain = _make_hit(analytic="plain-hit")
        resp = get_api_data(
            session,
            f"{host}/api/v1/hit/",
            method="POST",
            data=json.dumps([plain]),
        )
        plain_id = resp["valid"][0]["howler"]["id"]
        datastore.hit.commit()
        time.sleep(1)

        resp = get_api_data(
            session,
            f"{host}/api/v1/hit/bundle/{plain_id}",
            method="DELETE",
            data=json.dumps(["some-child"]),
            raw=True,
        )
        assert resp.status_code == 400

    # -- PUT on nonexistent bundle → develop returns 404 --------------------

    def test_put_nonexistent_bundle_returns_404(self, datastore: HowlerDatastore, login_session):
        """develop: PUT /hit/bundle/<nonexistent> returns 404 (etag lookup fails)."""
        session, host = login_session
        resp = get_api_data(
            session,
            f"{host}/api/v1/hit/bundle/does-not-exist-abc",
            method="PUT",
            data=json.dumps(["some-id"]),
            raw=True,
        )
        assert resp.status_code == 404

    # -- DELETE on nonexistent bundle → develop returns 404 -----------------

    def test_delete_nonexistent_bundle_returns_404(self, datastore: HowlerDatastore, login_session):
        """develop: DELETE /hit/bundle/<nonexistent> returns 404 (etag lookup fails)."""
        session, host = login_session
        resp = get_api_data(
            session,
            f"{host}/api/v1/hit/bundle/does-not-exist-abc",
            method="DELETE",
            data=json.dumps(["some-id"]),
            raw=True,
        )
        assert resp.status_code == 404

    # -- DELETE wildcard sets is_bundle=False on develop --------------------

    def test_wildcard_delete_sets_is_bundle_false(self, datastore: HowlerDatastore, login_session):
        """develop: removing all children with ['*'] sets is_bundle to False."""
        session, host = login_session
        children = _post_children(session, host, count=2)
        datastore.hit.commit()
        time.sleep(1)

        resp = _post_bundle(session, host, child_ids=children)
        bundle_id = resp.json()["api_response"]["howler"]["id"]
        datastore.hit.commit()
        time.sleep(1)

        resp = get_api_data(
            session,
            f"{host}/api/v1/hit/bundle/{bundle_id}",
            method="DELETE",
            data=json.dumps(["*"]),
            raw=True,
        )
        assert resp.status_code == 200
        howler = resp.json()["api_response"]["howler"]
        assert howler["hits"] == []
        assert howler["is_bundle"] is False

    # -- POST with child-is-a-bundle → develop returns 400 -----------------

    def test_create_bundle_child_is_bundle_rejected(self, datastore: HowlerDatastore, login_session):
        """develop: nesting a bundle inside another bundle returns 400."""
        session, host = login_session
        # Create an inner bundle first
        inner_children = _post_children(session, host, count=1)
        datastore.hit.commit()
        time.sleep(1)

        inner_resp = _post_bundle(session, host, child_ids=inner_children)
        assert inner_resp.status_code == 201
        inner_id = inner_resp.json()["api_response"]["howler"]["id"]
        datastore.hit.commit()
        time.sleep(1)

        # Try to create an outer bundle containing the inner bundle
        resp = _post_bundle(session, host, child_ids=[inner_id])
        assert resp.status_code == 400

    # -- PUT child-is-a-bundle → develop returns 400 -----------------------

    def test_put_child_is_bundle_rejected(self, datastore: HowlerDatastore, login_session):
        """develop: adding a bundle as a child via PUT returns 400."""
        session, host = login_session
        # Create a bundle to be the "child"
        child_bundle_children = _post_children(session, host, count=1)
        datastore.hit.commit()
        time.sleep(1)

        child_resp = _post_bundle(session, host, child_ids=child_bundle_children)
        child_bundle_id = child_resp.json()["api_response"]["howler"]["id"]
        datastore.hit.commit()
        time.sleep(1)

        # Create a separate bundle to be the "parent"
        parent_children = _post_children(session, host, count=1)
        datastore.hit.commit()
        time.sleep(1)

        parent_resp = _post_bundle(session, host, child_ids=parent_children)
        parent_id = parent_resp.json()["api_response"]["howler"]["id"]
        datastore.hit.commit()
        time.sleep(1)

        # Try to add the child bundle into the parent bundle
        resp = get_api_data(
            session,
            f"{host}/api/v1/hit/bundle/{parent_id}",
            method="PUT",
            data=json.dumps([child_bundle_id]),
            raw=True,
        )
        assert resp.status_code == 400

    # -- Children get howler.bundles back-reference on develop --------------
    # On the feature branch the howler.bundles field has been removed from
    # the ODM entirely, so children use howler.related (case back-refs)
    # instead.  This test cannot pass on the feature branch.

    @pytest.mark.xfail(
        reason="howler.bundles ODM field removed on feature branch; children use howler.related instead",
        strict=False,
    )
    def test_children_have_bundles_backref(self, datastore: HowlerDatastore, login_session):
        """develop: each child hit has the bundle ID in howler.bundles."""
        session, host = login_session
        children = _post_children(session, host, count=2)
        datastore.hit.commit()
        time.sleep(1)

        resp = _post_bundle(session, host, child_ids=children)
        bundle_id = resp.json()["api_response"]["howler"]["id"]
        datastore.hit.commit()
        time.sleep(1)

        for child_id in children:
            hit = get_api_data(session, f"{host}/api/v1/hit/{child_id}")
            assert bundle_id in hit["howler"]["bundles"]

    # -- PUT on a plain (non-bundle) hit converts it to a bundle on develop --

    def test_put_on_plain_hit_converts_to_bundle(self, datastore: HowlerDatastore, login_session):
        """develop: PUT /hit/bundle/<plain_hit_id> converts a regular hit into a bundle."""
        session, host = login_session
        plain = _make_hit(analytic="convert-me")
        resp = get_api_data(
            session,
            f"{host}/api/v1/hit/",
            method="POST",
            data=json.dumps([plain]),
        )
        plain_id = resp["valid"][0]["howler"]["id"]

        new_children = _post_children(session, host, count=1)
        datastore.hit.commit()
        time.sleep(1)

        resp = get_api_data(
            session,
            f"{host}/api/v1/hit/bundle/{plain_id}",
            method="PUT",
            data=json.dumps(new_children),
            raw=True,
        )
        assert resp.status_code == 200
        howler = resp.json()["api_response"]["howler"]
        assert howler["is_bundle"] is True
        assert set(howler["hits"]) == set(new_children)
