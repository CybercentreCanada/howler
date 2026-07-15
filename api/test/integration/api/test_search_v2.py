import json
from typing import cast

import pytest

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
from test.conftest import APIError, get_api_data

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
            resp = get_api_data(session, f"{host}/api/v2/search/{collection}", params=params)
            res.extend(resp["items"])
            if len(resp["items"]) == 0 or "next_deep_paging_id" not in resp:
                break
            params["deep_paging_id"] = resp["next_deep_paging_id"]
        assert len(res) >= TEST_SIZE


def test_facet_search(datastore, login_session):
    session, host = login_session

    for collection in collections:
        resp = get_api_data(
            session,
            f"{host}/api/v2/search/facet/{collection}",
            params={"fields": "name"},
        )
        assert len(resp) == 1
        assert len(resp["name"]) == TEST_SIZE
        for v in resp["name"].values():
            assert isinstance(v, int)

        resp = get_api_data(
            session,
            f"{host}/api/v2/search/facet/{collection}",
            method="POST",
            data=json.dumps({"fields": ["name"]}),
        )
        assert len(resp) == 1
        assert len(resp["name"]) == TEST_SIZE
        for v in resp["name"].values():
            assert isinstance(v, int)


def test_search(datastore, login_session):
    session, host = login_session

    for collection in collections:
        resp = get_api_data(session, f"{host}/api/v2/search/{collection}", params={"query": "id:*"})
        assert TEST_SIZE <= resp["total"] >= len(resp["items"])


def test_count(datastore, login_session):
    session, host = login_session

    for collection in collections:
        search_resp = get_api_data(session, f"{host}/api/v2/search/{collection}", params={"query": "id:*"})
        count_resp = get_api_data(
            session,
            f"{host}/api/v2/search/count/{collection}",
            params={"query": "id:*"},
        )
        assert search_resp["total"] == count_resp["count"]


def test_count_via_post(datastore, login_session):
    session, host = login_session

    for collection in collections:
        get_resp = get_api_data(
            session,
            f"{host}/api/v2/search/count/{collection}",
            method="GET",
            params={"query": "id:*"},
        )

        post_resp = get_api_data(
            session,
            f"{host}/api/v2/search/count/{collection}",
            method="POST",
            data=json.dumps({"query": "id:*"}),
        )
        assert "count" in post_resp
        assert get_resp["count"] == post_resp["count"]


def test_count_with_filters_vs_total(datastore, login_session):
    session, host = login_session

    total_resp = get_api_data(
        session,
        f"{host}/api/v2/search/count/hit",
        method="POST",
        data=json.dumps({"query": "howler.id:*"}),
    )
    assert total_resp["count"] > 0

    filtered_resp = get_api_data(
        session,
        f"{host}/api/v2/search/count/hit",
        method="POST",
        data=json.dumps({"query": "howler.id:*", "filters": ["howler.status:open"]}),
    )
    assert "count" in filtered_resp
    assert filtered_resp["count"] <= total_resp["count"]


def test_count_zero_results(datastore, login_session):
    session, host = login_session

    for collection in collections:
        resp = get_api_data(
            session,
            f"{host}/api/v2/search/count/{collection}",
            method="POST",
            data=json.dumps({"query": "name:not_real_value"}),
        )
        assert "count" in resp
        assert resp["count"] == 0


def test_count_with_filters(datastore, login_session):
    session, host = login_session

    total_resp = get_api_data(
        session,
        f"{host}/api/v2/search/count/hit",
        method="POST",
        data=json.dumps({"query": "howler.id:*"}),
    )
    assert total_resp["count"] > 0

    filtered_resp = get_api_data(
        session,
        f"{host}/api/v2/search/count/hit",
        method="POST",
        data=json.dumps({"query": "howler.id:*", "filters": ["howler.status:open"]}),
    )
    assert "count" in filtered_resp
    assert filtered_resp["count"] <= total_resp["count"]


def test_count_missing_query(datastore, login_session):
    """Omitting the query parameter returns a 400 error for both GET and POST."""
    session, host = login_session

    with pytest.raises(APIError) as api_err:
        get_api_data(session, f"{host}/api/v2/search/count/user")
    assert "400" in str(api_err)

    with pytest.raises(APIError) as api_err:
        get_api_data(
            session,
            f"{host}/api/v2/search/count/user",
            method="POST",
            data=json.dumps({}),
        )
    assert "400" in str(api_err)

    with pytest.raises(APIError) as api_err:
        get_api_data(
            session,
            f"{host}/api/v2/search/count/user",
            method="POST",
            data=json.dumps({"query": ""}),
        )
    assert "400" in str(api_err)


def test_count_invalid_index(datastore, login_session):
    session, host = login_session

    with pytest.raises(APIError) as api_err:
        get_api_data(
            session,
            f"{host}/api/v2/search/count/nonexistent_index",
            params={"query": "id:*"},
        )
    assert "400" in str(api_err)


def test_count_hit_matches_search_total(datastore, login_session):
    """Count result for the hit index is consistent with the total from a full search."""
    session, host = login_session

    search_resp = get_api_data(
        session,
        f"{host}/api/v2/search/hit",
        params={"query": "howler.id:*", "track_total_hits": "true"},
    )
    count_resp = get_api_data(
        session,
        f"{host}/api/v2/search/count/hit",
        params={"query": "howler.id:*"},
    )
    assert count_resp["count"] == search_resp["total"]


def test_hit_analytic_search(datastore: HowlerDatastore, login_session):
    session, host = login_session

    case_sensitive_total = get_api_data(
        session,
        f"{host}/api/v2/search/hit",
        params={"query": 'howler.analytic:"Password Checker"'},
    )["total"]

    case_insensitive_total_1 = get_api_data(
        session,
        f"{host}/api/v2/search/hit",
        params={"query": 'howler.analytic:"password checker"'},
    )["total"]
    assert case_sensitive_total == case_insensitive_total_1

    case_insensitive_total_2 = get_api_data(
        session,
        f"{host}/api/v2/search/hit",
        params={"query": 'howler.analytic:"PaSsWoRd ChEcKeR"'},
    )["total"]
    assert case_sensitive_total == case_insensitive_total_2


def test_hit_detection_search(datastore: HowlerDatastore, login_session):
    session, host = login_session

    example_hit: Hit = get_api_data(
        session,
        f"{host}/api/v2/search/hit",
        params={"query": "_exists_:howler.detection", "rows": 1},
    )["items"][0]
    detection = cast(str, example_hit["howler"]["detection"])

    case_sensitive_total = get_api_data(
        session,
        f"{host}/api/v2/search/hit",
        params={"query": f'howler.detection:"{detection}"'},
    )["total"]

    case_insensitive_total_1 = get_api_data(
        session,
        f"{host}/api/v2/search/hit",
        params={"query": f'howler.detection:"{detection.lower()}"'},
    )["total"]
    assert case_sensitive_total == case_insensitive_total_1

    silly_detection = ""
    for i in range(len(detection)):
        if float(int(i / 2)) == i / 2:
            silly_detection += detection[i].upper()
        else:
            silly_detection += detection[i].lower()

    case_insensitive_total_2 = get_api_data(
        session,
        f"{host}/api/v2/search/hit",
        params={"query": f'howler.detection:"{silly_detection}"'},
    )["total"]
    assert case_sensitive_total == case_insensitive_total_2


def test_hit_search_with_metadata(datastore: HowlerDatastore, login_session):
    session, host = login_session

    resp_without_metadata = get_api_data(
        session, f"{host}/api/v2/search/hit", params={"query": "howler.id:*", "rows": 5}
    )

    assert resp_without_metadata["total"] > 0
    assert len(resp_without_metadata["items"]) > 0

    for item in resp_without_metadata["items"]:
        assert "__template" not in item
        assert "__overview" not in item
        assert "__dossiers" not in item
        assert "__analytic" not in item

    resp_with_metadata_get = get_api_data(
        session,
        f"{host}/api/v2/search/hit",
        params={"query": "howler.id:*", "rows": 5, "metadata": ["template", "overview", "dossiers", "analytic"]},
    )

    assert resp_with_metadata_get["total"] == resp_without_metadata["total"]
    assert len(resp_with_metadata_get["items"]) == len(resp_without_metadata["items"])

    for item in resp_with_metadata_get["items"]:
        assert "__template" in item
        assert "__overview" in item
        assert "__dossiers" in item
        assert "__analytic" in item

        if item["howler"]["analytic"] in ["Password Checker", "Bad Guy Finder"]:
            assert item["__template"]["analytic"] == item["howler"]["analytic"]
            assert item["__overview"]["analytic"] == item["howler"]["analytic"]

        assert isinstance(item["__dossiers"], list)

        if item["__analytic"]:
            assert isinstance(item["__analytic"], dict)
            assert "name" in item["__analytic"]
            assert item["__analytic"]["name"] == item["howler"]["analytic"]
            assert "analytic_id" in item["__analytic"]

    resp_with_metadata_post = get_api_data(
        session,
        f"{host}/api/v2/search/hit",
        method="POST",
        data=json.dumps({"query": "howler.id:*", "rows": 5, "metadata": ["template", "overview", "analytic"]}),
    )

    assert resp_with_metadata_post["total"] == resp_without_metadata["total"]
    assert len(resp_with_metadata_post["items"]) == len(resp_without_metadata["items"])

    for item in resp_with_metadata_post["items"]:
        assert "__template" in item
        assert "__overview" in item
        assert "__analytic" in item
        assert "__dossiers" not in item

        if item["__analytic"]:
            assert isinstance(item["__analytic"], dict)
            assert "name" in item["__analytic"]
            assert item["__analytic"]["name"] == item["howler"]["analytic"]

    resp_user = get_api_data(
        session,
        f"{host}/api/v2/search/user",
        params={"query": "id:*", "rows": 5, "metadata": ["template"]},
    )

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

    resp = get_api_data(session, f"{host}/api/v2/search/hit/explain", params={"query": "howler.id:*"})

    assert isinstance(resp, dict)
    assert "valid" in resp
    assert resp["valid"] is True

    assert "_shards" not in resp

    for explanation in resp["explanations"]:
        assert "index" not in explanation

    resp_complex = get_api_data(
        session,
        f"{host}/api/v2/search/hit/explain",
        params={"query": 'howler.analytic:"Password Checker" AND howler.status:open'},
    )

    assert isinstance(resp_complex, dict)
    assert "valid" in resp_complex
    assert resp_complex["valid"] is True

    resp_field = get_api_data(
        session, f"{host}/api/v2/search/hit/explain", params={"query": "howler.score:[50 TO 100]"}
    )

    assert isinstance(resp_field, dict)
    assert "valid" in resp_field
    assert resp_field["valid"] is True


def test_explain_query_post(datastore, login_session):
    """Test explain query functionality using POST request"""
    session, host = login_session

    resp = get_api_data(
        session, f"{host}/api/v2/search/hit/explain", method="POST", data=json.dumps({"query": "howler.id:*"})
    )

    assert isinstance(resp, dict)
    assert "valid" in resp
    assert resp["valid"] is True

    resp_phrase = get_api_data(
        session,
        f"{host}/api/v2/search/hit/explain",
        method="POST",
        data=json.dumps({"query": 'howler.analytic:"Example Analytic"'}),
    )

    assert isinstance(resp_phrase, dict)
    assert "valid" in resp_phrase
    assert resp_phrase["valid"] is True

    resp_multi_phrase = get_api_data(
        session,
        f"{host}/api/v2/search/hit/explain",
        method="POST",
        data=json.dumps({"query": 'howler.analytic:"Password Checker" OR howler.detection:"Suspicious Activity"'}),
    )

    assert isinstance(resp_multi_phrase, dict)
    assert "valid" in resp_multi_phrase
    assert resp_multi_phrase["valid"] is True


def test_explain_query_invalid_syntax(datastore, login_session):
    """Test explain query with invalid Lucene syntax"""
    session, host = login_session

    resp_field = get_api_data(
        session, f"{host}/api/v2/search/hit/explain", params={"query": 'howler.analytic:"unmatched quote'}
    )

    assert isinstance(resp_field, dict)
    assert "valid" in resp_field
    assert resp_field["valid"] is False

    resp_field = get_api_data(
        session,
        f"{host}/api/v2/search/hit/explain",
        method="POST",
        data=json.dumps({"query": "invalid::field:syntax"}),
    )

    assert isinstance(resp_field, dict)
    assert "valid" in resp_field
    assert resp_field["valid"] is False

    resp_field = get_api_data(session, f"{host}/api/v2/search/hit/explain", params={"query": "howler.score:[50 TO"})

    assert isinstance(resp_field, dict)
    assert "valid" in resp_field
    assert resp_field["valid"] is False


def test_explain_query_missing_query(datastore, login_session):
    """Omitting the query parameter returns a 400 error for both GET and POST."""
    session, host = login_session

    with pytest.raises(APIError) as api_err:
        get_api_data(session, f"{host}/api/v2/search/hit/explain", params={})
    assert "400" in str(api_err)

    with pytest.raises(APIError) as api_err:
        get_api_data(session, f"{host}/api/v2/search/hit/explain", method="POST", data=json.dumps({}))
    assert "400" in str(api_err)

    with pytest.raises(APIError) as api_err:
        get_api_data(session, f"{host}/api/v2/search/hit/explain", method="POST", data=json.dumps({"query": ""}))
    assert "400" in str(api_err)


def test_explain_query_invalid_index(datastore, login_session):
    """Test explain query with invalid index"""
    session, host = login_session

    with pytest.raises(APIError) as api_err:
        get_api_data(session, f"{host}/api/v2/search/nonexistent/explain", params={"query": "id:*"})
    assert "400" in str(api_err)


def test_explain_query_multiple_indexes(datastore, login_session):
    """Test explain query across different valid indexes"""
    session, host = login_session

    resp_hit = get_api_data(session, f"{host}/api/v2/search/hit/explain", params={"query": "howler.id:*"})
    assert isinstance(resp_hit, dict)
    assert "valid" in resp_hit
    assert resp_hit["valid"] is True

    resp_user = get_api_data(session, f"{host}/api/v2/search/user/explain", params={"query": "name:*"})
    assert isinstance(resp_user, dict)
    assert "valid" in resp_user
    assert resp_user["valid"] is True


def test_explain_query_lucene_phrase_escaping(datastore, login_session):
    """Test that Lucene phrase escaping works correctly in explain"""
    session, host = login_session

    test_queries = [
        'howler.analytic:"Test: Analytic"',
        'howler.detection:"Alert (Suspicious)"',
        'howler.analytic:"Multi-Word Analytic Name"',
        'howler.detection:"Special & Characters"',
    ]

    for query in test_queries:
        resp = get_api_data(session, f"{host}/api/v2/search/hit/explain", params={"query": query})

        assert isinstance(resp, dict)
        assert "valid" in resp
        assert resp["valid"] is True


def test_explain_query_response_structure(datastore, login_session):
    """Test the structure of explain query response"""
    session, host = login_session

    resp = get_api_data(session, f"{host}/api/v2/search/hit/explain", params={"query": "howler.id:*"})

    assert isinstance(resp, dict)
    assert "valid" in resp

    if "explanations" in resp:
        assert isinstance(resp["explanations"], list)

    if "error" in resp:
        assert isinstance(resp["error"], dict)


def test_explain_query_edge_cases(datastore, login_session):
    """Test explain query with edge cases and special scenarios"""
    session, host = login_session

    resp_wildcard = get_api_data(session, f"{host}/api/v2/search/hit/explain", params={"query": "*:*"})
    assert resp_wildcard["valid"] is True

    resp_boolean = get_api_data(
        session,
        f"{host}/api/v2/search/hit/explain",
        params={"query": "howler.status:open AND NOT howler.status:closed"},
    )
    assert resp_boolean["valid"] is True

    resp_range = get_api_data(
        session, f"{host}/api/v2/search/hit/explain", params={"query": "howler.timestamp:[2023-01-01 TO 2024-01-01]"}
    )
    assert resp_range["valid"] is True


def test_search_fl_wildcard_expands_prefix(datastore: HowlerDatastore, login_session):
    """Wildcard patterns in the fl parameter must be expanded to matching fields."""
    session, host = login_session

    resp = get_api_data(
        session,
        f"{host}/api/v2/search/hit",
        params={"query": "howler.id:*", "rows": 1, "fl": "howler.*"},
    )

    assert resp["total"] > 0
    item = resp["items"][0]

    for key in item:
        if key == "id":
            continue
        assert key in {"howler", "__index"} or key.startswith("howler."), (
            f"Unexpected key {key!r} returned when fl='howler.*'"
        )

    assert "howler" in item
    assert "id" in item["howler"] or "status" in item["howler"]


def test_search_fl_wildcard_mixed(datastore: HowlerDatastore, login_session):
    """Combining a wildcard pattern with an exact field name must work correctly."""
    session, host = login_session

    resp = get_api_data(
        session,
        f"{host}/api/v2/search/hit",
        params={"query": "howler.id:*", "rows": 1, "fl": "howler.id,event.*"},
    )

    assert resp["total"] > 0
    item = resp["items"][0]

    assert "howler" in item
    assert "id" in item["howler"]

    assert "event" in item or any(k.startswith("event.") for k in item), (
        "Expected event fields to be present when fl includes 'event.*'"
    )


def test_search_fl_wildcard_exact_match_fallback(datastore: HowlerDatastore, login_session):
    """A non-wildcard fl value must continue to work as before."""
    session, host = login_session

    resp = get_api_data(
        session,
        f"{host}/api/v2/search/hit",
        params={"query": "howler.id:*", "rows": 1, "fl": "howler.id"},
    )

    assert resp["total"] > 0
    item = resp["items"][0]
    assert "howler" in item
    assert "id" in item["howler"]


def test_search_fail(datastore, login_session):
    session, host = login_session

    with pytest.raises(APIError) as api_err:
        get_api_data(session, f"{host}/api/v2/search/hit", params={"query": "--1123!@#21123!@#9sfg8d76dfvhjkln543"})
    assert "400" in str(api_err)

    with pytest.raises(APIError) as api_err:
        get_api_data(
            session,
            f"{host}/api/v2/search/count/hit",
            params={"query": "--1123!@#21123!@#9sfg8d76dfvhjkln543"},
        )
    assert "400" in str(api_err)

    with pytest.raises(APIError) as api_err:
        get_api_data(
            session,
            f"{host}/api/v2/search/facet/hit",
            method="POST",
            data=json.dumps({"query": "--1123!@#21123!@#9sfg8d76dfvhjkln543", "fields": ["howler.status"]}),
        )
    assert "400" in str(api_err)
