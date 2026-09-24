import os
import sys
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv

load_dotenv()
load_dotenv(Path(__file__).parent / ".env.test")

# Prefer the checked-out API and plugins over installed copies in /etc/howler/plugins.
plugin_root = Path(__file__).resolve().parents[2]
api_path = plugin_root.parent / "api"
for source in (api_path, plugin_root / "evidence", plugin_root / "sentinel"):
    sys.path.insert(0, str(source))

# Importing the application inserts HWL_PLUGIN_DIRECTORY at the front of sys.path. Point it
# at the checkout rather than the older plugins installed under /etc/howler/plugins.
os.environ["HWL_PLUGIN_DIRECTORY"] = str(plugin_root)
# Every run owns a fresh schema-compatible index namespace, including application globals.
index_prefix = f"sentinel-test-{uuid4().hex}"
os.environ["HWL_DATASTORE_INDEX_PREFIX"] = index_prefix
from howler.config import config

config.core.plugins.add("evidence")
config.core.plugins.add("sentinel")

import pytest
from howler.datastore.howler_store import HowlerDatastore
from howler.datastore.store import ESCollection, ESStore
from howler.sample_data import random_data


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
        random_data.create_hits(ds, 20)
        yield ds

    finally:
        indices = store.client.indices.get(index=f"{index_prefix}-*", allow_no_indices=True)
        if indices:
            store.client.indices.delete(index=list(indices))
