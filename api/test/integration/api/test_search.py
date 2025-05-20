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


# noinspection PyUnusedLocal
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


# noinspection PyUnusedLocal
def test_facet_search(datastore, login_session):
    session, host = login_session

    for collection in collections:
        resp = get_api_data(session, f"{host}/api/v1/search/facet/{collection}/name/")
        assert len(resp) == TEST_SIZE
        for v in resp.values():
            assert isinstance(v, int)


# noinspection PyUnusedLocal
def test_grouped_search(datastore, login_session):
    session, host = login_session

    for collection in collections:
        resp = get_api_data(session, f"{host}/api/v1/search/grouped/{collection}/name/")
        assert resp["total"] >= TEST_SIZE
        for v in resp["items"]:
            assert v["total"] == 1 and "value" in v


# noinspection PyUnusedLocal
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


# noinspection PyUnusedLocal
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


# noinspection PyUnusedLocal
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


# noinspection PyUnusedLocal
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
