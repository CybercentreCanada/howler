import hashlib
import random

import pytest
import requests
from conftest import UI_HOST

from howler_client.common.utils import ClientError


def test_add(client):
    uname = hashlib.sha256(random.randbytes(128)).hexdigest()
    user_data = {
        "name": "cool_guy",
        "uname": uname,
        "email": "cool_guy@gmail.com",
    }

    res = client.user.add(uname, user_data)
    assert res["success"]

    res = client.user(uname)
    assert res["uname"] == user_data["uname"]


def test_delete(client):
    # Classifications don't work when using the howler api random_model_obj(User) function, so we do it ourselves.
    data = requests.get(f"{UI_HOST}/api/v1/configs")
    unrestricted_classification = data.json()["api_response"]["c12nDef"]["UNRESTRICTED"]
    user_data = {
        "id": "soon_to_be_gone_user",
        "name": "soon_to_be_gone_guy",
        "uname": "xXsoon_to_be_goneXx",
        "email": "soon_to_be_gone_guy@gmail.com",
    }
    username = user_data["uname"]
    user_data["classification"] = unrestricted_classification
    client.user.add(username, user_data)

    assert client.user(username) is not None

    # assert client.user.delete(username) is None

    with pytest.raises(ClientError, match="does not exist"):
        client.user(username)


def test_get(client):
    res = client.user("admin")

    assert res["name"] == "Michael Scott"
    assert res["uname"] == "admin"


def test_list(client):
    res = client.user.list()
    assert "admin" in [x["uname"] for x in res["items"]]

    res = client.user.list(query="id:admin")
    assert "admin" in [x["uname"] for x in res["items"]]
    assert res["total"] == 1


def test_update(client):
    new_name = "new user name"

    user_id = "user"
    user_data = client.user(user_id)
    assert user_data is not None

    user_data["name"] = new_name
    res = client.user.update(user_id, user_data)
    assert res["success"]

    assert client.user(user_id)["name"] == new_name


def test_whoami(client):
    res = client.user.whoami()
    assert {
        "avatar",
        "classification",
        "email",
        "groups",
        "is_active",
        "is_admin",
        "name",
        "roles",
        "username",
    }.issubset(set(res.keys()))

    assert res["username"] == "admin"
