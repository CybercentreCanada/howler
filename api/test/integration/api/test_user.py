import json
import random

import pytest
from conftest import get_api_data

from howler.odm.random_data import create_users, wipe_users

AVATAR = "AVATAR!"
NUM_USERS = 5
user_list = []


@pytest.fixture(scope="module")
def datastore(datastore_connection):
    global user_list
    ds = datastore_connection
    try:
        wipe_users(ds)
        create_users(ds)

        for x in range(NUM_USERS):
            u = ds.user.get("user")
            u.uname = f"test_{x+1}"
            ds.user.save(u.uname, u)
            ds.user_avatar.save(u.uname, AVATAR)
            user_list.append(u.uname)

        ds.user.commit()

        yield ds
    finally:
        wipe_users(ds)
        create_users(ds)


# noinspection PyUnusedLocal
def test_add_user(datastore, login_session):
    session, host = login_session

    u = datastore.user.get("user")
    u.uname = "TEST_ADD"

    resp = get_api_data(
        session,
        f"{host}/api/v1/user/{u.uname}/",
        method="POST",
        data=json.dumps(u.as_primitives()),
    )
    assert resp["success"]

    datastore.user.commit()
    new_user = datastore.user.get(u.uname)
    assert new_user == u


# noinspection PyUnusedLocal
def test_get_user(datastore, login_session):
    session, host = login_session
    username = random.choice(user_list)

    resp = get_api_data(session, f"{host}/api/v1/user/{username}/")
    new_user = datastore.user.get(username, as_obj=False)

    assert resp["name"] == new_user["name"]
    assert resp["uname"] == new_user["uname"]


# noinspection PyUnusedLocal
def test_get_user_avatar(datastore, login_session):
    session, host = login_session
    username = random.choice(user_list)

    resp = get_api_data(session, f"{host}/api/v1/user/avatar/{username}/")
    assert resp == AVATAR


# noinspection PyUnusedLocal
def test_remove_user(datastore, login_session):
    session, host = login_session
    username = random.choice(user_list)
    user_list.remove(username)

    get_api_data(session, f"{host}/api/v1/user/{username}/", method="DELETE")

    assert datastore.user.get(username) is None
    assert datastore.user_avatar.get(username) is None


# noinspection PyUnusedLocal
def test_set_user(datastore, login_session):
    session, host = login_session
    username = random.choice(user_list)

    u = datastore.user.get("user").as_primitives()
    u["uname"] = username

    resp = get_api_data(session, f"{host}/api/v1/user/{username}/", method="PUT", data=json.dumps(u))
    assert resp["success"]

    datastore.user.commit()

    new_user = datastore.user.get(username, as_obj=False)
    for k in ["apikeys", "password"]:
        u.pop(k)
        new_user.pop(k)

    for k in u.keys():
        assert u[k] == new_user[k]


# noinspection PyUnusedLocal
def test_set_user_avatar(datastore, login_session):
    session, host = login_session

    new_avatar = "NEW AVATAR@!"

    resp = get_api_data(session, f"{host}/api/v1/user/avatar/admin/", method="POST", data=new_avatar)
    assert resp["success"]

    datastore.user_avatar.commit()
    assert new_avatar == datastore.user_avatar.get("admin")
