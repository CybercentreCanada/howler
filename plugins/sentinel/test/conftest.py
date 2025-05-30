import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
load_dotenv(Path(__file__).parent / ".env.test")

# We append the plugin directory for howler to the python part
sys.path.insert(0, str(Path.cwd()))
from howler.config import config

config.core.plugins.append("sentinel")

import pytest
from howler.datastore.howler_store import HowlerDatastore
from howler.datastore.store import ESCollection, ESStore
from howler.odm import random_data


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
        yield ds

    finally:
        random_data.wipe_users(ds)
