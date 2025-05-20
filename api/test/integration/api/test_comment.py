import json

import pytest
from conftest import get_api_data

from howler.datastore.howler_store import HowlerDatastore
from howler.odm.models.analytic import Analytic
from howler.odm.models.hit import Hit
from howler.odm.random_data import (
    create_hits,
    create_templates,
    wipe_hits,
    wipe_templates,
)


@pytest.fixture(scope="module")
def datastore(datastore_connection):
    ds = datastore_connection
    try:
        wipe_templates(ds)
        wipe_hits(ds)
        create_templates(ds)
        create_hits(ds, hit_count=2)

        yield ds
    finally:
        wipe_templates(ds)
        wipe_hits(ds)


def test_comments_analytic(datastore: HowlerDatastore, login_session):
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


def test_reactions_analytic(datastore: HowlerDatastore, login_session):
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
        f"{host}/api/v1/analytic/{analytic.analytic_id}/comments/{resp['comment'][0]['id']}/react",
        method="PUT",
        data=json.dumps({"type": "thumbsup"}),
    )

    assert any(comment["reactions"]["admin"] == "thumbsup" for comment in resp["comment"])

    resp = get_api_data(
        session,
        f"{host}/api/v1/analytic/{analytic.analytic_id}/comments/{resp['comment'][0]['id']}/react",
        method="DELETE",
        data=json.dumps([resp["comment"][0]["id"]]),
    )

    assert all(comment["reactions"].get("admin", None) is None for comment in resp["comment"])


def test_comments_hit(datastore: HowlerDatastore, login_session):
    session, host = login_session

    hit: Hit = datastore.hit.search("howler.id:*")["items"][0]

    new_comments = []
    for c in hit.howler.comment:
        c["user"] = "admin"
        new_comments.append(c)

    hit.howler.comment = new_comments
    datastore.hit.save(hit.howler.id, hit)
    datastore.hit.commit()

    resp = get_api_data(
        session,
        f"{host}/api/v1/hit/{hit.howler.id}/comments",
        method="POST",
        data=json.dumps({"value": "potato"}),
    )

    assert len(resp["howler"]["comment"]) == len(hit.howler.comment) + 1

    resp = get_api_data(
        session,
        f"{host}/api/v1/hit/{hit.howler.id}/comments/{resp['howler']['comment'][0]['id']}",
        method="PUT",
        data=json.dumps({"value": "potato2"}),
    )

    assert any(comment["value"] == "potato2" for comment in resp["howler"]["comment"])

    get_api_data(
        session,
        f"{host}/api/v1/hit/{hit.howler.id}/comments",
        method="DELETE",
        data=json.dumps([resp["howler"]["comment"][0]["id"]]),
    )

    final_hit = get_api_data(session, f"{host}/api/v1/hit/{hit.howler.id}")

    assert len(final_hit["howler"]["comment"]) == len(resp["howler"]["comment"]) - 1


def test_reactions_hit(datastore: HowlerDatastore, login_session):
    session, host = login_session

    hit: Hit = datastore.hit.search("howler.id:*")["items"][1]

    new_comments = []
    for c in hit.howler.comment:
        c["user"] = "admin"
        new_comments.append(c)

    hit.howler.comment = new_comments
    datastore.hit.save(hit.howler.id, hit)
    datastore.hit.commit()

    resp = get_api_data(
        session,
        f"{host}/api/v1/hit/{hit.howler.id}/comments/{hit.howler.comment[0].id}/react",
        method="PUT",
        data=json.dumps({"type": "thumbsup"}),
    )

    assert any(comment["reactions"]["admin"] == "thumbsup" for comment in resp["howler"]["comment"])

    resp = get_api_data(
        session,
        f"{host}/api/v1/hit/{hit.howler.id}/comments/{hit.howler.comment[0].id}/react",
        method="DELETE",
        data=json.dumps([hit.howler.comment[0].id]),
    )

    assert all(comment["reactions"].get("admin", None) is None for comment in resp["howler"]["comment"])
