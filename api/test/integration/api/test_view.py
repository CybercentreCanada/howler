import json

import pytest
from conftest import APIError, get_api_data

from howler.datastore.howler_store import HowlerDatastore
from howler.odm.models.view import View
from howler.odm.random_data import create_views, wipe_views


@pytest.fixture(scope="module")
def datastore(datastore_connection):
    ds = datastore_connection
    try:
        create_views(ds)

        yield ds
    finally:
        wipe_views(ds)


# noinspection PyUnusedLocal
def test_add_view(datastore: HowlerDatastore, login_session):
    session, host = login_session

    view_data = {}

    with pytest.raises(APIError) as err:
        get_api_data(
            session,
            f"{host}/api/v1/view/",
            method="POST",
            data=json.dumps(view_data),
        )

    assert "title" in str(err.value)

    view_data["title"] = "Test View"

    with pytest.raises(APIError) as err:
        get_api_data(
            session,
            f"{host}/api/v1/view/",
            method="POST",
            data=json.dumps(view_data),
        )

    assert "query" in str(err.value)

    view_data["query"] = "howler.id:*"
    with pytest.raises(APIError) as err:
        get_api_data(
            session,
            f"{host}/api/v1/view/",
            method="POST",
            data=json.dumps(view_data),
        )

    assert "type" in str(err.value)

    view_data["type"] = "personal"

    resp = get_api_data(
        session,
        f"{host}/api/v1/view/",
        method="POST",
        data=json.dumps(view_data),
    )

    assert resp["owner"] == "admin"

    view_data["type"] = "global"
    resp = get_api_data(
        session,
        f"{host}/api/v1/view/",
        method="POST",
        data=json.dumps(view_data),
    )

    assert resp["owner"] == "admin"


# noinspection PyUnusedLocal
def test_get_views(datastore, login_session):
    session, host = login_session

    resp = get_api_data(session, f"{host}/api/v1/view/")

    assert all(t["type"] == "global" or t["owner"] in ["admin", "none"] for t in resp)


# noinspection PyUnusedLocal
def test_remove_view(datastore: HowlerDatastore, login_session):
    session, host = login_session

    datastore.view.commit()
    total = datastore.view.search("view_id:*")["total"]

    create_res = get_api_data(
        session,
        f"{host}/api/v1/view/",
        method="POST",
        data=json.dumps({"title": "testremove", "type": "global", "query": "howler.hash:*"}),
    )

    datastore.view.commit()
    assert total + 1 == datastore.view.search("view_id:*")["total"]

    res = get_api_data(session, f"{host}/api/v1/view/{create_res['view_id']}/", method="DELETE")

    datastore.view.commit()
    assert res is None
    assert total == datastore.view.search("view_id:*")["total"]


# noinspection PyUnusedLocal
def test_set_view(datastore: HowlerDatastore, login_session):
    session, host = login_session

    id = datastore.view.search("owner:admin AND type:(-readonly)")["items"][0]["view_id"]

    resp = get_api_data(
        session,
        f"{host}/api/v1/view/{id}/",
        method="PUT",
        data=json.dumps({"title": "new title thing"}),
    )
    assert resp["title"] == "new title thing"

    datastore.view.commit()

    updated_view = datastore.view.get(id, as_obj=True)
    assert updated_view.title == "new title thing"


def test_favourite(datastore: HowlerDatastore, login_session):
    session, host = login_session

    uname = get_api_data(session, f"{host}/api/v1/user/whoami", method="GET")["username"]

    view: View = datastore.view.search(f"type:global OR owner:{uname}")["items"][0]

    get_api_data(
        session,
        f"{host}/api/v1/view/{view.view_id}/favourite",
        method="POST",
        data={},
    )

    datastore.user.commit()

    assert view.view_id in datastore.user.search(f"uname:{uname}")["items"][0]["favourite_views"]

    get_api_data(
        session,
        f"{host}/api/v1/view/{view.view_id}/favourite",
        method="DELETE",
    )

    datastore.user.commit()

    assert view.view_id not in datastore.user.search(f"uname:{uname}")["items"][0]["favourite_views"]
