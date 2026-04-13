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
