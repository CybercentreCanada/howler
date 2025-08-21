import json
from typing import Any

import pytest
from conftest import APIError, get_api_data

from howler.datastore.howler_store import HowlerDatastore
from howler.odm.random_data import create_dossiers, wipe_dossiers


@pytest.fixture(scope="module")
def datastore(datastore_connection):
    ds = datastore_connection
    try:
        create_dossiers(ds)

        yield ds
    finally:
        wipe_dossiers(ds)


# noinspection PyUnusedLocal
def test_add_dossier(datastore: HowlerDatastore, login_session):
    session, host = login_session

    dossier_data: dict[str, Any] = {"leads": []}

    with pytest.raises(APIError) as err:
        get_api_data(
            session,
            f"{host}/api/v1/dossier/",
            method="POST",
            data=json.dumps(dossier_data),
        )

    assert "title" in str(err.value)

    dossier_data["title"] = "Test dossier"

    with pytest.raises(APIError) as err:
        get_api_data(
            session,
            f"{host}/api/v1/dossier/",
            method="POST",
            data=json.dumps(dossier_data),
        )

    assert "query" in str(err.value)

    dossier_data["query"] = "howler.id:*"
    with pytest.raises(APIError) as err:
        get_api_data(
            session,
            f"{host}/api/v1/dossier/",
            method="POST",
            data=json.dumps(dossier_data),
        )

    assert "type" in str(err.value)

    dossier_data["type"] = "personal"

    resp = get_api_data(
        session,
        f"{host}/api/v1/dossier/",
        method="POST",
        data=json.dumps(dossier_data),
    )

    assert resp["owner"] == "admin"

    dossier_data["type"] = "global"
    resp = get_api_data(
        session,
        f"{host}/api/v1/dossier/",
        method="POST",
        data=json.dumps(dossier_data),
    )

    assert resp["owner"] == "admin"


# noinspection PyUnusedLocal
def test_get_dossiers(datastore, login_session):
    session, host = login_session

    resp = get_api_data(session, f"{host}/api/v1/dossier/")

    assert all(t["type"] == "global" or t["owner"] in ["admin", "none"] for t in resp)


# noinspection PyUnusedLocal
def test_remove_dossier(datastore: HowlerDatastore, login_session):
    session, host = login_session

    total = datastore.dossier.search("dossier_id:*")["total"]

    create_res = get_api_data(
        session,
        f"{host}/api/v1/dossier/",
        method="POST",
        data=json.dumps({"title": "testremove", "type": "global", "query": "howler.hash:*", "leads": []}),
    )

    assert total + 1 == datastore.dossier.search("dossier_id:*")["total"]

    res = get_api_data(session, f"{host}/api/v1/dossier/{create_res['dossier_id']}/", method="DELETE")

    assert res is None
    assert total == datastore.dossier.search("dossier_id:*")["total"]


# noinspection PyUnusedLocal
def test_set_dossier(datastore: HowlerDatastore, login_session):
    session, host = login_session

    dossier_id = datastore.dossier.search("owner:admin")["items"][0]["dossier_id"]

    resp = get_api_data(
        session,
        f"{host}/api/v1/dossier/{dossier_id}/",
        method="PUT",
        data=json.dumps({"title": "new title thing"}),
    )
    assert resp["title"] == "new title thing"

    updated_dossier = datastore.dossier.get(dossier_id, as_obj=True)
    assert updated_dossier.title == "new title thing"


# noinspection PyUnusedLocal
def test_get_dossier_for_hit(datastore: HowlerDatastore, login_session):
    session, host = login_session

    # Create a test hit with a unique howler.id
    test_hit_id = "test-hit-for-dossier-matching"
    hit_data = {
        "howler": {
            "id": test_hit_id,
            "analytic": "Test analytic for dossier matching",
            "hash": "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48cc",
            "score": "0.8",
            "assignment": "admin",
            "outline": {
                "threat": "10.0.0.1",
                "target": "test-target",
                "indicators": ["test-indicator"],
                "summary": "Test hit for dossier matching",
            },
        },
        "event": {
            "provider": "test",
        },
    }

    # Save the hit to the datastore
    datastore.hit.save(test_hit_id, hit_data)

    # Create a dossier that matches this hit (query matches the hit's howler.id)
    dossier_data = {
        "title": "Test Dossier for Hit Matching",
        "query": f'howler.id:"{test_hit_id}"',
        "type": "global",
        "leads": [],
    }

    create_res = get_api_data(
        session,
        f"{host}/api/v1/dossier/",
        method="POST",
        data=json.dumps(dossier_data),
    )

    created_dossier_id = create_res["dossier_id"]

    try:
        # Test the get_dossier_for_hit endpoint
        resp = get_api_data(
            session,
            f"{host}/api/v1/dossier/hit/{test_hit_id}/",
            method="GET",
        )

        # Verify the response is a list
        assert isinstance(resp, list)

        # Check that our created dossier is in the result list
        matching_dossier_ids = [d["dossier_id"] for d in resp]
        assert created_dossier_id in matching_dossier_ids

        # Find our specific dossier in the response and verify its data
        our_dossier = next((d for d in resp if d["dossier_id"] == created_dossier_id), None)
        assert our_dossier is not None
        assert our_dossier["title"] == "Test Dossier for Hit Matching"
        assert our_dossier["query"] == f'howler.id:"{test_hit_id}"'
        assert our_dossier["type"] == "global"

    finally:
        # Clean up - delete the hit and dossier from the database
        datastore.hit.delete(test_hit_id)

        datastore.dossier.delete(created_dossier_id)
