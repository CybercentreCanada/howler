import pytest
from conftest import get_api_data

from howler.datastore.howler_store import HowlerDatastore
from howler.odm.random_data import create_users, wipe_hits

hit = {
    "howler": {
        "id": "test",
        "analytic": "test",
        "assignment": "user",
        "hash": "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bc",
        "score": "0",
        "status": "on-hold",
        "labels": {"assignments": []},
    },
}


@pytest.fixture(scope="module")
def datastore(datastore_connection: HowlerDatastore):
    try:
        wipe_hits(datastore_connection)
        create_users(datastore_connection)

        datastore_connection.hit.save(hit["howler"]["id"], hit)

        # Commit changes to DataStore
        datastore_connection.hit.commit()

        yield datastore_connection
    finally:
        wipe_hits(datastore_connection)


def test_get_hit(datastore: HowlerDatastore, login_session):
    """Test that etags work as expected when getting a hit"""
    session, host = login_session

    res = get_api_data(session, f"{host}/api/v1/hit/{hit['howler']['id']}/", raw=True)

    res = get_api_data(
        session,
        f"{host}/api/v1/hit/{hit['howler']['id']}/",
        headers={
            "If-Match": res.headers["ETag"],
            "content-type": "application/json",
        },
        raw=True,
    )

    assert res.status_code == 304


def test_get_user(datastore: HowlerDatastore, login_session):
    """Test that etags work as expected when getting a user"""
    session, host = login_session

    res = get_api_data(session, f"{host}/api/v1/user/user/", raw=True)

    res = get_api_data(
        session,
        f"{host}/api/v1/user/user/",
        headers={
            "If-Match": res.headers["ETag"],
            "content-type": "application/json",
        },
        raw=True,
    )

    assert res.status_code == 304
