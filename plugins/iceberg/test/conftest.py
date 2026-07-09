import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from howler.common import loader
from howler.config import config
from howler.datastore.howler_store import HowlerDatastore
from howler.datastore.store import ESCollection, ESStore
from howler.odm import random_data
from howler.odm.models.howler_data import Log

sys.path.insert(0, str(Path.cwd()))


@pytest.fixture(scope="session")
def datastore_connection():
    ESCollection.MAX_RETRY_BACKOFF = 0.5
    store = ESStore()
    ret_val = store.ping()
    if not ret_val:
        pytest.skip("Could not connect to datastore")

    ds: HowlerDatastore = HowlerDatastore(store)
    try:
        random_data.wipe_users(ds)
        random_data.create_users(ds)
        random_data.wipe_hits(ds)
        random_data.create_hits(ds, 20)
        yield ds

    finally:
        random_data.wipe_hits(ds)
        random_data.wipe_users(ds)


@pytest.fixture(scope="module")
def test_client():
    config.core.plugins.add("iceberg")

    from howler.app import app

    app.config.update({"TESTING": True})
    with app.test_client() as client:
        yield client


@pytest.fixture(scope="module")
def current_time():
    return datetime.now()


@pytest.fixture(scope="module")
def hits_with_timestamps(datastore_connection, current_time):
    lookups = loader.get_lookups()
    users = datastore_connection.user.search("*:*")["items"]

    hits = [random_data.generate_useful_hit(lookups, users) for _ in range(20)]

    for i, hit in enumerate(hits):
        # Set the timestamp of the hit to a specific number of days ago, cycling through 0 to 3 days ago
        days_ago = i % 4
        hit.timestamp = (current_time - timedelta(days=days_ago)).isoformat()
        hit.howler.log = [
            Log(
                {
                    "timestamp": (current_time - timedelta(days=4)).isoformat(),
                    "explanation": "test first log entry",
                    "user": "admin",
                }
            )
        ]

    for hit in hits[: len(hits) // 2]:
        hit.howler.log.append(
            Log(
                {
                    "timestamp": (current_time - timedelta(days=2)).isoformat(),
                    "explanation": "test log entry",
                    "user": "admin",
                }
            )
        )

    return hits


@pytest.fixture(scope="module", autouse=True)
def datastore_with_hits(datastore_connection, hits_with_timestamps):
    current_hits = datastore_connection.hit.search("*:*")["items"]

    random_data.wipe_hits(datastore_connection)
    for hit in hits_with_timestamps:
        datastore_connection.hit.save(hit.howler.id, hit)
    datastore_connection.hit.commit()

    yield datastore_connection

    datastore_connection.hit.delete_by_query(
        " OR ".join([f"howler.id:{hit.howler.id}" for hit in hits_with_timestamps])
    )
    for hit in current_hits:
        datastore_connection.hit.save(hit.howler.id, hit)
    datastore_connection.hit.commit()
