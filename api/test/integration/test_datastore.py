import os
import random
import string
import time
import uuid
import warnings
from typing import Any

import pytest
from datemath import dm
from retrying import retry

from howler import odm
from howler.datastore.collection import ESCollection
from howler.datastore.exceptions import VersionConflictException
from howler.datastore.store import ESStore

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    test_map = {
        "test1": {
            "expiry_dt": dm("now-2d/m").isoformat().replace("+00:00", ".001Z"),
            "lvl_i": 400,
            "test1_s": "hello",
            "tags_ss": ["a", "b", "c"],
        },
        "test2": {
            "expiry_dt": dm("now-1d/m").isoformat().replace("+00:00", ".001Z"),
            "lvl_i": 100,
            "test2_s": "hello",
            "tags_ss": ["a", "b", "f"],
        },
        "test3": {
            "expiry_dt": dm("now/m").isoformat().replace("+00:00", ".001Z"),
            "lvl_i": 200,
            "test3_s": "hello",
            "tags_ss": ["a", "b", "e"],
        },
        "test4": {
            "expiry_dt": dm("now-2d/m").isoformat().replace("+00:00", ".001Z"),
            "lvl_i": 400,
            "test4_s": "hello",
            "tags_ss": ["a", "b", "d"],
        },
        "dict1": {
            "expiry_dt": dm("now-2d/m").isoformat().replace("+00:00", ".001Z"),
            "lvl_i": 400,
            "classification_s": "U",
            "test1_s": "hello",
            "tags_ss": [],
        },
        "dict2": {
            "expiry_dt": dm("now/m").isoformat().replace("+00:00", ".001Z"),
            "lvl_i": 100,
            "classification_s": "U",
            "test2_s": "hello",
            "tags_ss": [],
        },
        "dict3": {
            "expiry_dt": dm("now-3d/m").isoformat().replace("+00:00", ".001Z"),
            "lvl_i": 200,
            "classification_s": "C",
            "test3_s": "hello",
            "tags_ss": [],
        },
        "dict4": {
            "expiry_dt": dm("now-1d/m").isoformat().replace("+00:00", ".001Z"),
            "lvl_i": 400,
            "classification_s": "TS",
            "test4_s": "hello",
            "tags_ss": [],
        },
        "string": "A string!",
        "list": ["a", "list", "of", "string", 100],
        "int": 69,
        "to_update": {
            "counters": {"lvl_i": 100, "inc_i": 0, "dec_i": 100},
            "list": ["hello", "remove"],
            "map": {"a": 1},
        },
        "bulk_update": {
            "bulk_b": True,
            "map": {"a": 1},
            "counters": {"lvl_i": 100, "inc_i": 0, "dec_i": 100},
            "list": ["hello", "remove"],
        },
        "bulk_update2": {
            "bulk_b": True,
            "map": {"a": 1},
            "counters": {"lvl_i": 100, "inc_i": 0, "dec_i": 100},
            "list": ["hello", "remove"],
        },
        "delete1": {"delete_b": True, "lvl_i": 100},
        "delete2": {"delete_b": True, "lvl_i": 300},
        "delete3": {"delete_b": True, "lvl_i": 400},
        "delete4": {"delete_b": True, "lvl_i": 200},
    }


class SetupException(Exception):
    pass


# Retry setup up to 10 times with random wait between attempts
@retry(stop_max_attempt_number=10, wait_random_min=100, wait_random_max=500)
def setup_store(docstore: ESStore, request) -> ESCollection:
    """
    Set up a test ESCollection with test data. Cleans up after the test.
    """
    try:
        ret_val = docstore.ping()
        if ret_val:
            # Generate a random collection name
            collection_name = "".join(random.choices(string.ascii_lowercase, k=10))
            docstore.register(collection_name)
            collection = docstore.__getattr__(collection_name)
            request.addfinalizer(collection.wipe)

            # Remove any existing test data
            for k in test_map.keys():
                collection.delete(k)

            # Add all test data
            for k, v in test_map.items():
                collection.save(k, v)

            # Commit saved data
            collection.commit()

            return collection
    except ConnectionError:
        raise SetupException("Could not setup Datastore: %s" % docstore.__class__.__name__)

    raise SetupException("Could not setup Datastore: %s" % docstore.__class__.__name__)


@pytest.fixture(scope="module")
def es_connection(request):
    """
    Pytest fixture to provide a test ESCollection with test data.
    Cleans up indices and aliases after the test.
    """
    from howler.datastore.store import ESStore

    try:
        collection: ESCollection = setup_store(ESStore(), request)

        yield collection

        # Cleanup: delete alias and index after test
        collection.datastore.client.indices.delete_alias(index=f"{collection.name}_hot", name=collection.name)
        collection.datastore.client.indices.delete(index=f"{collection.name}_hot")
    except SetupException:
        return pytest.skip("Connection to the Elasticsearch server failed. This test cannot be performed...")


def _test_exists(c: ESCollection):
    """
    Test that all expected keys exist in the collection.

    Verifies the exists() method correctly identifies documents that are present
    in the collection by checking each key from the test_map.
    """
    assert c.exists("test1")
    assert c.exists("test2")
    assert c.exists("test3")
    assert c.exists("test4")
    assert c.exists("string")
    assert c.exists("list")
    assert c.exists("int")


def _test_get(c: ESCollection):
    """
    Test that all expected keys return the correct value.

    Validates the get() method retrieves documents correctly and returns
    data that matches what was originally stored in the test_map.
    """
    assert test_map.get("test1") == c.get("test1")
    assert test_map.get("test2") == c.get("test2")
    assert test_map.get("test3") == c.get("test3")
    assert test_map.get("test4") == c.get("test4")
    assert test_map.get("string") == c.get("string")
    assert test_map.get("list") == c.get("list")
    assert test_map.get("int") == c.get("int")


def _test_require(c: ESCollection):
    """
    Test the require() method for all expected keys.

    The require() method should behave similarly to get() but may have
    different error handling for missing documents. Validates that it
    returns the same data as stored in test_map.
    """
    # Test GET
    assert test_map.get("test1") == c.require("test1")
    assert test_map.get("test2") == c.require("test2")
    assert test_map.get("test3") == c.require("test3")
    assert test_map.get("test4") == c.require("test4")
    assert test_map.get("string") == c.require("string")
    assert test_map.get("list") == c.require("list")
    assert test_map.get("int") == c.require("int")


def _test_get_if_exists(c: ESCollection):
    """
    Test the get_if_exists() method for all expected keys.

    This method should return documents if they exist, or None if they don't.
    Since all test documents should exist, validates that the method returns
    the correct data matching test_map.
    """
    # Test GET
    assert test_map.get("test1") == c.get_if_exists("test1")
    assert test_map.get("test2") == c.get_if_exists("test2")
    assert test_map.get("test3") == c.get_if_exists("test3")
    assert test_map.get("test4") == c.get_if_exists("test4")
    assert test_map.get("string") == c.get_if_exists("string")
    assert test_map.get("list") == c.get_if_exists("list")
    assert test_map.get("int") == c.get_if_exists("int")


def _test_multiget(c: ESCollection):
    """
    Test multi-get functionality for both list and dictionary return types.

    The multiget() method should efficiently retrieve multiple documents at once.
    Tests both as_dictionary=False (returns list) and as_dictionary=True (returns dict)
    modes, and validates that empty key lists return empty results.
    """
    # TEST Multi-get
    raw = [test_map.get("test1"), test_map.get("int"), test_map.get("test2")]
    ds_raw = c.multiget(["test1", "int", "test2"], as_dictionary=False)
    for item in ds_raw:
        raw.remove(item)
    assert len(raw) == 0

    for k, v in c.multiget(["test1", "int", "test2"], as_dictionary=True).items():
        assert test_map[k] == v

    assert c.multiget([]) == {}


def _test_keys(c: ESCollection):
    """
    Test that all keys in the collection match the expected test_map keys.

    The keys() method should return all document IDs in the collection.
    Validates that the collection contains exactly the keys from test_map
    and no extra or missing keys.
    """
    # Test KEYS
    test_keys = list(test_map.keys())
    for k in c.keys():
        test_keys.remove(k)
    assert len(test_keys) == 0


def _test_update(c: ESCollection):
    """
    Test update operations including set, increment, decrement, append, remove, and delete.

    Tests the update() method with various operation types:
    - SET: Set field values
    - INC/DEC: Increment/decrement numeric values
    - APPEND: Add items to lists
    - APPEND_IF_MISSING: Add items only if not already present
    - REMOVE: Remove items from lists
    - DELETE: Remove entire fields from documents
    """
    # Test Update
    expected = {
        "counters": {"lvl_i": 666, "inc_i": 50, "dec_i": 50},
        "list": ["hello", "world!", "test_if_missing"],
        "map": {"b": 99},
    }
    operations = [
        (c.UPDATE_SET, "counters.lvl_i", 666),
        (c.UPDATE_INC, "counters.inc_i", 50),
        (c.UPDATE_DEC, "counters.dec_i", 50),
        (c.UPDATE_APPEND, "list", "world!"),
        (c.UPDATE_APPEND_IF_MISSING, "list", "test_if_missing"),
        (c.UPDATE_APPEND_IF_MISSING, "list", "world!"),
        (c.UPDATE_REMOVE, "list", "remove"),
        (c.UPDATE_DELETE, "map", "a"),
        (c.UPDATE_SET, "map.b", 99),
    ]
    assert c.update("to_update", operations)
    assert c.get("to_update") == expected


def _test_update_fails(c: ESCollection):
    """
    Test that update fails for non-existent keys, invalid operations, and version conflicts.

    Validates error handling in the update() method:
    - Updates to non-existent documents should fail
    - Updates with invalid field names should fail
    - Updates with incorrect version numbers should raise VersionConflictException
    """
    assert not c.update("to_update_doesnt_exist", [(c.UPDATE_SET, "map.b", 99)])
    assert not c.update(
        "to_update",
        [(c.UPDATE_SET, "RTGE$%^Y#$Gavsdfvbkl", "dafgkjbsdfkgjsbdnfgjkhsdfg")],
    )
    val = c.get("to_update", version=True)[1]

    with pytest.raises(VersionConflictException):
        assert not c.update("to_update", [(c.UPDATE_SET, "map.b", 99)], version=val.replace("1", "2"))


def _test_update_by_query(c: ESCollection):
    """
    Test update_by_query for bulk updates and ensure correct filtering logic.

    The update_by_query() method should update multiple documents that match
    a query. Tests both successful bulk updates and failed updates when
    filters don't match any documents.
    """
    # Test update_by_query
    expected = {
        "bulk_b": True,
        "counters": {"lvl_i": 666, "inc_i": 50, "dec_i": 50},
        "list": ["hello", "world!", "test_if_missing"],
        "map": {"b": 99},
    }
    operations = [
        (c.UPDATE_SET, "counters.lvl_i", 666),
        (c.UPDATE_INC, "counters.inc_i", 50),
        (c.UPDATE_DEC, "counters.dec_i", 50),
        (c.UPDATE_APPEND, "list", "world!"),
        (c.UPDATE_APPEND_IF_MISSING, "list", "test_if_missing"),
        (c.UPDATE_APPEND_IF_MISSING, "list", "world!"),
        (c.UPDATE_REMOVE, "list", "remove"),
        (c.UPDATE_DELETE, "map", "a"),
        (c.UPDATE_SET, "map.b", 99),
    ]
    assert c.update_by_query("bulk_b:true", operations)
    expected.update({})
    assert c.get("bulk_update") == expected
    assert c.get("bulk_update2") == expected

    assert not c.update_by_query("bulk_b:false", [], filters=["bulk_b:true"])


def _test_delete_by_query(c: ESCollection):
    """
    Test delete_by_query to ensure matching documents are deleted and count is correct.

    The delete_by_query() method should remove all documents matching a query.
    Tests that exactly 4 documents with delete_b:true are removed and that
    the final document count is correct. Includes retry logic for eventually
    consistent databases.
    """
    # Test Delete Matching
    key_len = len(list(c.keys()))
    c.delete_by_query("delete_b:true")
    c.commit()
    retry_count = 0
    # Leave time for eventually consistent DBs to be in sync
    while key_len - 4 != len(list(c.keys())):
        if retry_count == 5:
            break
        retry_count += 1
        time.sleep(0.5 * retry_count)
        c.commit()
    assert key_len - 4 == len(list(c.keys()))


def _test_fields(c: ESCollection):
    """
    Test that fields() method returns a non-empty field mapping.

    The fields() method should return the field schema/mapping for the collection,
    which is used to understand the structure and types of indexed fields.
    """
    assert c.fields() != {}


def _test_search(c: ESCollection):
    """
    Test search functionality with sorting, filtering, and field limiting.

    Tests the search() method with various parameters:
    - Basic wildcard search with sorting
    - Search with offset, row limits, filters, and field selection
    Validates that search results contain expected document IDs and fields.
    """
    for item in c.search("*:*", sort="id asc")["items"]:
        assert item["id"][0] in test_map
    for item in c.search(
        "*:*",
        offset=1,
        rows=1,
        filters="lvl_i:400",
        sort="id asc",
        fl="id,classification_s",
    )["items"]:
        assert item["id"][0] in test_map
        assert item.get("classification_s", None) is not None


def _test_group_search(c: ESCollection):
    """
    Test grouped_search for correct grouping, offset, row count, and total logic.

    The grouped_search() method groups search results by a field value.
    Tests both simple and complex grouped searches with different parameters
    to ensure proper grouping, pagination, and result structure.
    """
    gs_simple = c.grouped_search("lvl_i", fl="classification_s")
    assert gs_simple["offset"] == 0
    assert gs_simple["rows"] == 25
    assert gs_simple["total"] == 8
    assert len(gs_simple["items"]) == 3
    total = 0
    for item in gs_simple["items"]:
        assert "value" in item
        assert isinstance(item["value"], int)
        assert "total" in item
        assert isinstance(item["total"], int)
        assert "items" in item
        assert isinstance(item["items"], list)
        total += item["total"]
    assert total == gs_simple["total"]

    gs_complex = c.grouped_search("lvl_i", fl="classification_s", offset=1, rows=2, sort="lvl_i desc")
    assert gs_complex["offset"] == 1
    assert gs_complex["rows"] == 2
    assert gs_complex["total"] == 8
    assert len(gs_complex["items"]) == 2
    total = 0
    for item in gs_complex["items"]:
        assert "value" in item
        assert isinstance(item["value"], int)
        assert "total" in item
        assert isinstance(item["total"], int)
        assert "items" in item
        assert isinstance(item["items"], list)
        total += item["total"]
    assert total <= gs_complex["total"]


def _test_deepsearch(c: ESCollection):
    """
    Test deep paging search to ensure all items are retrieved and match expected keys.

    Deep paging allows iterating through large result sets without traditional offset/limit
    pagination. Tests that all documents can be retrieved using deep paging and that
    the total count matches regular search results.
    """
    res = []
    deep_paging_id = "*"
    while True:
        s_data = c.search("*:*", rows=5, deep_paging_id=deep_paging_id)
        res.extend(s_data["items"])
        if len(res) == s_data["total"] or len(s_data["items"]) == 0:
            break
        deep_paging_id = s_data["next_deep_paging_id"]

    assert len(res) == c.search("*:*", sort="id asc")["total"]
    for item in res:
        assert item["id"][0] in test_map


def _test_streamsearch(c: ESCollection):
    """
    Test stream_search for correct filtering and field selection.

    Stream search provides an iterator interface for search results, useful for
    processing large result sets efficiently. Tests that the stream returns
    expected documents with proper filtering and field selection.
    """
    items = list(c.stream_search("classification_s:*", filters="lvl_i:400", fl="id,classification_s"))
    assert len(items) > 0
    for item in items:
        assert item["id"][0] in test_map
        assert item.get("classification_s", None) is not None


def _test_histogram(c: ESCollection):
    """
    Test histogram aggregation for integer and date fields, checking value types and counts.

    Histogram aggregation groups data into buckets for analysis. Tests both
    numeric histograms (for integer fields) and date histograms (for datetime fields)
    to ensure proper bucketing and count aggregation.
    """
    h_int = c.histogram("lvl_i", 0, 1000, 100, mincount=2)
    assert len(h_int) > 0
    for k, v in h_int.items():
        assert isinstance(k, int)
        assert isinstance(v, int)
        assert v > 0

    h_date = c.histogram(
        "expiry_dt",
        "{n}-10{d}/{d}".format(n=c.datastore.now, d=c.datastore.day),
        "{n}+10{d}/{d}".format(n=c.datastore.now, d=c.datastore.day),
        "+1{d}".format(d=c.datastore.day),
        mincount=2,
    )
    assert len(h_date) > 0
    for k, v in h_date.items():
        assert isinstance(k, str)
        assert "T00:00:00" in k
        assert k.endswith("Z")
        assert isinstance(v, int)
        assert v > 0


def _test_facet(c: ESCollection):
    """
    Test facet aggregation for classification_s field, ensuring correct keys and counts.

    Facet aggregation counts the occurrences of different values in a field.
    Tests that the facet operation returns expected classification values
    (U, C, TS) with positive counts.
    """
    facets = c.facet("classification_s")
    assert len(facets) > 0
    for k, v in facets.items():
        assert k in ["U", "C", "TS"]
        assert isinstance(v, int)
        assert v > 0


def _test_stats(c: ESCollection):
    """
    Test stats aggregation for lvl_i field, checking all expected statistics are present and valid.

    Stats aggregation computes statistical measures (count, min, max, avg, sum) for numeric fields.
    Tests that all expected statistics are returned with positive values for the lvl_i field.
    """
    stats = c.stats("lvl_i")
    assert len(stats) > 0
    for k, v in stats.items():
        assert k in ["count", "min", "max", "avg", "sum"]
        assert isinstance(v, (int, float))
        assert v > 0


TEST_FUNCTIONS = [
    (_test_exists, "exists"),
    (_test_get, "get"),
    (_test_require, "require"),
    (_test_get_if_exists, "get_if_exists"),
    (_test_multiget, "multiget"),
    (_test_keys, "keys"),
    (_test_update, "update"),
    (_test_update_fails, "update_fails"),
    (_test_update_by_query, "update_by_query"),
    (_test_delete_by_query, "delete_by_query"),
    (_test_fields, "fields"),
    (_test_search, "search"),
    (_test_group_search, "group_search"),
    (_test_deepsearch, "deepsearch"),
    (_test_streamsearch, "streamsearch"),
    (_test_histogram, "histogram"),
    (_test_facet, "facet"),
    (_test_stats, "stats"),
]


# Parametrize test_es to run all test functions in TEST_FUNCTIONS
@pytest.mark.parametrize("function", [f[0] for f in TEST_FUNCTIONS], ids=[f[1] for f in TEST_FUNCTIONS])
def test_es(es_connection: ESCollection, function):
    # Only run the test if the connection is available
    if es_connection:
        function(es_connection)


@pytest.fixture
def reduced_scroll_cursors(es_connection: ESCollection):
    """
    Reduce the max_open_scroll_context setting to make scroll cursor exhaustion tests faster.
    This helps trigger and test scroll cursor limits more quickly, especially on CI servers.
    """
    settings = es_connection.datastore.client.cluster.get_settings()

    old_value = 500
    # Ensure the transient search settings exist
    if "search" not in settings["transient"]:
        settings["transient"]["search"] = {}
    else:
        old_value = settings["transient"]["search"].get("max_open_scroll_context", old_value)
    # Set a low limit for open scroll contexts
    settings["transient"]["search"]["max_open_scroll_context"] = 5

    try:
        es_connection.datastore.client.cluster.put_settings(**settings)
        yield
    finally:
        # Restore the original scroll context limit after the test
        settings["transient"]["search"]["max_open_scroll_context"] = old_value
        es_connection.datastore.client.cluster.put_settings(**settings)


def test_empty_cursor_exhaustion(es_connection: ESCollection, reduced_scroll_cursors):
    """Test that repeated empty searches with deep paging do not leak scroll cursors."""
    for _ in range(20):
        result = es_connection.search('id: "TEST STRING THAT IS NOT AN ID"', deep_paging_id="*")
        assert result["total"] == 0


def test_short_cursor_exhaustion(es_connection: ESCollection, reduced_scroll_cursors):
    """Test that repeated short searches with deep paging do not leak scroll cursors."""
    result = es_connection.search("*:*")
    doc = result["items"][0]["id"][0]
    query = f"id: {doc}"

    for _ in range(20):
        result = es_connection.search(query, rows=2, deep_paging_id="*")
        assert result["total"] == 1


def test_atomic_save(es_connection: ESCollection):
    """Save a new document atomically, then try to save it again and detect the failure."""
    unique_id = uuid.uuid4().hex
    data = {"id": unique_id, "cats": "good"}

    # Verify the document is new
    no_data, version = es_connection.get_if_exists(unique_id, as_obj=False, version=True)
    assert no_data is None
    assert version is not None

    # Save atomically with version set
    es_connection.save(unique_id, data, version=version)

    # Make sure we can't save again with the same 'version'
    with pytest.raises(VersionConflictException):
        es_connection.save(unique_id, data, version=version)

    # Get the data, which exists now
    new_data, version = es_connection.get_if_exists(unique_id, as_obj=False, version=True)
    assert new_data is not None

    # Overwrite with real version
    es_connection.save(unique_id, data, version=version)

    # But it should only work once
    with pytest.raises(VersionConflictException):
        es_connection.save(unique_id, data, version=version)


@pytest.mark.parametrize(
    "shards", [pytest.param(1, id="shrink"), pytest.param(2, id="match"), pytest.param(4, id="grow")]
)
def test_fix_shards(es_connection: ESCollection, shards: int):
    """Test the fix_shards function by creating an index with incorrect shard count and fixing it."""
    # Create a unique test collection name to avoid conflicts
    os.environ["ELASTIC_DEFAULT_SHARDS"] = str(shards)
    test_collection_name = f"test_fix_shards_{uuid.uuid4().hex[:8]}"

    try:
        # Store original shard count from the test collection configuration
        incorrect_shards = 2

        # Manually create an index with incorrect shard count
        test_index_name = f"howler-{test_collection_name}"

        # Create index with incorrect number of shards
        index_settings = {
            "number_of_shards": incorrect_shards,
            "number_of_replicas": 0,  # Use 0 replicas for faster testing
        }

        # Create the index manually
        es_connection.datastore.client.indices.create(index=f"{test_index_name}_hot", settings=index_settings)

        # Create alias to make it look like a proper collection
        es_connection.datastore.client.indices.put_alias(index=f"{test_index_name}_hot", name=test_index_name)

        assert es_connection.datastore.client.indices.exists_alias(name=test_index_name)

        # Register and create a new collection instance for testing
        es_connection.datastore.register(test_collection_name)
        test_collection: ESCollection = getattr(es_connection.datastore, test_collection_name)

        assert test_collection.shards == shards

        # Verify the index was created with incorrect shard count
        current_settings = test_collection.with_retries(
            test_collection.datastore.client.indices.get_settings, index=f"{test_index_name}_hot"
        )

        current_shard_count = int(current_settings[f"{test_index_name}_hot"]["settings"]["index"]["number_of_shards"])
        assert current_shard_count == incorrect_shards, f"Expected {incorrect_shards} shards, got {current_shard_count}"

        # Add some test data to ensure data preservation during shard fixing
        test_data = {"test_field": "test_value", "timestamp": time.time()}
        test_collection.save("test_doc", test_data)
        test_collection.commit()

        # Verify data exists before fixing
        retrieved_data = test_collection.get("test_doc")
        assert retrieved_data["test_field"] == "test_value"

        # Now call fix_shards to correct the shard count
        test_collection.fix_shards()

        # Wait a moment for the operation to complete
        test_collection.commit()

        # Verify the shard count has been corrected
        # Get the current index (it might have changed after fix_shards)
        current_alias = test_collection._get_current_alias(test_collection.name)
        assert current_alias

        final_settings = test_collection.with_retries(
            test_collection.datastore.client.indices.get_settings, index=current_alias
        )

        final_shard_count = int(final_settings[current_alias]["settings"]["index"]["number_of_shards"])
        assert final_shard_count == shards, f"Expected {shards} shards after fix, got {final_shard_count}"

        # Verify data still exists after fixing
        retrieved_data_after = test_collection.get("test_doc")
        assert retrieved_data_after["test_field"] == "test_value"

    except Exception:
        raise
    finally:
        # Clean up: delete the test index and alias
        try:
            # Delete any aliases first
            if test_collection.with_retries(
                test_collection.datastore.client.indices.exists_alias, name=test_collection.name
            ):
                test_collection.with_retries(
                    test_collection.datastore.client.indices.delete_alias, index="_all", name=test_collection.name
                )

            # Delete all indices that match our test pattern
            indices_to_delete = []
            all_indices = test_collection.with_retries(
                test_collection.datastore.client.indices.get, index=f"{test_collection.name}*"
            )

            for index_name in all_indices.keys():
                if test_collection_name in index_name:
                    indices_to_delete.append(index_name)

            for index_name in indices_to_delete:
                if test_collection.with_retries(test_collection.datastore.client.indices.exists, index=index_name):
                    test_collection.with_retries(test_collection.datastore.client.indices.delete, index=index_name)

        except Exception:
            # Silently ignore cleanup errors to avoid failing the test
            pass


@pytest.mark.parametrize("replicas", [pytest.param(0, id="under"), pytest.param(2, id="over")])
def test_fix_replicas(es_connection: ESCollection, replicas: int):
    """Test the fix_replicas function by creating an index with incorrect replica count and fixing it."""
    # Create a unique test collection name to avoid conflicts
    os.environ["ELASTIC_DEFAULT_REPLICAS"] = str(replicas)
    test_collection_name = f"test_fix_replicas_{uuid.uuid4().hex[:8]}"

    try:
        # Store original replica count from the test collection configuration
        incorrect_replicas = 1 if replicas != 1 else 2  # Make sure it's different from target

        # Manually create an index with incorrect replica count
        test_index_name = f"howler-{test_collection_name}"

        # Create index with incorrect number of replicas
        index_settings = {
            "number_of_shards": 1,  # Keep shards simple for this test
            "number_of_replicas": incorrect_replicas,
        }

        # Create the index manually
        es_connection.datastore.client.indices.create(index=f"{test_index_name}_hot", settings=index_settings)

        # Create alias to make it look like a proper collection
        es_connection.datastore.client.indices.put_alias(index=f"{test_index_name}_hot", name=test_index_name)

        assert es_connection.datastore.client.indices.exists_alias(name=test_index_name)

        # Register and create a new collection instance for testing
        es_connection.datastore.register(test_collection_name)
        test_collection: ESCollection = getattr(es_connection.datastore, test_collection_name)

        assert test_collection.replicas == replicas

        # Verify the index was created with incorrect replica count
        current_settings = test_collection.with_retries(
            test_collection.datastore.client.indices.get_settings, index=f"{test_index_name}_hot"
        )

        current_replica_count = int(
            current_settings[f"{test_index_name}_hot"]["settings"]["index"]["number_of_replicas"]
        )
        assert (
            current_replica_count == incorrect_replicas
        ), f"Expected {incorrect_replicas} replicas, got {current_replica_count}"

        # Add some test data to ensure data preservation during replica fixing
        test_data = {"test_field": "test_value", "timestamp": time.time()}
        test_collection.save("test_doc", test_data)
        test_collection.commit()

        # Verify data exists before fixing
        retrieved_data = test_collection.get("test_doc")
        assert retrieved_data["test_field"] == "test_value"

        # Now call fix_replicas to correct the replica count
        result = test_collection.fix_replicas()
        assert result is True, "fix_replicas should return True on success"

        # Wait a moment for the operation to complete
        test_collection.commit()

        # Verify the replica count has been corrected
        final_settings = test_collection.with_retries(
            test_collection.datastore.client.indices.get_settings, index=test_collection.index_name
        )

        final_replica_count = int(final_settings[test_collection.index_name]["settings"]["index"]["number_of_replicas"])
        assert final_replica_count == replicas, f"Expected {replicas} replicas after fix, got {final_replica_count}"

        # Verify data still exists after fixing
        retrieved_data_after = test_collection.get("test_doc")
        assert retrieved_data_after["test_field"] == "test_value"

    except Exception:
        raise
    finally:
        # Clean up: delete the test index and alias
        try:
            # Delete any aliases first
            if test_collection.with_retries(
                test_collection.datastore.client.indices.exists_alias, name=test_collection.name
            ):
                test_collection.with_retries(
                    test_collection.datastore.client.indices.delete_alias, index="_all", name=test_collection.name
                )

            # Delete all indices that match our test pattern
            indices_to_delete = []
            all_indices = test_collection.with_retries(
                test_collection.datastore.client.indices.get, index=f"{test_collection.name}*"
            )

            for index_name in all_indices.keys():
                if test_collection_name in index_name:
                    indices_to_delete.append(index_name)

            for index_name in indices_to_delete:
                if test_collection.with_retries(test_collection.datastore.client.indices.exists, index=index_name):
                    test_collection.with_retries(test_collection.datastore.client.indices.delete, index=index_name)

        except Exception:
            # Silently ignore cleanup errors to avoid failing the test
            pass


@odm.model(index=True)
class Test1(odm.Model):
    field_1 = odm.Keyword(default="default")
    field_2 = odm.Keyword()
    field_3 = odm.Keyword(optional=True)


@odm.model(index=True)
class Test2(odm.Model):
    field_2 = odm.Keyword()
    field_3 = odm.Integer(default=1)


def test_reindex(es_connection: ESCollection):
    # Create a unique test collection name to avoid conflicts
    test_collection_name = f"test_fix_replicas_{uuid.uuid4().hex[:8]}"

    # Register and create a new collection instance using Test1 model
    es_connection.datastore.register(test_collection_name, Test1)
    test_collection: ESCollection = getattr(es_connection.datastore, test_collection_name)

    # Add two documents using Test1 model
    test_data: Any = Test1({"field_1": "example", "field_2": "example", "field_3": "example"})
    test_collection.save("example", test_data)
    test_data = Test1({"field_1": "example2", "field_2": "example2"})
    test_collection.save("example2", test_data)
    test_collection.commit()

    # Ensure both documents are present
    assert test_collection.search("field_2:*")["total"] == 2

    # Remove the collection from the registry to simulate a model change
    es_connection.datastore._collections.pop(test_collection_name)

    # Register the same collection name with a new model (Test2)
    es_connection.datastore.register(test_collection_name, Test2)
    ESCollection.IGNORE_ENSURE_COLLECTION = True  # Temporarily ignore collection checks
    test_collection: ESCollection = getattr(es_connection.datastore, test_collection_name)

    # Reindex the collection to migrate data to the new model
    test_collection.reindex()
    test_collection._ensure_collection()
    ESCollection.IGNORE_ENSURE_COLLECTION = False  # Restore collection checks

    # Add a new document using Test2 model
    test_data = Test2({"field_2": "example3", "field_3": 2})
    test_collection.save("example3", test_data)
    test_collection.commit()

    # Only two documents should remain after reindex (old model docs may be dropped)
    assert test_collection.search("field_2:*")["total"] == 2

    # The first document ("example") should be gone, "example2" should remain
    assert test_collection.get("example", as_obj=False) is None
    assert test_collection.get("example2", as_obj=False) is not None

    # "example2" should still have field_1 (from old model), "example3" should not (new model)
    assert "field_1" in test_collection.get("example2", as_obj=False)
    assert "field_1" not in test_collection.get("example3", as_obj=False)

    # Check field values for "example2" and "example3"
    assert test_collection.get("example2", as_obj=False)["field_2"] == "example2"
    assert test_collection.get("example2")["field_3"] == 1  # default value from Test2

    assert test_collection.get("example3", as_obj=False)["field_2"] == "example3"
    assert test_collection.get("example3", as_obj=False)["field_3"] == 2

    # "example1" should not exist
    assert test_collection.get("example1") is None

    # Returned objects should be instances of Test2
    assert isinstance(test_collection.get("example2"), Test2)
    assert isinstance(test_collection.get("example3"), Test2)

    # Accessing field_1 on Test2 model should raise, since it's not defined
    with pytest.raises(Exception):
        test_collection.get("example2").field_1
