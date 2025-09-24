import pytest
from conftest import get_api_data

from howler.common.logging import get_logger
from howler.cronjobs.view_cleanup import execute
from howler.odm.random_data import create_users, create_views, wipe_users, wipe_views

logger = get_logger(__file__)


AVATAR = "AVATAR!"


@pytest.fixture(scope="module")
def datastore(datastore_connection):
    global user
    ds = datastore_connection
    try:
        wipe_users(ds)
        wipe_views(ds)

        create_users(ds)
        create_views(ds)

        u = ds.user.get("user")

        # Grab a valid view to ensure only bad pinned views are cleared
        view = ds.view.search("*:*", rows=1)["items"][0]
        u.uname = "test_user"
        u.dashboard.append(
            {"entry_id": view.view_id, "type": "view", "config": f'{{"limit":3,"viewId":{view.view_id}}}'}
        )
        u.dashboard.append(
            {
                "entry_id": "7h1515n074r34lv13w",
                "type": "view",
                "config": '{"limit":3,"viewId":"7h1515n074r34lv13w"}',
            }
        )
        ds.user.save(u.uname, u)
        ds.user_avatar.save(u.uname, AVATAR)

        ds.user.commit()

        yield ds
    finally:
        wipe_users(ds)
        wipe_views(ds)
        create_users(ds)
        create_views(ds)


# noinspection PyUnusedLocal
def test_view_cleanup(datastore, login_session):
    session, host = login_session
    username = "test_user"

    resp = get_api_data(session, f"{host}/api/v1/user/{username}/")
    new_user = datastore.user.get(username, as_obj=False)

    assert resp["uname"] == new_user["uname"]
    assert len(resp["dashboard"]) == 2

    execute()  # Executes the view_cleanup cronjob

    resp = get_api_data(session, f"{host}/api/v1/user/{username}/")
    assert len(resp["dashboard"]) == 1  # Our non-existent view is removed but our valid one remains
