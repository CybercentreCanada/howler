import json
from typing import Any

import pytest
from conftest import APIError, get_api_data

from howler.datastore.howler_store import HowlerDatastore
from howler.odm.random_data import create_overviews, wipe_overviews


@pytest.fixture(scope="module")
def datastore(datastore_connection):
    ds = datastore_connection
    try:
        create_overviews(ds)

        yield ds
    finally:
        wipe_overviews(ds)


# noinspection PyUnusedLocal
def test_add_overview(datastore: HowlerDatastore, login_session):
    session, host = login_session

    overview_data: dict[str, Any] = {}

    with pytest.raises(APIError) as err:
        get_api_data(
            session,
            f"{host}/api/v1/overview/",
            method="POST",
            data=json.dumps(overview_data),
        )

    assert "content" in str(err.value)

    overview_data["content"] = "#Overview Content\n\nOverview Content"

    with pytest.raises(APIError) as err:
        get_api_data(
            session,
            f"{host}/api/v1/overview/",
            method="POST",
            data=json.dumps(overview_data),
        )

    assert "analytic" in str(err.value)

    overview_data["analytic"] = "test"
    resp = get_api_data(
        session,
        f"{host}/api/v1/overview/",
        method="POST",
        data=json.dumps(overview_data),
    )

    assert resp["owner"] == "admin"


# noinspection PyUnusedLocal
def test_get_overviews(datastore, login_session):
    session, host = login_session

    resp = get_api_data(session, f"{host}/api/v1/overview/")

    assert all(t["content"] for t in resp)


# noinspection PyUnusedLocal
def test_remove_overview(datastore: HowlerDatastore, login_session):
    session, host = login_session

    datastore.overview.commit()
    total = datastore.overview.search("overview_id:*")["total"]

    create_res = get_api_data(
        session,
        f"{host}/api/v1/overview/",
        method="POST",
        data=json.dumps({"analytic": "testremove", "owner": "admin", "content": "# Test"}),
    )

    datastore.overview.commit()
    assert total + 1 == datastore.overview.search("overview_id:*")["total"]

    res = get_api_data(session, f"{host}/api/v1/overview/{create_res['overview_id']}/", method="DELETE")

    datastore.overview.commit()
    assert res is None
    assert total == datastore.overview.search("overview_id:*")["total"]


def test_overview_conflict(datastore: HowlerDatastore, login_session):
    session, host = login_session

    get_api_data(
        session,
        f"{host}/api/v1/overview/",
        method="POST",
        data=json.dumps({"analytic": "test-conflict", "owner": "admin", "content": "# Test"}),
    )

    datastore.overview.commit()

    with pytest.raises(APIError) as err:
        get_api_data(
            session,
            f"{host}/api/v1/overview/",
            method="POST",
            data=json.dumps({"analytic": "test-conflict", "owner": "admin", "content": "# Test"}),
        )

    assert "already exists" in str(err.value)


# noinspection PyUnusedLocal
def test_set_overview(datastore: HowlerDatastore, login_session):
    session, host = login_session

    id = datastore.overview.search("owner:admin")["items"][0]["overview_id"]
    resp = get_api_data(
        session,
        f"{host}/api/v1/overview/{id}/",
        method="PUT",
        data=json.dumps({"content": "Potato"}),
    )
    assert resp["content"] == "Potato"

    datastore.overview.commit()

    updated_overview = datastore.overview.get(id, as_obj=True)
    assert updated_overview.content == "Potato"
