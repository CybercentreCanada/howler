import pytest
from conftest import APIError, get_api_data

from howler.config import config
from howler.datastore.howler_store import HowlerDatastore


# noinspection PyUnusedLocal
def test_get_user(datastore_connection: HowlerDatastore, login_session):
    if not config.ui.enforce_quota:
        pytest.skip("config.ui.enforce_quota is set to false, skipping")

    data = datastore_connection.user.get("admin")
    data["api_quota"] = 0
    datastore_connection.user.save("admin", data)

    with pytest.raises(APIError):
        session, host = login_session
        resp = get_api_data(session, f"{host}/api/v1/user/user/")
        new_user = datastore_connection.user.get("user", as_obj=False)

        assert resp["name"] == new_user["name"]
        assert resp["uname"] == new_user["uname"]

    data["api_quota"] = 25
    datastore_connection.user.save("admin", data)
