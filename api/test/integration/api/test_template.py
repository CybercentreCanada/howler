import json
from typing import Any

import pytest
from conftest import APIError, get_api_data

from howler.datastore.howler_store import HowlerDatastore
from howler.odm.random_data import create_templates, wipe_templates


@pytest.fixture(scope="module")
def datastore(datastore_connection):
    ds = datastore_connection
    try:
        create_templates(ds)

        yield ds
    finally:
        wipe_templates(ds)


# noinspection PyUnusedLocal
def test_add_template(datastore: HowlerDatastore, login_session):
    session, host = login_session

    template_data: dict[str, Any] = {}

    with pytest.raises(APIError) as err:
        get_api_data(
            session,
            f"{host}/api/v1/template/",
            method="POST",
            data=json.dumps(template_data),
        )

    assert "keys" in str(err.value)

    template_data["keys"] = ["howler.analytic", "event.id"]

    with pytest.raises(APIError) as err:
        get_api_data(
            session,
            f"{host}/api/v1/template/",
            method="POST",
            data=json.dumps(template_data),
        )

    assert "template.analytic" in str(err.value)

    template_data["analytic"] = "test"
    with pytest.raises(APIError) as err:
        get_api_data(
            session,
            f"{host}/api/v1/template/",
            method="POST",
            data=json.dumps(template_data),
        )

    assert "type" in str(err.value)

    template_data["type"] = "personal"
    resp = get_api_data(
        session,
        f"{host}/api/v1/template/",
        method="POST",
        data=json.dumps(template_data),
    )

    assert resp["owner"] == "admin"

    template_data["type"] = "global"
    resp = get_api_data(
        session,
        f"{host}/api/v1/template/",
        method="POST",
        data=json.dumps(template_data),
    )

    assert "owner" not in resp


# noinspection PyUnusedLocal
def test_get_templates(datastore, login_session):
    session, host = login_session

    resp = get_api_data(session, f"{host}/api/v1/template/")

    assert all(t["type"] == "global" or t["owner"] == "admin" for t in resp)


# noinspection PyUnusedLocal
def test_remove_template(datastore: HowlerDatastore, login_session):
    session, host = login_session

    datastore.template.commit()
    total = datastore.template.search("template_id:*")["total"]

    create_res = get_api_data(
        session,
        f"{host}/api/v1/template/",
        method="POST",
        data=json.dumps({"analytic": "testremove", "type": "global", "keys": ["howler.hash"]}),
    )

    datastore.template.commit()
    assert total + 1 == datastore.template.search("template_id:*")["total"]

    res = get_api_data(session, f"{host}/api/v1/template/{create_res['template_id']}/", method="DELETE")

    datastore.template.commit()
    assert res is None
    assert total == datastore.template.search("template_id:*")["total"]


def test_template_conflict(datastore: HowlerDatastore, login_session):
    session, host = login_session

    get_api_data(
        session,
        f"{host}/api/v1/template/",
        method="POST",
        data=json.dumps({"analytic": "test-conflict", "type": "global", "keys": ["howler.hash"]}),
    )

    datastore.template.commit()

    with pytest.raises(APIError) as err:
        get_api_data(
            session,
            f"{host}/api/v1/template/",
            method="POST",
            data=json.dumps({"analytic": "test-conflict", "type": "global", "keys": ["howler.hash"]}),
        )

    assert "already exists" in str(err.value)


# noinspection PyUnusedLocal
def test_set_template(datastore: HowlerDatastore, login_session):
    session, host = login_session

    id = datastore.template.search("owner:admin")["items"][0]["template_id"]
    resp = get_api_data(
        session,
        f"{host}/api/v1/template/{id}/",
        method="PUT",
        data=json.dumps(["event.id"]),
    )
    assert resp["keys"] == ["event.id"]

    datastore.template.commit()

    updated_template = datastore.template.get(id, as_obj=True)
    assert updated_template.keys == ["event.id"]
