import json

import pytest
from conftest import get_api_data

from howler.datastore.howler_store import HowlerDatastore
from howler.odm.models.analytic import Analytic
from howler.odm.random_data import create_analytics, wipe_analytics


@pytest.fixture(scope="module")
def datastore(datastore_connection):
    ds = datastore_connection
    try:
        wipe_analytics(ds)
        create_analytics(ds)

        yield ds
    finally:
        wipe_analytics(ds)


def test_get_analytics(datastore: HowlerDatastore, login_session):
    session, host = login_session

    resp = get_api_data(session, f"{host}/api/v1/analytic")

    assert len(resp) == len(datastore.analytic.search("analytic_id:*")["items"])


def test_get_analytic(datastore: HowlerDatastore, login_session):
    session, host = login_session

    analytic_id = datastore.analytic.search("analytic_id:*")["items"][0]["analytic_id"]

    resp = get_api_data(session, f"{host}/api/v1/analytic/{analytic_id}")

    assert resp["analytic_id"] == analytic_id


def test_update_analytic(datastore: HowlerDatastore, login_session):
    session, host = login_session

    new_desc = "blah blah blah"

    analytic: Analytic = datastore.analytic.search("analytic_id:*")["items"][0]

    assert analytic.description != new_desc

    get_api_data(
        session,
        f"{host}/api/v1/analytic/{analytic.analytic_id}/",
        method="PUT",
        data=json.dumps({"description": new_desc}),
    )

    resp = get_api_data(session, f"{host}/api/v1/analytic/{analytic.analytic_id}")

    assert resp["description"] == new_desc


def test_change_ownership(datastore: HowlerDatastore, login_session):
    session, host = login_session

    analytic: Analytic = datastore.analytic.search("analytic_id:*")["items"][0]

    new_owner = "admin" if analytic.owner != "admin" else "user"

    get_api_data(
        session,
        f"{host}/api/v1/analytic/{analytic.analytic_id}/owner",
        method="POST",
        data=json.dumps({"username": new_owner}),
    )

    resp = get_api_data(session, f"{host}/api/v1/analytic/{analytic.analytic_id}")

    assert resp["owner"] == new_owner


def test_comments(datastore: HowlerDatastore, login_session):
    session, host = login_session

    analytic: Analytic = datastore.analytic.search("analytic_id:*")["items"][0]

    new_comments = []
    for c in analytic.comment:
        c["user"] = "admin"
        new_comments.append(c)

    analytic.comment = new_comments
    datastore.analytic.save(analytic.analytic_id, analytic)
    datastore.analytic.commit()

    resp = get_api_data(
        session,
        f"{host}/api/v1/analytic/{analytic.analytic_id}/comments",
        method="POST",
        data=json.dumps({"value": "potato"}),
    )

    assert len(resp["comment"]) == len(analytic.comment) + 1

    resp = get_api_data(
        session,
        f"{host}/api/v1/analytic/{analytic.analytic_id}/comments/{resp['comment'][0]['id']}",
        method="PUT",
        data=json.dumps({"value": "potato2"}),
    )

    assert any(comment["value"] == "potato2" for comment in resp["comment"])

    get_api_data(
        session,
        f"{host}/api/v1/analytic/{analytic.analytic_id}/comments",
        method="DELETE",
        data=json.dumps([resp["comment"][0]["id"]]),
    )

    final_analytic = get_api_data(session, f"{host}/api/v1/analytic/{analytic.analytic_id}")

    assert len(final_analytic["comment"]) == len(resp["comment"]) - 1


def test_favourite(datastore: HowlerDatastore, login_session):
    session, host = login_session

    uname = get_api_data(session, f"{host}/api/v1/user/whoami", method="GET")["username"]

    analytic: Analytic = datastore.analytic.search("analytic_id:*")["items"][0]

    get_api_data(
        session,
        f"{host}/api/v1/analytic/{analytic.analytic_id}/favourite",
        method="POST",
        data={},
    )

    datastore.user.commit()

    assert analytic.analytic_id in datastore.user.search(f"uname:{uname}")["items"][0]["favourite_analytics"]

    get_api_data(
        session,
        f"{host}/api/v1/analytic/{analytic.analytic_id}/favourite",
        method="DELETE",
    )

    datastore.user.commit()

    assert analytic.analytic_id not in datastore.user.search(f"uname:{uname}")["items"][0]["favourite_analytics"]


def test_delete(datastore: HowlerDatastore, login_session):
    session, host = login_session

    analytic: Analytic = datastore.analytic.search("_exists_:rule")["items"][0]

    get_api_data(
        session,
        f"{host}/api/v1/analytic/{analytic.analytic_id}",
        method="DELETE",
    )

    datastore.analytic.commit()

    assert not datastore.analytic.exists(analytic.analytic_id)
