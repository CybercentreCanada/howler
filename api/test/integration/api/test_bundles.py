import json

import pytest
from conftest import APIError, get_api_data

from howler.datastore.howler_store import HowlerDatastore
from howler.odm.models.hit import Hit
from howler.odm.random_data import create_bundles, create_hits, wipe_hits
from howler.odm.randomizer import (
    get_random_filename,
    get_random_hash,
    get_random_ip,
    get_random_iso_date,
)


@pytest.fixture(scope="module")
def datastore(datastore_connection: HowlerDatastore):
    try:
        wipe_hits(datastore_connection)

        create_hits(datastore_connection, hit_count=20)
        create_bundles(datastore_connection)

        # Commit changes to DataStore
        datastore_connection.hit.commit()

        yield datastore_connection
    finally:
        wipe_hits(datastore_connection)


def test_create_bundle_from_map(datastore: HowlerDatastore, login_session):
    session, host = login_session

    existing_hits = datastore.hit.search("howler.is_bundle:false", rows=2)["items"]

    tool_name = "test_bundles"
    map = {
        "analytic": ["howler.analytic"],
        "file.sha256": ["file.hash.sha256", "howler.hash"],
        "file.name": ["file.name"],
        "src_ip": ["source.ip", "related.ip"],
        "dest_ip": ["destination.ip", "related.ip"],
        "time.created": ["event.start"],
        "time.completed": ["event.end"],
        "raw": ["howler.data"],
        "is_bundle": ["howler.is_bundle"],
        "hits": ["howler.hits"],
    }
    hits = [{"is_bundle": True, "hits": [eh.howler.id for eh in existing_hits]}]
    for _ in range(2):
        hits.append(
            {
                "src_ip": get_random_ip(),
                "dest_ip": get_random_ip(),
                "file": {"name": get_random_filename(), "sha256": get_random_hash(64)},
                "time": {
                    "created": get_random_iso_date(),
                    "completed": get_random_iso_date(),
                },
            }
        )

    for hit in hits:
        hit["raw"] = {**hit}

    res = get_api_data(
        session,
        f"{host}/api/v1/tools/{tool_name}/hits",
        data=json.dumps({"map": map, "hits": hits}),
        method="POST",
    )

    assert len(res) == len(hits)
    num_bundles = 0
    for hit in res:
        data = get_api_data(
            session,
            f"{host}/api/v1/hit/{hit['id']}",
        )

        if data["howler"]["is_bundle"]:
            num_bundles += 1
            assert len(data["howler"]["hits"]) == (len(hits) - 1) + len(existing_hits)
            assert data["howler"]["bundle_size"] == len(data["howler"]["hits"])

    assert num_bundles == 1


def test_create_bundle_existing(datastore: HowlerDatastore, login_session):
    session, host = login_session

    hits = datastore.hit.search("howler.is_bundle:false", rows=2)["items"]

    req_data = {
        "bundle": {
            "howler.analytic": "test",
            "howler.score": 0.0,
        },
        "hits": [hit.howler.id for hit in hits],
    }

    resp = get_api_data(session, f"{host}/api/v1/hit/bundle", method="POST", data=json.dumps(req_data))

    assert resp["howler"]["is_bundle"]

    for hit in hits:
        child_hit_data = get_api_data(session, f"{host}/api/v1/hit/{hit.howler.id}")

        assert not child_hit_data["howler"]["is_bundle"]
        assert len(child_hit_data["howler"]["bundles"]) > 0


def test_create_bundle_only(datastore: HowlerDatastore, login_session):
    session, host = login_session

    hits = datastore.hit.search("howler.is_bundle:false AND -_exists_:howler.bundles", rows=2)["items"]

    req_data = {
        "bundle": {
            "howler.analytic": "test",
            "howler.score": 0.0,
            "howler.hits": [hit.howler.id for hit in hits],
        }
    }

    resp = get_api_data(session, f"{host}/api/v1/hit/bundle", method="POST", data=json.dumps(req_data))

    assert resp["howler"]["is_bundle"]

    for hit in hits:
        child_hit_data = get_api_data(session, f"{host}/api/v1/hit/{hit.howler.id}")

        assert not child_hit_data["howler"]["is_bundle"]
        assert sorted(list(set(child_hit_data["howler"]["bundles"]))) == sorted(child_hit_data["howler"]["bundles"])
        assert len(child_hit_data["howler"]["bundles"]) > 0


def test_create_bundle_fail_missing(datastore: HowlerDatastore, login_session):
    session, host = login_session

    hits = datastore.hit.search("howler.id:*", rows=2)["items"]

    req_data = {
        "hits": [hit.howler.id for hit in hits],
    }

    with pytest.raises(APIError) as err:
        get_api_data(
            session,
            f"{host}/api/v1/hit/bundle",
            method="POST",
            data=json.dumps(req_data),
        )

    assert err.value.args[0].startswith("400: You did not provide")

    req_data = {
        "bundle": {
            "howler.analytic": "test",
            "howler.score": 0.0,
        },
    }

    with pytest.raises(APIError) as err:
        get_api_data(
            session,
            f"{host}/api/v1/hit/bundle",
            method="POST",
            data=json.dumps(req_data),
        )

    assert err.value.args[0].startswith("400: You did not provide")


def test_create_bundle_fail_subbundle(datastore: HowlerDatastore, login_session):
    session, host = login_session

    hits = datastore.hit.search("howler.is_bundle:true", rows=2)["items"]

    req_data = {
        "bundle": {
            "howler.analytic": "test",
            "howler.score": 0.0,
            "howler.hits": [hit.howler.id for hit in hits],
        }
    }

    with pytest.raises(APIError) as err:
        get_api_data(
            session,
            f"{host}/api/v1/hit/bundle",
            method="POST",
            data=json.dumps(req_data),
        )

    assert err.value.args[0].startswith("400: You cannot specify a bundle as a child of another bundle")


def test_update_bundle(datastore: HowlerDatastore, login_session):
    session, host = login_session

    existing_bundle: Hit = datastore.hit.search("howler.is_bundle:true")["items"][0]

    new_child_hits = datastore.hit.search(
        f"howler.id:(NOT ({' OR '.join(existing_bundle.howler.hits)})) AND howler.is_bundle:false",
        rows=2,
    )["items"]

    get_api_data(
        session,
        f"{host}/api/v1/hit/bundle/{existing_bundle.howler.id}",
        method="PUT",
        data=json.dumps([hit.howler.id for hit in new_child_hits]),
    )

    for hit in new_child_hits:
        child_hit_data = get_api_data(session, f"{host}/api/v1/hit/{hit.howler.id}")

        assert not child_hit_data["howler"]["is_bundle"]

    assert len(get_api_data(session, f"{host}/api/v1/hit/{existing_bundle.howler.id}")["howler"]["hits"]) > len(
        existing_bundle.howler.hits
    )


def test_update_bundle_change_to_bundle(datastore: HowlerDatastore, login_session):
    session, host = login_session

    existing_non_bundle: Hit = datastore.hit.search("howler.is_bundle:false AND -_exists_:howler.bundles")["items"][0]

    assert not existing_non_bundle.howler.is_bundle

    new_child_hits = datastore.hit.search(
        "howler.is_bundle:false",
        rows=2,
    )["items"]

    get_api_data(
        session,
        f"{host}/api/v1/hit/bundle/{existing_non_bundle.howler.id}",
        method="PUT",
        data=json.dumps([hit.howler.id for hit in new_child_hits]),
    )

    for hit in new_child_hits:
        child_hit_data = get_api_data(session, f"{host}/api/v1/hit/{hit.howler.id}")

        assert not child_hit_data["howler"]["is_bundle"]

    assert get_api_data(session, f"{host}/api/v1/hit/{existing_non_bundle.howler.id}")["howler"]["is_bundle"]


def test_update_fail_subbundle(datastore: HowlerDatastore, login_session):
    session, host = login_session

    existing_bundle: Hit = datastore.hit.search("howler.is_bundle:true")["items"][0]

    new_child_hits = datastore.hit.search(
        f"howler.id:(NOT ({' OR '.join(existing_bundle.howler.hits)})) AND howler.is_bundle:true",
        rows=1,
    )["items"]

    with pytest.raises(APIError) as err:
        get_api_data(
            session,
            f"{host}/api/v1/hit/bundle/{existing_bundle.howler.id}",
            method="PUT",
            data=json.dumps([hit.howler.id for hit in new_child_hits]),
        )

    assert err.value.args[0].startswith("400: You cannot specify a bundle as a child of another bundle")


@pytest.mark.skip(reason="Unstable test")
def test_remove_bundle_children_some(datastore: HowlerDatastore, login_session):
    session, host = login_session

    existing_bundle: Hit = datastore.hit.search("howler.is_bundle:true")["items"][0]

    assert len(existing_bundle.howler.hits) > 1

    child_hit_data_before = get_api_data(session, f"{host}/api/v1/hit/{existing_bundle.howler.hits[0]}")

    assert len(child_hit_data_before["howler"]["bundles"]) > 0

    get_api_data(
        session,
        f"{host}/api/v1/hit/bundle/{existing_bundle.howler.id}",
        method="DELETE",
        data=json.dumps([existing_bundle.howler.hits[0]]),
    )

    child_hit_data = get_api_data(session, f"{host}/api/v1/hit/{existing_bundle.howler.hits[0]}")

    assert len(child_hit_data["howler"]["bundles"]) < len(child_hit_data_before["howler"]["bundles"])

    resp = get_api_data(session, f"{host}/api/v1/hit/{existing_bundle.howler.id}")

    assert len(resp["howler"]["hits"]) < len(existing_bundle.howler.hits)
    assert resp["howler"]["is_bundle"]


def test_remove_bundle_children_all(datastore: HowlerDatastore, login_session):
    session, host = login_session

    existing_bundle: Hit = datastore.hit.search("howler.is_bundle:true")["items"][0]

    get_api_data(
        session,
        f"{host}/api/v1/hit/bundle/{existing_bundle.howler.id}",
        method="DELETE",
        data=json.dumps(["*"]),
    )

    resp = get_api_data(session, f"{host}/api/v1/hit/{existing_bundle.howler.id}")

    assert not resp["howler"]["is_bundle"]
    assert len(resp["howler"]["hits"]) < 1


def test_delete_hit(datastore: HowlerDatastore, login_session):
    session, host = login_session

    existing_bundle: Hit = datastore.hit.search("howler.is_bundle:true")["items"][0]

    hit_id_to_delete = existing_bundle.howler.hits[0]

    get_api_data(
        session=session,
        url=f"{host}/api/v1/hit/",
        data=json.dumps([hit_id_to_delete]),
        method="DELETE",
    )

    assert hit_id_to_delete not in datastore.hit.get(existing_bundle.howler.id).howler.hits
