"""Integration tests for classification-based access control (PR #233).

These tests make real HTTP requests against a running Howler API server to verify
that the classification-based access control enforcement works end-to-end.

Key points verified:
  - The 'hit' index now enforces classification-based search filtering.
  - An UNRESTRICTED user cannot find RESTRICTED hits via search.
  - A RESTRICTED user can find hits at or below their classification.
  - Admin users bypass classification filters entirely.
  - Hit objects carry the 'classification' field through the API.

Test users (created by random_data.create_users):
  - admin  -- RESTRICTED classification, admin type (bypasses ACL), key: admin:devkey:admin
  - user   -- RESTRICTED classification, regular user, key: user:devkey:user
  - huey   -- UNRESTRICTED classification, regular user, key: huey:devkey:huey
"""

import base64
import json
import uuid

import pytest
import requests

from howler.config import CLASSIFICATION
from howler.datastore.howler_store import HowlerDatastore
from howler.odm.models.user import User
from howler.security.utils import get_password_hash
from howler.services import user_service
from test.conftest import get_api_data

# The search-filtering tests rely on the server enforcing classification levels.
# When CLASSIFICATION.enforce is False (e.g. default dev / unenforced deployment),
# all hits are indexed at the null level and every user can see every hit, so
# the assertions would be vacuously wrong.  Skip gracefully in that case.
_enforce_only = pytest.mark.skipif(
    not CLASSIFICATION.enforce,
    reason="Classification enforcement is disabled (CLASSIFICATION.enforce=False); "
    "access-control filter tests require enforce=True in the deployment's "
    "classification.yml.",
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def datastore(datastore_connection: HowlerDatastore):
    """Alias for the session-scoped datastore connection."""
    yield datastore_connection


@pytest.fixture(scope="module")
def classified_hits(datastore: HowlerDatastore):
    """Create one UNRESTRICTED and one RESTRICTED hit for classification tests.

    Also ensures test users have their access_control field populated.
    This field is normally built and saved during OAuth login by
    user_service.add_access_control(). Test users authenticate via API key,
    so the server never runs that path for them. Without access_control set,
    the search endpoint receives access_control=None and skips the
    classification filter entirely -- every hit is visible to every user.

    Yields a tuple of (unrestricted_hit_id, restricted_hit_id).
    Cleans up both hits on teardown.
    """
    # Populate access_control for the users exercised by these tests.
    # We read each user record, compute the Lucene filter from their
    # classification, write it back, then commit so the API server sees it.
    for uname in ["huey", "user"]:
        user_doc = datastore.user.get_if_exists(uname, as_obj=False)
        if user_doc:
            user_service.add_access_control(user_doc)
            datastore.user.save(uname, user_doc)
    datastore.user.commit()

    unrestricted_id = str(uuid.uuid4())
    restricted_id = str(uuid.uuid4())

    unrestricted_hit = {
        "howler": {
            "id": unrestricted_id,
            "analytic": "access_control_test_unrestricted",
            "hash": "a" * 64,
        },
        "classification": CLASSIFICATION.UNRESTRICTED,
    }

    restricted_hit = {
        "howler": {
            "id": restricted_id,
            "analytic": "access_control_test_restricted",
            "hash": "b" * 64,
        },
        "classification": CLASSIFICATION.RESTRICTED,
    }

    datastore.hit.save(unrestricted_id, unrestricted_hit)
    datastore.hit.save(restricted_id, restricted_hit)
    datastore.hit.commit()

    yield unrestricted_id, restricted_id

    # Cleanup
    datastore.hit.delete(unrestricted_id)
    datastore.hit.delete(restricted_id)
    datastore.hit.commit()


@pytest.fixture(scope="function")
def admin_session(host):
    """Authenticated session for the 'admin' user (RESTRICTED, admin type).

    Admin bypasses classification access control entirely.
    """
    session = requests.Session()
    session.headers.update({"Authorization": f"Basic {base64.b64encode(b'admin:devkey:admin').decode('utf-8')}"})
    return session, host


@pytest.fixture(scope="function")
def user_session(host):
    """Authenticated session for 'user' (Dwight Schrute, RESTRICTED classification).

    This user has RESTRICTED clearance, so they can see both U and R hits.
    """
    session = requests.Session()
    session.headers.update({"Authorization": f"Basic {base64.b64encode(b'user:devkey:user').decode('utf-8')}"})
    return session, host


@pytest.fixture(scope="function")
def huey_session(host):
    """Authenticated session for 'huey' (UNRESTRICTED classification).

    This user has UNRESTRICTED clearance only -- they should NOT be able to see
    RESTRICTED hits through search.
    """
    session = requests.Session()
    session.headers.update({"Authorization": f"Basic {base64.b64encode(b'huey:devkey:huey').decode('utf-8')}"})
    return session, host


# ===================================================================
# Group E -- Hit classification field presence
# ===================================================================


class TestHitClassificationField:
    """Verify the new 'classification' field is present on Hit records via the API."""

    def test_hit_has_classification_field(self, admin_session, classified_hits):
        """A GET on a specific hit returns the 'classification' field in the response.

        This confirms that the Hit model now exposes classification through the API.
        Note: Direct GET by hit ID does NOT enforce classification-based access control --
        it's the search endpoint that applies the access_control Lucene filter.
        """
        session, host = admin_session
        unrestricted_id, _ = classified_hits

        result = get_api_data(session, f"{host}/api/v1/hit/{unrestricted_id}/")
        assert "classification" in result

    def test_classification_field_preserved_on_hit(self, admin_session, classified_hits):
        """A hit saved with RESTRICTED classification retains that value when retrieved.

        This verifies the classification field round-trips correctly through save and GET.
        """
        session, host = admin_session
        _, restricted_id = classified_hits

        result = get_api_data(session, f"{host}/api/v1/hit/{restricted_id}/")
        assert result["classification"] == CLASSIFICATION.RESTRICTED


# ===================================================================
# Group F -- Search result filtering by classification
# ===================================================================


@_enforce_only
class TestSearchAccessControl:
    """Test that hit search results are filtered based on the user's classification.

    The enforcement path:
      1. user_service.add_access_control() builds a Lucene query string from the
         user's classification, stored in user['access_control'].
      2. The search endpoint checks has_access_control("hit") -> True.
      3. The access_control filter is appended to the Lucene query, limiting results
         to hits whose classification level, groups, and requirements are satisfied.

    Skipped when CLASSIFICATION.enforce is False (see _enforce_only marker above).
    """

    def test_unrestricted_user_search_excludes_restricted_hits(self, huey_session, classified_hits):
        """huey (UNRESTRICTED) searches for the RESTRICTED hit by ID -- should get 0 results.

        The access_control filter limits huey to __access_lvl__:[0 TO 100], which
        excludes RESTRICTED hits (level 200).
        """
        session, host = huey_session
        _, restricted_id = classified_hits

        result = get_api_data(
            session,
            f"{host}/api/v1/search/hit/",
            data=json.dumps({"query": f"howler.id:{restricted_id}"}),
            method="POST",
        )
        assert result["total"] == 0

    def test_unrestricted_user_search_includes_unrestricted_hits(self, huey_session, classified_hits):
        """huey (UNRESTRICTED) searches for the UNRESTRICTED hit by ID -- should get 1 result.

        The hit's classification (UNRESTRICTED, level 100) is within huey's clearance.
        """
        session, host = huey_session
        unrestricted_id, _ = classified_hits

        result = get_api_data(
            session,
            f"{host}/api/v1/search/hit/",
            data=json.dumps({"query": f"howler.id:{unrestricted_id}"}),
            method="POST",
        )
        assert result["total"] == 1

    def test_restricted_user_search_includes_restricted_hits(self, user_session, classified_hits):
        """'user' (RESTRICTED) searches for the RESTRICTED hit by ID -- should get 1 result.

        The user's classification (RESTRICTED, level 200) matches the hit's level.
        """
        session, host = user_session
        _, restricted_id = classified_hits

        result = get_api_data(
            session,
            f"{host}/api/v1/search/hit/",
            data=json.dumps({"query": f"howler.id:{restricted_id}"}),
            method="POST",
        )
        assert result["total"] == 1

    def test_restricted_user_search_includes_unrestricted_hits(self, user_session, classified_hits):
        """'user' (RESTRICTED) searches for the UNRESTRICTED hit by ID -- should get 1 result.

        A user with higher clearance can always access lower-classified hits.
        """
        session, host = user_session
        unrestricted_id, _ = classified_hits

        result = get_api_data(
            session,
            f"{host}/api/v1/search/hit/",
            data=json.dumps({"query": f"howler.id:{unrestricted_id}"}),
            method="POST",
        )
        assert result["total"] == 1

    def test_admin_bypasses_classification_filter(self, admin_session, classified_hits):
        """admin can find the RESTRICTED hit via search -- admin type bypasses ACL.

        Even though admins also have a classification, the search endpoint
        does not apply the access_control filter for admin-type users.
        """
        session, host = admin_session
        _, restricted_id = classified_hits

        result = get_api_data(
            session,
            f"{host}/api/v1/search/hit/",
            data=json.dumps({"query": f"howler.id:{restricted_id}"}),
            method="POST",
        )
        assert result["total"] == 1


# ===================================================================
# Group G -- User whoami classification consistency
# ===================================================================


class TestUserClassification:
    """Verify that user classification is visible and correct via the API."""

    def test_user_whoami_shows_classification(self, huey_session):
        """huey's /whoami endpoint shows UNRESTRICTED classification.

        This confirms the classification field is round-tripped through user
        serialization and API response correctly.
        """
        session, host = huey_session

        result = get_api_data(session, f"{host}/api/v1/user/whoami/")
        assert "classification" in result
        assert result["classification"] == CLASSIFICATION.UNRESTRICTED


# ===================================================================
# Group H -- Group membership access control
# ===================================================================

# Canonical classification strings for the two departments.
# DEPARTMENT 1 uses its solitary display name ("ANY"); DEPARTMENT 2 uses
# the explicit "REL TO" form. normalize_classification ensures we always
# use the canonical normalized form stored in Elasticsearch.
_C12N_D1 = CLASSIFICATION.normalize_classification("RESTRICTED//ANY")
_C12N_D2 = CLASSIFICATION.normalize_classification("RESTRICTED//REL TO DEPARTMENT 2")
_C12N_BOTH = CLASSIFICATION.normalize_classification("RESTRICTED//REL TO DEPARTMENT 1, DEPARTMENT 2")


@pytest.fixture(scope="module")
def group_accounts(datastore: HowlerDatastore):
    """Create two transient users — one with D1 clearance only, one with D2 clearance only.

    Each user gets a single API key so the HTTP session fixtures can authenticate.
    add_access_control() is called before saving so Elasticsearch has the correct
    Lucene access_control filter stored on each user document.

    Yields a dict mapping uname -> plain-text key password.
    Cleans up both user records on teardown.
    """
    d1_uname = "test_grp_d1"
    d2_uname = "test_grp_d2"
    d1_pass = "d1-devkey-secret"
    d2_pass = "d2-devkey-secret"

    for uname, c12n, password in [
        (d1_uname, _C12N_D1, d1_pass),
        (d2_uname, _C12N_D2, d2_pass),
    ]:
        pw_hash = get_password_hash(password)
        user_data = User(
            {
                "name": f"Group Test User ({uname})",
                "email": f"{uname}@example.com",
                "classification": c12n,
                "password": pw_hash,
                "uname": uname,
                "type": ["user"],
                "apikeys": {"devkey": {"acl": ["R", "W"], "password": pw_hash}},
            }
        )
        doc = user_data.as_primitives()
        user_service.add_access_control(doc)
        datastore.user.save(uname, doc)

    datastore.user.commit()

    yield {d1_uname: d1_pass, d2_uname: d2_pass}

    datastore.user.delete(d1_uname)
    datastore.user.delete(d2_uname)
    datastore.user.commit()


@pytest.fixture(scope="module")
def group_hits(datastore: HowlerDatastore):
    """Create three hits differentiated only by group classification.

    - d1_id:   classified as D1 only (RESTRICTED//ANY)
    - d2_id:   classified as D2 only (RESTRICTED//REL TO DEPARTMENT 2)
    - both_id: classified as both D1 and D2 (RESTRICTED//REL TO DEPARTMENT 1, DEPARTMENT 2)

    Yields (d1_id, d2_id, both_id). Cleans up on teardown.
    """
    d1_id = str(uuid.uuid4())
    d2_id = str(uuid.uuid4())
    both_id = str(uuid.uuid4())

    for hit_id, analytic, c12n in [
        (d1_id, "grp_test_d1_only", _C12N_D1),
        (d2_id, "grp_test_d2_only", _C12N_D2),
        (both_id, "grp_test_both_depts", _C12N_BOTH),
    ]:
        datastore.hit.save(
            hit_id,
            {
                "howler": {"id": hit_id, "analytic": analytic, "hash": "d" * 64},
                "classification": c12n,
            },
        )

    datastore.hit.commit()

    yield d1_id, d2_id, both_id

    for hit_id in [d1_id, d2_id, both_id]:
        datastore.hit.delete(hit_id)
    datastore.hit.commit()


@pytest.fixture(scope="function")
def d1_session(host, group_accounts):
    """Authenticated session for the D1-only test user."""
    uname = "test_grp_d1"
    token = base64.b64encode(f"{uname}:devkey:{group_accounts[uname]}".encode()).decode()
    session = requests.Session()
    session.headers.update({"Authorization": f"Basic {token}"})
    return session, host


@pytest.fixture(scope="function")
def d2_session(host, group_accounts):
    """Authenticated session for the D2-only test user."""
    uname = "test_grp_d2"
    token = base64.b64encode(f"{uname}:devkey:{group_accounts[uname]}".encode()).decode()
    session = requests.Session()
    session.headers.update({"Authorization": f"Basic {token}"})
    return session, host


@_enforce_only
class TestGroupMembershipAccessControl:
    """Verify that group-restricted hits are only visible to users who hold the matching group.

    The enforcement path is identical to level-based filtering:
      - Each hit's classification is indexed as __access_grp1__ (short group names).
      - Each user's access_control Lucene filter limits hits to those whose
        __access_grp1__ contains __EMPTY__ (no group required) or one of the
        user's own group short names.

    Parameterised helpers reduce repetition; individual test methods name the
    exact scenario so failures are immediately understandable.
    """

    # ── D1 user ───────────────────────────────────────────────────────────

    def test_d1_user_can_see_d1_hit(self, d1_session, group_hits):
        """D1 user can see a hit classified for D1."""
        session, host = d1_session
        d1_id, _, _ = group_hits
        result = get_api_data(
            session,
            f"{host}/api/v1/search/hit/",
            data=json.dumps({"query": f"howler.id:{d1_id}"}),
            method="POST",
        )
        assert result["total"] == 1

    def test_d1_user_cannot_see_d2_hit(self, d1_session, group_hits):
        """D1 user cannot see a hit classified for D2 only."""
        session, host = d1_session
        _, d2_id, _ = group_hits
        result = get_api_data(
            session,
            f"{host}/api/v1/search/hit/",
            data=json.dumps({"query": f"howler.id:{d2_id}"}),
            method="POST",
        )
        assert result["total"] == 0

    def test_d1_user_can_see_both_depts_hit(self, d1_session, group_hits):
        """D1 user can see a hit classified for both D1 and D2 (D1 membership is sufficient)."""
        session, host = d1_session
        _, _, both_id = group_hits
        result = get_api_data(
            session,
            f"{host}/api/v1/search/hit/",
            data=json.dumps({"query": f"howler.id:{both_id}"}),
            method="POST",
        )
        assert result["total"] == 1

    # ── D2 user ───────────────────────────────────────────────────────────

    def test_d2_user_cannot_see_d1_hit(self, d2_session, group_hits):
        """D2 user cannot see a hit classified for D1 only."""
        session, host = d2_session
        d1_id, _, _ = group_hits
        result = get_api_data(
            session,
            f"{host}/api/v1/search/hit/",
            data=json.dumps({"query": f"howler.id:{d1_id}"}),
            method="POST",
        )
        assert result["total"] == 0

    def test_d2_user_can_see_d2_hit(self, d2_session, group_hits):
        """D2 user can see a hit classified for D2."""
        session, host = d2_session
        _, d2_id, _ = group_hits
        result = get_api_data(
            session,
            f"{host}/api/v1/search/hit/",
            data=json.dumps({"query": f"howler.id:{d2_id}"}),
            method="POST",
        )
        assert result["total"] == 1

    def test_d2_user_can_see_both_depts_hit(self, d2_session, group_hits):
        """D2 user can see a hit classified for both D1 and D2 (D2 membership is sufficient)."""
        session, host = d2_session
        _, _, both_id = group_hits
        result = get_api_data(
            session,
            f"{host}/api/v1/search/hit/",
            data=json.dumps({"query": f"howler.id:{both_id}"}),
            method="POST",
        )
        assert result["total"] == 1

    # ── Admin bypasses group filter ────────────────────────────────────────

    def test_admin_can_see_all_group_hits(self, admin_session, group_hits):
        """admin (admin type) can see all three group-restricted hits."""
        session, host = admin_session
        d1_id, d2_id, both_id = group_hits
        for hit_id in [d1_id, d2_id, both_id]:
            result = get_api_data(
                session,
                f"{host}/api/v1/search/hit/",
                data=json.dumps({"query": f"howler.id:{hit_id}"}),
                method="POST",
            )
            assert result["total"] == 1, f"admin should see hit {hit_id}"


# ===================================================================
# Group I -- Wildcard searches return only classification-matching hits
# ===================================================================

# All hits in this group share the analytic prefix "wildcard_acl_test_" so the
# wildcard query can be scoped to just these records without touching the rest
# of the index.  IDs are fixed at module level so the ID set is deterministic
# for the membership assertions below.
_WC_UNRESTRICTED_ID = str(uuid.uuid4())
_WC_RESTRICTED_ID = str(uuid.uuid4())
_WC_D1_ID = str(uuid.uuid4())
_WC_D2_ID = str(uuid.uuid4())
_WC_BOTH_ID = str(uuid.uuid4())

# Query that matches exactly the five hits created in this group.
_WC_QUERY = "howler.analytic:wildcard_acl_test_*"


@pytest.fixture(scope="module")
def wildcard_hits(datastore: HowlerDatastore):
    """Create five hits with different classification levels and groups.

    analytic prefix "wildcard_acl_test_" allows a single wildcard query to
    address exactly this set without matching unrelated index content.

    Hit IDs and their expected classifications:
      _WC_UNRESTRICTED_ID  -> UNRESTRICTED
      _WC_RESTRICTED_ID    -> RESTRICTED  (plain level, no group/required)
      _WC_D1_ID            -> RESTRICTED//ANY  (D1 only)
      _WC_D2_ID            -> RESTRICTED//REL TO DEPARTMENT 2  (D2 only)
      _WC_BOTH_ID          -> RESTRICTED//REL TO DEPARTMENT 1, DEPARTMENT 2

    Note: CLASSIFICATION.RESTRICTED is RESTRICTED//ADMIN//ANY (requires ADMIN
    marking and D1 group).  We deliberately use a plain "RESTRICTED" string
    here so the hit has no group or required-marking fence.
    """
    _restricted_nogroup = CLASSIFICATION.normalize_classification("RESTRICTED")
    hits = [
        (_WC_UNRESTRICTED_ID, "wildcard_acl_test_unrestricted", CLASSIFICATION.UNRESTRICTED),
        (_WC_RESTRICTED_ID, "wildcard_acl_test_restricted", _restricted_nogroup),
        (_WC_D1_ID, "wildcard_acl_test_d1", _C12N_D1),
        (_WC_D2_ID, "wildcard_acl_test_d2", _C12N_D2),
        (_WC_BOTH_ID, "wildcard_acl_test_both", _C12N_BOTH),
    ]
    for hit_id, analytic, c12n in hits:
        datastore.hit.save(
            hit_id,
            {
                "howler": {"id": hit_id, "analytic": analytic, "hash": "e" * 64},
                "classification": c12n,
            },
        )
    datastore.hit.commit()

    yield

    for hit_id, _, _ in hits:
        datastore.hit.delete(hit_id)
    datastore.hit.commit()


def _search_ids(session, host: str, query: str) -> set[str]:
    """Return the set of howler.id values from a search, fetching up to 25 rows."""
    result = get_api_data(
        session,
        f"{host}/api/v1/search/hit/",
        data=json.dumps({"query": query, "rows": 25, "fl": "howler.id"}),
        method="POST",
    )
    return {item["howler"]["id"] for item in result["items"]}


@_enforce_only
class TestWildcardSearchFiltering:
    """Wildcard queries must still honour classification access control.

    All tests use _WC_QUERY ("howler.analytic:wildcard_acl_test_*") to address
    only the five hits created by the wildcard_hits fixture, then assert on the
    exact set of IDs returned rather than bare counts.
    """

    def test_huey_wildcard_returns_only_unrestricted(self, huey_session, wildcard_hits):
        """huey (UNRESTRICTED, no group) sees only the UNRESTRICTED hit.

        RESTRICTED hits (_WC_RESTRICTED_ID, _WC_D1_ID, _WC_D2_ID, _WC_BOTH_ID)
        are all at level 200 which exceeds huey's clearance of 100.
        """
        session, host = huey_session
        ids = _search_ids(session, host, _WC_QUERY)
        assert ids == {_WC_UNRESTRICTED_ID}

    def test_user_wildcard_returns_unrestricted_restricted_d1_and_both(self, user_session, wildcard_hits):
        """'user' (CLASSIFICATION.RESTRICTED = RESTRICTED//ADMIN//ANY) sees four hits.

        CLASSIFICATION.RESTRICTED normalises to RESTRICTED//ADMIN//ANY, giving 'user':
          - Level RESTRICTED (200)
          - Required marking ADMIN
          - Group D1 (via the solitary display name ANY)

        Visible hits:
          _WC_UNRESTRICTED_ID -- level 100, no fences
          _WC_RESTRICTED_ID   -- plain RESTRICTED, no group/required fence
          _WC_D1_ID           -- RESTRICTED//ANY: user has D1 ✓
          _WC_BOTH_ID         -- RESTRICTED//D1+D2: D1 membership is sufficient ✓

        _WC_D2_ID (D2-only) is NOT visible because user holds D1, not D2.
        """
        session, host = user_session
        ids = _search_ids(session, host, _WC_QUERY)
        assert ids == {_WC_UNRESTRICTED_ID, _WC_RESTRICTED_ID, _WC_D1_ID, _WC_BOTH_ID}

    def test_d1_user_wildcard_returns_d1_and_both_not_d2(self, d1_session, wildcard_hits, group_accounts):
        """D1 user sees UNRESTRICTED, RESTRICTED (no group), D1-only, and both-dept hits.

        The D2-only hit (_WC_D2_ID) must NOT appear because the user holds D1, not D2.
        """
        session, host = d1_session
        ids = _search_ids(session, host, _WC_QUERY)
        assert _WC_UNRESTRICTED_ID in ids
        assert _WC_RESTRICTED_ID in ids
        assert _WC_D1_ID in ids
        assert _WC_BOTH_ID in ids
        assert _WC_D2_ID not in ids

    def test_d2_user_wildcard_returns_d2_and_both_not_d1(self, d2_session, wildcard_hits, group_accounts):
        """D2 user sees UNRESTRICTED, RESTRICTED (no group), D2-only, and both-dept hits.

        The D1-only hit (_WC_D1_ID) must NOT appear because the user holds D2, not D1.
        """
        session, host = d2_session
        ids = _search_ids(session, host, _WC_QUERY)
        assert _WC_UNRESTRICTED_ID in ids
        assert _WC_RESTRICTED_ID in ids
        assert _WC_D2_ID in ids
        assert _WC_BOTH_ID in ids
        assert _WC_D1_ID not in ids

    def test_admin_wildcard_returns_all_five(self, admin_session, wildcard_hits):
        """admin sees all five hits regardless of classification or group.

        Admin type bypasses the access_control Lucene filter entirely.
        """
        session, host = admin_session
        ids = _search_ids(session, host, _WC_QUERY)
        assert ids == {
            _WC_UNRESTRICTED_ID,
            _WC_RESTRICTED_ID,
            _WC_D1_ID,
            _WC_D2_ID,
            _WC_BOTH_ID,
        }
