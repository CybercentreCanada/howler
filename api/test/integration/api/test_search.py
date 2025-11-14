import json
from typing import cast

import pytest
from conftest import APIError, get_api_data

from howler.datastore.howler_store import HowlerDatastore
from howler.odm.models.hit import Hit
from howler.odm.random_data import (
    create_hits,
    create_overviews,
    create_templates,
    create_users,
    wipe_hits,
    wipe_overviews,
    wipe_templates,
    wipe_users,
)

TEST_SIZE = 10
collections = ["user"]


@pytest.fixture(scope="module")
def datastore(datastore_connection):
    ds = datastore_connection
    try:
        u = ds.user.get("user")
        for x in range(TEST_SIZE - 2):
            u.name = f"TEST_{x}"
            ds.user.save(u.name, u)
        ds.user.commit()

        create_hits(datastore_connection, hit_count=15)
        create_templates(datastore_connection)
        create_overviews(datastore_connection)

        yield ds
    finally:
        wipe_hits(datastore_connection)
        wipe_users(ds)
        wipe_templates(ds)
        wipe_overviews(ds)
        create_users(ds)


def test_deep_search(datastore, login_session):
    session, host = login_session

    params = {"query": "id:*", "rows": 5}
    for collection in collections:
        params["deep_paging_id"] = "*"
        res = []
        while True:
            resp = get_api_data(session, f"{host}/api/v1/search/{collection}/", params=params)
            res.extend(resp["items"])
            if len(resp["items"]) == 0 or "next_deep_paging_id" not in resp:
                break
            params["deep_paging_id"] = resp["next_deep_paging_id"]
        assert len(res) >= TEST_SIZE


def test_facet_search(datastore, login_session):
    session, host = login_session

    for collection in collections:
        resp = get_api_data(session, f"{host}/api/v1/search/facet/{collection}/name/")
        assert len(resp) == TEST_SIZE
        for v in resp.values():
            assert isinstance(v, int)

        resp = get_api_data(
            session, f"{host}/api/v1/search/facet/{collection}", method="POST", data=json.dumps({"fields": ["name"]})
        )
        assert len(resp) == 1
        assert len(resp["name"]) == TEST_SIZE
        for v in resp["name"].values():
            assert isinstance(v, int)


def test_grouped_search(datastore, login_session):
    session, host = login_session

    for collection in collections:
        resp = get_api_data(session, f"{host}/api/v1/search/grouped/{collection}/name/")
        assert resp["total"] >= TEST_SIZE
        for v in resp["items"]:
            assert v["total"] == 1 and "value" in v


def test_histogram_search(datastore, login_session):
    session, host = login_session

    # TODO: Data histogram can't be tested until we have an index witha date
    date_hist_map: dict[str, str] = {}

    for collection in collections:
        hist_field = date_hist_map.get(collection, None)
        if not hist_field:
            continue

        resp = get_api_data(session, f"{host}/api/v1/search/histogram/{collection}/{hist_field}/")
        for k, v in resp.items():
            assert k.startswith("2") and k.endswith("Z") and isinstance(v, int)

    int_hist_map = {"user": "api_quota"}

    for collection in collections:
        hist_field = int_hist_map.get(collection, "archive_ts")
        if not hist_field:
            continue

        resp = get_api_data(session, f"{host}/api/v1/search/histogram/{collection}/{hist_field}/")
        for k, v in resp.items():
            assert isinstance(int(k), int) and isinstance(v, int)


def test_search(datastore, login_session):
    session, host = login_session

    for collection in collections:
        resp = get_api_data(session, f"{host}/api/v1/search/{collection}/", params={"query": "id:*"})
        assert TEST_SIZE <= resp["total"] >= len(resp["items"])


def test_get_fields(datastore, login_session):
    session, host = login_session

    for collection in collections:
        resp = get_api_data(session, f"{host}/api/v1/search/fields/{collection}/")
        for v in resp.values():
            assert sorted(list(v.keys())) == sorted(
                [
                    "default",
                    "indexed",
                    "list",
                    "stored",
                    "type",
                    "description",
                    "deprecated",
                    "deprecated_description",
                    "regex",
                    "values",
                ]
            )


def test_count(datastore, login_session):
    session, host = login_session

    for collection in collections:
        search_resp = get_api_data(session, f"{host}/api/v1/search/{collection}/", params={"query": "id:*"})
        count_resp = get_api_data(
            session,
            f"{host}/api/v1/search/count/{collection}/",
            params={"query": "id:*"},
        )
        assert search_resp["total"] == count_resp["count"]


def test_stats_search(datastore, login_session):
    session, host = login_session

    int_map = {"user": "api_quota"}

    for collection in collections:
        field = int_map.get(collection, False)
        if not field:
            continue

        resp = get_api_data(session, f"{host}/api/v1/search/stats/{collection}/{field}/")
        assert sorted(list(resp.keys())) == ["avg", "count", "max", "min", "sum"]
        for v in resp.values():
            assert isinstance(v, int) or isinstance(v, float)


def test_search_fail(datastore, login_session):
    session, host = login_session

    urls = [
        "api/v1/search/stats/hit/howler.score",
        "api/v1/search/histogram/hit/howler.score",
        "api/v1/search/facet/hit/howler.status",
        "api/v1/search/count/hit",
        "api/v1/search/grouped/hit/howler.status",
        "api/v1/search/hit",
    ]

    for url in urls:
        with pytest.raises(APIError) as api_err:
            get_api_data(
                session,
                f"{host}/{url}",
                params={"query": "--1123!@#21123!@#9sfg8d76dfvhjkln543"},
            )

        assert "400" in str(api_err)


def test_hit_analytic_search(datastore: HowlerDatastore, login_session):
    case_sensitive_total = datastore.hit.search('howler.analytic:"Password Checker"')["total"]

    case_insensitive_total_1 = datastore.hit.search('howler.analytic:"password checker"')["total"]
    assert case_sensitive_total == case_insensitive_total_1

    case_insensitive_total_2 = datastore.hit.search('howler.analytic:"PaSsWoRd ChEcKeR"')["total"]
    assert case_sensitive_total == case_insensitive_total_2


def test_hit_detection_search(datastore: HowlerDatastore, login_session):
    example_hit: Hit = datastore.hit.search("_exists_:howler.detection", rows=1, as_obj=True)["items"][0]
    detection = cast(str, example_hit.howler.detection)

    case_sensitive_total = datastore.hit.search(f'howler.detection:"{detection}"')["total"]

    case_insensitive_total_1 = datastore.hit.search(f'howler.detection:"{detection.lower()}"')["total"]
    assert case_sensitive_total == case_insensitive_total_1

    silly_detection = ""
    for i in range(len(detection)):
        if float(int(i / 2)) == i / 2:
            silly_detection += detection[i].upper()
        else:
            silly_detection += detection[i].lower()

    case_insensitive_total_2 = datastore.hit.search(f'howler.detection:"{silly_detection}"')["total"]
    assert case_sensitive_total == case_insensitive_total_2


def test_hit_search_with_metadata(datastore: HowlerDatastore, login_session):
    session, host = login_session

    # Test search without metadata first
    resp_without_metadata = get_api_data(session, f"{host}/api/v1/search/hit/", params={"query": "id:*", "rows": 5})

    # Ensure we have some hits to work with
    assert resp_without_metadata["total"] > 0
    assert len(resp_without_metadata["items"]) > 0

    # Verify no metadata fields are present initially
    for item in resp_without_metadata["items"]:
        assert "__template" not in item
        assert "__overview" not in item
        assert "__dossiers" not in item
        assert "__analytic" not in item

    # Test search with metadata using GET request
    resp_with_metadata_get = get_api_data(
        session,
        f"{host}/api/v1/search/hit/",
        params={"query": "id:*", "rows": 5, "metadata": ["template", "overview", "dossiers", "analytic"]},
    )

    # Should have same number of results
    assert resp_with_metadata_get["total"] == resp_without_metadata["total"]
    assert len(resp_with_metadata_get["items"]) == len(resp_without_metadata["items"])

    # Verify metadata fields are present
    for item in resp_with_metadata_get["items"]:
        assert "__template" in item
        assert "__overview" in item
        assert "__dossiers" in item
        assert "__analytic" in item

        if item["howler"]["analytic"] in ["Password Checker", "Bad Guy Finder"]:
            assert item["__template"]["analytic"] == item["howler"]["analytic"]
            assert item["__overview"]["analytic"] == item["howler"]["analytic"]

        assert isinstance(item["__dossiers"], list)

        # Verify analytic metadata structure
        if item["__analytic"]:
            assert isinstance(item["__analytic"], dict)
            assert "name" in item["__analytic"]
            assert item["__analytic"]["name"] == item["howler"]["analytic"]
            assert "analytic_id" in item["__analytic"]
        # __analytic can be None if no matching analytic record exists

    # Test search with metadata using POST request
    resp_with_metadata_post = get_api_data(
        session,
        f"{host}/api/v1/search/hit/",
        method="POST",
        data=json.dumps({"query": "id:*", "rows": 5, "metadata": ["template", "overview", "analytic"]}),
    )

    # Should have same number of results as other requests
    assert resp_with_metadata_post["total"] == resp_without_metadata["total"]
    assert len(resp_with_metadata_post["items"]) == len(resp_without_metadata["items"])

    # Verify metadata fields are present
    for item in resp_with_metadata_post["items"]:
        assert "__template" in item
        assert "__overview" in item
        assert "__analytic" in item
        assert "__dossiers" not in item

        # Verify analytic metadata structure for POST request
        if item["__analytic"]:
            assert isinstance(item["__analytic"], dict)
            assert "name" in item["__analytic"]
            assert item["__analytic"]["name"] == item["howler"]["analytic"]

    # Test that metadata is only added for hit index
    # First ensure user collection works normally without metadata
    resp_user = get_api_data(
        session, f"{host}/api/v1/search/user/", params={"query": "id:*", "rows": 5, "metadata": ["template"]}
    )

    # User search should work but metadata should be ignored (no error)
    assert resp_user["total"] >= 0
    if resp_user["items"]:
        for item in resp_user["items"]:
            assert "__template" not in item
            assert "__overview" not in item
            assert "__dossiers" not in item
            assert "__analytic" not in item


def test_explain_query_get(datastore, login_session):
    """Test explain query functionality using GET request"""
    session, host = login_session

    # Test basic query explanation with GET request
    resp = get_api_data(session, f"{host}/api/v1/search/hit/explain", params={"query": "id:*"})

    # Basic structure validation - Elasticsearch validate_query response
    assert isinstance(resp, dict)
    assert "valid" in resp
    assert resp["valid"] is True

    assert "_shards" not in resp

    for explanation in resp["explanations"]:
        assert "index" not in explanation

    # TODO: Add more specific validation for Elasticsearch validation response structure
    # The exact structure depends on Elasticsearch version and configuration

    # Test with a more complex Lucene query
    resp_complex = get_api_data(
        session,
        f"{host}/api/v1/search/hit/explain",
        params={"query": 'howler.analytic:"Password Checker" AND howler.status:open'},
    )

    assert isinstance(resp_complex, dict)
    assert "valid" in resp_complex
    assert resp_complex["valid"] is True

    # Test with field-specific query
    resp_field = get_api_data(
        session, f"{host}/api/v1/search/hit/explain", params={"query": "howler.score:[50 TO 100]"}
    )

    assert isinstance(resp_field, dict)
    assert "valid" in resp_field
    assert resp_field["valid"] is True


def test_explain_query_post(datastore, login_session):
    """Test explain query functionality using POST request"""
    session, host = login_session

    # Test basic query explanation with POST request
    resp = get_api_data(session, f"{host}/api/v1/search/hit/explain", method="POST", data=json.dumps({"query": "id:*"}))

    assert isinstance(resp, dict)
    assert "valid" in resp
    assert resp["valid"] is True

    # Test with quoted phrases (tests Lucene phrase escaping)
    resp_phrase = get_api_data(
        session,
        f"{host}/api/v1/search/hit/explain",
        method="POST",
        data=json.dumps({"query": 'howler.analytic:"Example Analytic"'}),
    )

    assert isinstance(resp_phrase, dict)
    assert "valid" in resp_phrase
    assert resp_phrase["valid"] is True

    # Test with multiple quoted phrases
    resp_multi_phrase = get_api_data(
        session,
        f"{host}/api/v1/search/hit/explain",
        method="POST",
        data=json.dumps({"query": 'howler.analytic:"Password Checker" OR howler.detection:"Suspicious Activity"'}),
    )

    assert isinstance(resp_multi_phrase, dict)
    assert "valid" in resp_multi_phrase
    assert resp_multi_phrase["valid"] is True


def test_explain_query_invalid_syntax(datastore, login_session):
    """Test explain query with invalid Lucene syntax"""
    session, host = login_session

    # Test with malformed query - unmatched quotes
    resp_field = get_api_data(
        session, f"{host}/api/v1/search/hit/explain", params={"query": 'howler.analytic:"unmatched quote'}
    )

    assert isinstance(resp_field, dict)
    assert "valid" in resp_field
    assert resp_field["valid"] is False

    # Test with malformed query - invalid field syntax
    resp_field = get_api_data(
        session,
        f"{host}/api/v1/search/hit/explain",
        method="POST",
        data=json.dumps({"query": "invalid::field:syntax"}),
    )

    assert isinstance(resp_field, dict)
    assert "valid" in resp_field
    assert resp_field["valid"] is False

    # Test with malformed query - unbalanced brackets
    resp_field = get_api_data(session, f"{host}/api/v1/search/hit/explain", params={"query": "howler.score:[50 TO"})

    assert isinstance(resp_field, dict)
    assert "valid" in resp_field
    assert resp_field["valid"] is False


def test_explain_query_missing_query(datastore, login_session):
    """Test explain query with missing query parameter"""
    session, host = login_session

    # Test GET request without query parameter
    with pytest.raises(APIError) as api_err:
        get_api_data(session, f"{host}/api/v1/search/hit/explain", params={})
    assert "400" in str(api_err)

    # Test POST request without query in body
    with pytest.raises(APIError) as api_err:
        get_api_data(session, f"{host}/api/v1/search/hit/explain", method="POST", data=json.dumps({}))
    assert "400" in str(api_err)

    # Test POST request with empty query
    with pytest.raises(APIError) as api_err:
        get_api_data(session, f"{host}/api/v1/search/hit/explain", method="POST", data=json.dumps({"query": ""}))
    assert "400" in str(api_err)


def test_explain_query_invalid_index(datastore, login_session):
    """Test explain query with invalid index"""
    session, host = login_session

    # Test with non-existent index
    with pytest.raises(APIError) as api_err:
        get_api_data(session, f"{host}/api/v1/search/nonexistent/explain", params={"query": "id:*"})
    assert "400" in str(api_err)


def test_explain_query_multiple_indexes(datastore, login_session):
    """Test explain query across different valid indexes"""
    session, host = login_session

    # Test with hit index (primary use case)
    resp_hit = get_api_data(session, f"{host}/api/v1/search/hit/explain", params={"query": "id:*"})
    assert isinstance(resp_hit, dict)
    assert "valid" in resp_hit
    assert resp_hit["valid"] is True

    # Test with user index
    resp_user = get_api_data(session, f"{host}/api/v1/search/user/explain", params={"query": "name:*"})
    assert isinstance(resp_user, dict)
    assert "valid" in resp_user
    assert resp_user["valid"] is True

    # TODO: Add tests for other indexes like template, overview once they're available in test data


def test_explain_query_lucene_phrase_escaping(datastore, login_session):
    """Test that Lucene phrase escaping works correctly in explain"""
    session, host = login_session

    # Test query with special characters that need escaping
    test_queries = [
        'howler.analytic:"Test: Analytic"',
        'howler.detection:"Alert (Suspicious)"',
        'howler.analytic:"Multi-Word Analytic Name"',
        'howler.detection:"Special & Characters"',
    ]

    for query in test_queries:
        resp = get_api_data(session, f"{host}/api/v1/search/hit/explain", params={"query": query})

        assert isinstance(resp, dict)
        assert "valid" in resp
        # The query should be valid after proper escaping
        assert resp["valid"] is True


def test_explain_query_response_structure(datastore, login_session):
    """Test the structure of explain query response"""
    session, host = login_session

    resp = get_api_data(session, f"{host}/api/v1/search/hit/explain", params={"query": "id:*"})

    # Basic response structure validation
    assert isinstance(resp, dict)
    assert "valid" in resp

    # TODO: Add more specific validation based on Elasticsearch validate_query API response
    # Common fields in Elasticsearch validation response:
    # - valid: boolean indicating if query is valid
    # - explanations: array of explanations (when explain=True)
    # - error: error details if query is invalid

    # For now, just ensure it's a valid response structure
    if "explanations" in resp:
        assert isinstance(resp["explanations"], list)

    if "error" in resp:
        assert isinstance(resp["error"], dict)


def test_explain_query_edge_cases(datastore, login_session):
    """Test explain query with edge cases and special scenarios"""
    session, host = login_session

    # Test with wildcard queries
    resp_wildcard = get_api_data(session, f"{host}/api/v1/search/hit/explain", params={"query": "*:*"})
    assert resp_wildcard["valid"] is True

    # Test with boolean queries
    resp_boolean = get_api_data(
        session,
        f"{host}/api/v1/search/hit/explain",
        params={"query": "howler.status:open AND NOT howler.status:closed"},
    )
    assert resp_boolean["valid"] is True

    # Test with range queries
    resp_range = get_api_data(
        session, f"{host}/api/v1/search/hit/explain", params={"query": "howler.timestamp:[2023-01-01 TO 2024-01-01]"}
    )
    assert resp_range["valid"] is True

    # TODO: Add tests for:
    # - Fuzzy queries (term~)
    # - Proximity queries ("term1 term2"~10)
    # - Boost queries (term^2)
    # - Nested queries (when applicable)
    # - Regular expression queries (/pattern/)
