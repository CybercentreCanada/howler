"""Integration tests for ILM index lifecycle management.

These tests require a running Elasticsearch instance.
They verify that ILM policies, index templates, and rollover aliases are
correctly set up against a real ES cluster.
"""

import logging
import random
import string
import time

import pytest

from howler.common.loader import DATASTORE_INDEX_PREFIX
from howler.datastore.collection import ESCollection
from howler.datastore.store import ESStore
from howler.odm.models.config import ILMIndexConfig

logger = logging.getLogger(__name__)


def _random_name():
    return "ilmtest_" + "".join(random.choices(string.ascii_lowercase, k=8))


@pytest.fixture(scope="module")
def es_store():
    """Connect to an ES instance, skip if unavailable."""
    try:
        store = ESStore()
        ESCollection.MAX_RETRY_BACKOFF = 0.5
        if not store.ping():
            pytest.skip("Could not connect to Elasticsearch")
        yield store
    except Exception:
        pytest.skip("Could not connect to Elasticsearch")


@pytest.fixture()
def ilm_collection(es_store, request):
    """Create an ILM-managed ESCollection and clean up afterwards."""
    name = _random_name()
    ilm_index_config = ILMIndexConfig(warm="30d", cold="90d")

    es_store.register(name, ilm_config=ilm_index_config)
    collection: ESCollection = getattr(es_store, name)

    def cleanup():
        logger.info("Cleaning up ILM collection %r", name)
        client = es_store.client

        # Delete all indices matching the collection name
        try:
            client.indices.delete(index=f"{DATASTORE_INDEX_PREFIX}-{name}-*", ignore_unavailable=True)
            logger.debug("Deleted indices %s-%s-*", DATASTORE_INDEX_PREFIX, name)
        except Exception:
            logger.warning("Failed to delete indices howler-%s-*", name, exc_info=True)

        try:
            client.indices.delete(index=f"{DATASTORE_INDEX_PREFIX}-{name}_hot", ignore_unavailable=True)
            logger.debug("Deleted index %s-%s_hot", DATASTORE_INDEX_PREFIX, name)
        except Exception:
            logger.warning("Failed to delete index howler-%s_hot", name, exc_info=True)

        # Delete alias if it exists
        try:
            client.indices.delete_alias(index="_all", name=f"{DATASTORE_INDEX_PREFIX}-{name}")
            logger.debug("Deleted alias %s-%s", DATASTORE_INDEX_PREFIX, name)
        except Exception:
            logger.warning("Failed to delete alias howler-%s", name, exc_info=True)

        # Delete ILM policy
        try:
            client.ilm.delete_lifecycle(name=f"{DATASTORE_INDEX_PREFIX}-{name}_policy")
            logger.debug("Deleted ILM policy %s-%s_policy", DATASTORE_INDEX_PREFIX, name)
        except Exception:
            logger.warning("Failed to delete ILM policy howler-%s_policy", name, exc_info=True)

        # Delete index template
        try:
            client.indices.delete_index_template(name=f"{DATASTORE_INDEX_PREFIX}-{name}_template")
            logger.debug("Deleted index template %s-%s_template", DATASTORE_INDEX_PREFIX, name)
        except Exception:
            logger.warning("Failed to delete index template howler-%s_template", name, exc_info=True)

        logger.info("Cleanup complete for ILM collection %r", name)

    request.addfinalizer(cleanup)
    return collection


@pytest.fixture()
def non_ilm_collection(es_store, request):
    """Create a standard (non-ILM) ESCollection and clean up afterwards."""
    name = _random_name()

    es_store.register(name)
    collection: ESCollection = getattr(es_store, name)

    def cleanup():
        logger.info("Cleaning up non-ILM collection %r", name)
        client = es_store.client
        # Delete all indices matching the collection name
        try:
            client.indices.delete(index=f"{DATASTORE_INDEX_PREFIX}-{name}_hot", ignore_unavailable=True)
            logger.debug("Deleted index %s-%s_hot", DATASTORE_INDEX_PREFIX, name)
        except Exception:
            logger.warning("Failed to delete index howler-%s_hot", name, exc_info=True)

        try:
            client.indices.delete_alias(index="_all", name=f"{DATASTORE_INDEX_PREFIX}-{name}")
            logger.debug("Deleted alias %s-%s", DATASTORE_INDEX_PREFIX, name)
        except Exception:
            logger.warning("Failed to delete alias howler-%s", name, exc_info=True)

        logger.info("Cleanup complete for non-ILM collection %r", name)

    request.addfinalizer(cleanup)
    return collection


class TestILMPolicyCreation:
    """Verify ILM policies are created correctly in ES."""

    def test_ilm_policy_exists(self, ilm_collection: ESCollection):
        """ILM policy should be created when collection is initialized."""
        assert ilm_collection._ilm_policy_exists()

    def test_ilm_policy_phases(self, ilm_collection: ESCollection, es_store: ESStore):
        """ILM policy should have hot, warm, and cold phases."""
        policy_name = f"{ilm_collection.name}_policy"
        response = es_store.client.ilm.get_lifecycle(name=policy_name)
        policy = response[policy_name]["policy"]
        phases = policy["phases"]

        assert "hot" in phases
        assert "rollover" in phases["hot"]["actions"]
        assert "warm" in phases
        assert "forcemerge" in phases["warm"]["actions"]
        assert phases["warm"]["min_age"] == "30d"
        assert "cold" in phases
        assert phases["cold"]["min_age"] == "90d"
        # No delete phase — retention cronjob handles deletion
        assert "delete" not in phases

    def test_ilm_policy_rollover_settings(self, ilm_collection: ESCollection, es_store: ESStore):
        """Rollover action should have the default max_age and max_primary_shard_size."""
        policy_name = f"{ilm_collection.name}_policy"
        response = es_store.client.ilm.get_lifecycle(name=policy_name)
        rollover = response[policy_name]["policy"]["phases"]["hot"]["actions"]["rollover"]

        assert rollover["max_age"] == "30d"
        assert rollover["max_primary_shard_size"] == "50gb"

    def test_no_readonly_in_warm_or_cold(self, ilm_collection: ESCollection, es_store: ESStore):
        """Warm and cold phases must NOT have readonly action."""
        policy_name = f"{ilm_collection.name}_policy"
        response = es_store.client.ilm.get_lifecycle(name=policy_name)
        phases = response[policy_name]["policy"]["phases"]

        assert "readonly" not in phases["warm"]["actions"]
        assert "readonly" not in phases["cold"].get("actions", {})


class TestILMIndexTemplateCreation:
    """Verify composable index templates are created correctly."""

    def test_index_template_exists(self, ilm_collection: ESCollection, es_store: ESStore):
        """Index template should exist after collection initialization."""
        template_name = f"{ilm_collection.name}_template"
        response = es_store.client.indices.get_index_template(name=template_name)
        templates = response["index_templates"]
        assert len(templates) == 1
        assert templates[0]["name"] == template_name

    def test_index_template_pattern(self, ilm_collection: ESCollection, es_store: ESStore):
        """Index template should match {name}-* pattern."""
        template_name = f"{ilm_collection.name}_template"
        response = es_store.client.indices.get_index_template(name=template_name)
        template = response["index_templates"][0]["index_template"]

        assert f"{ilm_collection.name}-*" in template["index_patterns"]

    def test_index_template_has_ilm_settings(self, ilm_collection: ESCollection, es_store: ESStore):
        """Index template should include lifecycle settings."""
        template_name = f"{ilm_collection.name}_template"
        response = es_store.client.indices.get_index_template(name=template_name)
        template = response["index_templates"][0]["index_template"]
        settings = template["template"]["settings"]["index"]

        assert settings["lifecycle"]["name"] == f"{ilm_collection.name}_policy"
        assert settings["lifecycle"]["rollover_alias"] == ilm_collection.name

    def test_index_template_has_mappings(self, ilm_collection: ESCollection, es_store: ESStore):
        """Index template should include field mappings."""
        template_name = f"{ilm_collection.name}_template"
        response = es_store.client.indices.get_index_template(name=template_name)
        template = response["index_templates"][0]["index_template"]

        assert "mappings" in template["template"]
        assert "id" in template["template"]["mappings"]["properties"]


class TestILMIndexBootstrap:
    """Verify that ILM indices and aliases are correctly bootstrapped."""

    def test_initial_index_created(self, ilm_collection: ESCollection, es_store: ESStore):
        """On fresh install, {name}-000001 should be created."""
        initial_index = f"{ilm_collection.name}-000001"
        assert es_store.client.indices.exists(index=initial_index)

    def test_alias_exists(self, ilm_collection: ESCollection, es_store: ESStore):
        """The collection alias should exist and point to the initial index."""
        assert es_store.client.indices.exists_alias(name=ilm_collection.name)

    def test_alias_is_write_index(self, ilm_collection: ESCollection, es_store: ESStore):
        """The initial index should be marked as is_write_index in the alias."""
        initial_index = f"{ilm_collection.name}-000001"
        aliases = es_store.client.indices.get_alias(index=initial_index)
        alias_info = aliases[initial_index]["aliases"][ilm_collection.name]
        assert alias_info.get("is_write_index") is True

    def test_index_has_ilm_settings(self, ilm_collection: ESCollection, es_store: ESStore):
        """The initial index should have lifecycle settings applied."""
        initial_index = f"{ilm_collection.name}-000001"
        settings = es_store.client.indices.get_settings(index=initial_index)
        index_settings = settings[initial_index]["settings"]["index"]

        assert index_settings["lifecycle"]["name"] == f"{ilm_collection.name}_policy"
        assert index_settings["lifecycle"]["rollover_alias"] == ilm_collection.name

    def test_no_hot_index_created(self, ilm_collection: ESCollection, es_store: ESStore):
        """The legacy _hot index should NOT be created for ILM collections."""
        hot_index = f"{ilm_collection.name}_hot"
        assert not es_store.client.indices.exists(index=hot_index)

    def test_index_name_updated(self, ilm_collection: ESCollection):
        """The collection's index_name should point to the ILM initial index."""
        assert ilm_collection.index_name == f"{ilm_collection.name}-000001"


class TestNonILMCollection:
    """Verify that non-ILM collections still work normally."""

    def test_hot_index_created(self, non_ilm_collection: ESCollection, es_store: ESStore):
        """Non-ILM collections should still use the _hot index naming."""
        hot_index = f"{non_ilm_collection.name}_hot"
        assert es_store.client.indices.exists(index=hot_index)

    def test_no_ilm_policy_created(self, non_ilm_collection: ESCollection):
        """Non-ILM collections should not have an ILM policy."""
        assert not non_ilm_collection._ilm_policy_exists()

    def test_alias_exists(self, non_ilm_collection: ESCollection, es_store: ESStore):
        """Non-ILM collections should still have their alias."""
        assert es_store.client.indices.exists_alias(name=non_ilm_collection.name)


class TestILMDataOperations:
    """Verify that data operations work correctly on ILM-managed indices."""

    def test_save_and_get(self, ilm_collection: ESCollection):
        """Documents can be saved and retrieved via the alias."""
        ilm_collection.save("doc1", {"field_s": "value1", "count_i": 42}, refresh="wait_for")
        result = ilm_collection.get("doc1")
        assert result["field_s"] == "value1"
        assert result["count_i"] == 42

    def test_search(self, ilm_collection: ESCollection):
        """Search through the alias should find documents."""
        ilm_collection.save("search_doc", {"field_s": "searchable", "count_i": 1}, refresh="wait_for")

        assert ilm_collection.search("field_s:searchable")["total"] >= 1

    def test_delete_by_query(self, ilm_collection: ESCollection):
        """delete_by_query should work through the alias across ILM indices."""
        ilm_collection.save("del1", {"field_s": "to_delete", "count_i": 1})
        ilm_collection.save("del2", {"field_s": "to_delete", "count_i": 2})
        ilm_collection.save("keep1", {"field_s": "to_keep", "count_i": 3}, refresh="wait_for")

        ilm_collection.delete_by_query("field_s:to_delete", refresh="true")

        time.sleep(0.1)

        assert ilm_collection.get_if_exists("del1") is None
        assert ilm_collection.get_if_exists("del2") is None
        assert ilm_collection.get_if_exists("keep1") is not None

    def test_update(self, ilm_collection: ESCollection):
        """Update operations should work on ILM-managed indices."""
        ilm_collection.save("upd1", {"field_s": "original", "count_i": 1}, refresh="wait_for")

        ilm_collection.update("upd1", [(ilm_collection.UPDATE_SET, "field_s", "updated")], refresh="true")

        time.sleep(0.1)

        result = ilm_collection.get("upd1")
        assert result["field_s"] == "updated"

    def test_stream_search(self, ilm_collection: ESCollection):
        """stream_search should work through the ILM alias."""
        bulk_plan = ilm_collection.get_bulk_plan()
        for i in range(5):
            bulk_plan.add_index_operation(f"stream_{i}", {"field_s": "streamable", "count_i": i})

        ilm_collection.bulk(bulk_plan, refresh="wait_for")

        items = list(ilm_collection.stream_search("field_s:streamable"))
        assert len(items) >= 5


class TestILMLegacyMigration:
    """Verify migration from legacy _hot index to ILM-managed index."""

    def test_migrate_from_hot_to_ilm(self, es_store: ESStore, request):
        """A legacy _hot index should be migrated to -000001 when ILM is enabled."""
        name = _random_name()
        full_name = f"{DATASTORE_INDEX_PREFIX}-{name}"
        hot_index = f"{full_name}_hot"
        ilm_initial = f"{full_name}-000001"

        def cleanup():
            logger.info("Cleaning up migration test collection %r", full_name)
            client = es_store.client
            for idx in [hot_index, ilm_initial]:
                try:
                    client.indices.delete(index=idx, ignore_unavailable=True)
                    logger.debug("Deleted index %s", idx)
                except Exception:
                    logger.warning("Failed to delete index %s", idx, exc_info=True)
            try:
                client.indices.delete_alias(index="_all", name=full_name)
                logger.debug("Deleted alias %s", full_name)
            except Exception:
                logger.warning("Failed to delete alias %s", full_name, exc_info=True)
            try:
                client.ilm.delete_lifecycle(name=f"{full_name}_policy")
                logger.debug("Deleted ILM policy %s_policy", full_name)
            except Exception:
                logger.warning("Failed to delete ILM policy %s_policy", full_name, exc_info=True)
            try:
                client.indices.delete_index_template(name=f"{full_name}_template")
                logger.debug("Deleted index template %s_template", full_name)
            except Exception:
                logger.warning("Failed to delete index template %s_template", full_name, exc_info=True)
            logger.info("Cleanup complete for migration test collection %r", full_name)

        request.addfinalizer(cleanup)

        # Step 1: Create a legacy _hot index manually with some data
        es_store.client.indices.create(
            index=hot_index,
            settings={"number_of_shards": 1, "number_of_replicas": 0},
        )
        es_store.client.indices.put_alias(index=hot_index, name=full_name)
        es_store.client.index(index=full_name, id="legacy_doc", document={"field_s": "from_hot"}, refresh=True)

        # Verify legacy setup
        assert es_store.client.indices.exists(index=hot_index)
        assert es_store.client.indices.exists_alias(name=full_name)

        # Step 2: Register with ILM config — should trigger migration
        ilm_index_config = ILMIndexConfig(warm="30d", cold="90d")
        es_store.register(name, ilm_config=ilm_index_config)
        collection: ESCollection = getattr(es_store, name)

        # Step 3: Verify migration results
        # The ILM initial index should exist
        assert es_store.client.indices.exists(index=ilm_initial)

        # The alias should point to the new ILM index
        aliases = es_store.client.indices.get_alias(index=ilm_initial)
        assert full_name in aliases[ilm_initial]["aliases"]

        # Data should still be accessible
        doc = collection.get("legacy_doc")
        assert doc is not None
        assert doc["field_s"] == "from_hot"

        # The collection's index_name should be updated
        assert collection.index_name == ilm_initial
