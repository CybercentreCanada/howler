import json
from typing import cast

import pytest
from conftest import APIError, get_api_data

from howler.datastore.howler_store import HowlerDatastore
from howler.odm.models.hit import Hit
from howler.odm.random_data import create_hits, create_users, wipe_hits, wipe_users

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

        yield ds
    finally:
        wipe_hits(datastore_connection)
        wipe_users(ds)
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

    # Test search with metadata using GET request
    resp_with_metadata_get = get_api_data(
        session,
        f"{host}/api/v1/search/hit/",
        params={"query": "id:*", "rows": 5, "metadata": ["template", "overview", "dossiers"]},
    )

    # Should have same number of results
    assert resp_with_metadata_get["total"] == resp_without_metadata["total"]
    assert len(resp_with_metadata_get["items"]) == len(resp_without_metadata["items"])

    # Verify metadata fields are present
    for item in resp_with_metadata_get["items"]:
        assert "__template" in item
        assert "__overview" in item
        assert "__dossiers" in item

        if item["howler"]["analytic"] in ["Password Checker", "Bad Guy Finder"]:
            assert item["__template"]["analytic"] == item["howler"]["analytic"]
            assert item["__overview"]["analytic"] == item["howler"]["analytic"]

        assert isinstance(item["__dossiers"], list)

    # Test search with metadata using POST request
    resp_with_metadata_post = get_api_data(
        session,
        f"{host}/api/v1/search/hit/",
        method="POST",
        data=json.dumps({"query": "id:*", "rows": 5, "metadata": ["template", "overview"]}),
    )

    # Should have same number of results as other requests
    assert resp_with_metadata_post["total"] == resp_without_metadata["total"]
    assert len(resp_with_metadata_post["items"]) == len(resp_without_metadata["items"])

    # Verify metadata fields are present
    for item in resp_with_metadata_post["items"]:
        assert "__template" in item
        assert "__overview" in item
        assert "__dossiers" not in item

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
