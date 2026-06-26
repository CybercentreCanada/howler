"""Integration tests for POST /api/v2/fuzzy/search.

Seeds the datastore with random hits, then exercises the fuzzy endpoint
to confirm results are returned and match expected records.
"""

import json

import pytest

from howler.datastore.howler_store import HowlerDatastore
from howler.odm.random_data import create_hits, wipe_hits
from test.conftest import APIError, get_api_data

HIT_COUNT = 15


@pytest.fixture(scope="module")
def datastore(datastore_connection):
    ds: HowlerDatastore = datastore_connection
    try:
        create_hits(ds, hit_count=HIT_COUNT)
        yield ds
    finally:
        wipe_hits(ds)


def _fuzzy_post(session, host, body: dict) -> dict:
    return get_api_data(
        session,
        f"{host}/api/v2/fuzzy/search",
        method="POST",
        data=json.dumps(body),
    )


class TestFuzzySearchBasic:
    """Basic functionality tests for the fuzzy search endpoint."""

    def test_search_returns_results(self, datastore: HowlerDatastore, login_session):
        """A broad wildcard-like query should return hits from the seeded data."""
        session, host = login_session

        # Grab a known hit from the datastore to use as a search target
        hits = datastore.hit.search("howler.id:*", rows=1, as_obj=False)["items"]
        assert len(hits) > 0
        target_hit = hits[0]
        threat = target_hit["howler"]["outline"]["threat"]

        result = _fuzzy_post(session, host, {"query": threat, "indexes": ["hit"]})

        assert result["total"] >= 1
        assert result["offset"] == 0
        assert len(result["items"]) >= 1

        # The matching hit should appear in the results
        ids_found = [item["howler"]["id"] for item in result["items"]]
        assert target_hit["howler"]["id"] in ids_found

    def test_search_by_hit_id(self, datastore: HowlerDatastore, login_session):
        """Searching by an exact howler.id should return that hit."""
        session, host = login_session

        hits = datastore.hit.search("howler.id:*", rows=1, as_obj=False)["items"]
        assert len(hits) > 0
        hit_id = hits[0]["howler"]["id"]

        result = _fuzzy_post(session, host, {"query": hit_id, "indexes": ["hit"]})

        assert result["total"] >= 1
        ids_found = [item["howler"]["id"] for item in result["items"]]
        assert hit_id in ids_found

    def test_search_across_multiple_indexes(self, datastore: HowlerDatastore, login_session):
        """Searching across hit and event should return results with __index set."""
        session, host = login_session

        hits = datastore.hit.search("howler.id:*", rows=1, as_obj=False)["items"]
        assert len(hits) > 0
        threat = hits[0]["howler"]["outline"]["threat"]

        result = _fuzzy_post(session, host, {"query": threat, "indexes": ["hit", "event"]})

        assert result["total"] >= 1
        # All items should have an __index field
        for item in result["items"]:
            assert "__index" in item
            assert item["__index"] in ("hit", "event")

    def test_search_results_have_score(self, datastore: HowlerDatastore, login_session):
        """All results should include a _score field."""
        session, host = login_session

        hits = datastore.hit.search("howler.id:*", rows=1, as_obj=False)["items"]
        hit_id = hits[0]["howler"]["id"]

        result = _fuzzy_post(session, host, {"query": hit_id, "indexes": ["hit"]})

        assert result["total"] >= 1
        for item in result["items"]:
            assert "_score" in item
            assert isinstance(item["_score"], (int, float))
            assert item["_score"] > 0


class TestFuzzySearchPagination:
    """Tests for pagination parameters."""

    def test_rows_limits_results(self, datastore: HowlerDatastore, login_session):
        """Setting rows should limit the number of returned items."""
        session, host = login_session

        hits = datastore.hit.search("howler.id:*", rows=1, as_obj=False)["items"]
        threat = hits[0]["howler"]["outline"]["threat"]

        result = _fuzzy_post(session, host, {"query": threat, "indexes": ["hit"], "rows": 2})

        assert result["rows"] <= 2

    def test_offset_skips_results(self, datastore: HowlerDatastore, login_session):
        """Setting offset should skip leading results."""
        session, host = login_session

        hits = datastore.hit.search("howler.id:*", rows=1, as_obj=False)["items"]
        threat = hits[0]["howler"]["outline"]["threat"]

        result_full = _fuzzy_post(session, host, {"query": threat, "indexes": ["hit"], "rows": 100})

        if result_full["total"] > 1:
            result_offset = _fuzzy_post(session, host, {"query": threat, "indexes": ["hit"], "rows": 100, "offset": 1})
            assert result_offset["offset"] == 1
            # Offset result should have one fewer item (or same if more pages exist)
            assert result_offset["total"] == result_full["total"]


class TestFuzzySearchValidation:
    """Tests for input validation and error handling."""

    def test_empty_query_returns_error(self, datastore: HowlerDatastore, login_session):
        """An empty query should return a 400 error."""
        session, host = login_session

        with pytest.raises(APIError) as exc_info:
            _fuzzy_post(session, host, {"query": "", "indexes": ["hit"]})

        assert "400" in str(exc_info.value)

    def test_missing_query_returns_error(self, datastore: HowlerDatastore, login_session):
        """A missing 'query' field should return a 400 error."""
        session, host = login_session

        with pytest.raises(APIError) as exc_info:
            _fuzzy_post(session, host, {"indexes": ["hit"]})

        assert "400" in str(exc_info.value)

    def test_invalid_index_returns_error(self, datastore: HowlerDatastore, login_session):
        """An invalid index name should return a 400 error."""
        session, host = login_session

        with pytest.raises(APIError) as exc_info:
            _fuzzy_post(session, host, {"query": "test", "indexes": ["invalid_index"]})

        assert "400" in str(exc_info.value)

    def test_missing_body_returns_error(self, datastore: HowlerDatastore, login_session):
        """A request with no body should return a 400 error."""
        session, host = login_session

        with pytest.raises(APIError) as exc_info:
            get_api_data(
                session,
                f"{host}/api/v2/fuzzy/search",
                method="POST",
                data=None,
                headers={"content-type": "application/json"},
            )

        assert "400" in str(exc_info.value)


class TestFuzzySearchFilters:
    """Tests for filter functionality."""

    def test_filter_narrows_results(self, datastore: HowlerDatastore, login_session):
        """Applying a filter should narrow the result set."""
        session, host = login_session

        hits = datastore.hit.search("howler.id:*", rows=1, as_obj=False)["items"]
        threat = hits[0]["howler"]["outline"]["threat"]
        hit_id = hits[0]["howler"]["id"]

        # Search without filter
        result_unfiltered = _fuzzy_post(session, host, {"query": threat, "indexes": ["hit"]})

        # Search with filter that matches only our specific hit
        result_filtered = _fuzzy_post(
            session,
            host,
            {"query": threat, "indexes": ["hit"], "filters": [f"howler.id:{hit_id}"]},
        )

        assert result_filtered["total"] >= 1
        assert result_filtered["total"] <= result_unfiltered["total"]
        # The filtered result should contain the specific hit
        ids_found = [item["howler"]["id"] for item in result_filtered["items"]]
        assert hit_id in ids_found

    def test_indexes_as_string(self, datastore: HowlerDatastore, login_session):
        """Indexes passed as a comma-separated string should work."""
        session, host = login_session

        hits = datastore.hit.search("howler.id:*", rows=1, as_obj=False)["items"]
        hit_id = hits[0]["howler"]["id"]

        result = _fuzzy_post(session, host, {"query": hit_id, "indexes": "hit,event"})

        assert result["total"] >= 1
