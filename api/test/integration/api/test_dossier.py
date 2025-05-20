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

    datastore.dossier.commit()
    total = datastore.dossier.search("dossier_id:*")["total"]

    create_res = get_api_data(
        session,
        f"{host}/api/v1/dossier/",
        method="POST",
        data=json.dumps({"title": "testremove", "type": "global", "query": "howler.hash:*", "leads": []}),
    )

    datastore.dossier.commit()
    assert total + 1 == datastore.dossier.search("dossier_id:*")["total"]

    res = get_api_data(session, f"{host}/api/v1/dossier/{create_res['dossier_id']}/", method="DELETE")

    datastore.dossier.commit()
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

    datastore.dossier.commit()

    updated_dossier = datastore.dossier.get(dossier_id, as_obj=True)
    assert updated_dossier.title == "new title thing"
