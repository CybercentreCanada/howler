"""Live-cluster integration tests for the Step-6 schema-model-driven datastore contract.

Requires a running Elasticsearch instance (skips otherwise). Uses a randomized, disposable
collection name for every test and always tears the index/alias down afterward; never touches
the shared/broad ``howler-*`` production-shaped indices used by other fixtures.
"""

from __future__ import annotations

import logging
import random
import string

import pytest

from howler.datastore.collection import ESCollection
from howler.datastore.store import ESStore
from howler.models import HowlerESModel, keyword, mapping, register_model
from howler.models import schema as new_schema

logger = logging.getLogger(__name__)


@register_model(index=True, store=True, id_field="key")
class LiveReconcileDoc(HowlerESModel):
    """A small top-level schema model dedicated to these live-cluster tests."""

    key: keyword()
    name: keyword(description="A plain, statically-typed field.")
    tags: mapping(keyword(), default={}, description="A dynamic-key mapping field.")


def _random_name() -> str:
    return "schematest_" + "".join(random.choices(string.ascii_lowercase, k=8))


@pytest.fixture(scope="module")
def es_store():
    try:
        store = ESStore()
        ESCollection.MAX_RETRY_BACKOFF = 0.5
        if not store.ping():
            pytest.skip("Could not connect to Elasticsearch")
        yield store
    except Exception:
        pytest.skip("Could not connect to Elasticsearch")


@pytest.fixture()
def schema_collection(es_store, request):
    """Register+create a randomized collection backed by ``LiveReconcileDoc``, then clean up."""
    name = _random_name()
    es_store.register(name, model_class=None, schema_model=LiveReconcileDoc)
    collection: ESCollection = getattr(es_store, name)

    def cleanup():
        logger.info("Cleaning up schema-model test collection %r", name)
        try:
            # This cluster enforces ``action.destructive_requires_name``, so wildcard/alias-only
            # deletes are rejected; delete the exact physical (non-ILM, plain ``_hot``) index.
            collection.datastore.client.indices.delete(index=f"{collection.name}_hot", ignore_unavailable=True)
        except Exception:
            logger.exception("Failed to clean up %r", name)

    request.addfinalizer(cleanup)
    return collection


def test_created_index_matches_generated_contract(schema_collection):
    """The live index's settings/mappings are compatible with ``howler.models.schema`` generation.

    Elasticsearch's mapping GET response omits explicitly-set-but-default values (e.g.
    ``"index": true``, ``"doc_values": true`` for a keyword field), so this compares field
    *names* and *types* rather than requiring byte-for-byte equality with the round-tripped
    mapping - the same "nested vs dotted representation" style tolerance called out for
    reconciliation: what matters is that the live index is compatible with the generated
    contract, not that raw JSON echoes back unchanged.
    """
    client = schema_collection.datastore.client
    live = client.indices.get(index=schema_collection.name)
    live_index = next(iter(live.values()))

    expected_mappings = new_schema.document_mapping(LiveReconcileDoc)
    assert set(live_index["mappings"]["properties"]) == set(expected_mappings["properties"])
    for field_name, expected_body in expected_mappings["properties"].items():
        live_body = live_index["mappings"]["properties"][field_name]
        assert live_body.get("type") == expected_body.get("type"), field_name
        if "enabled" in expected_body:
            assert live_body.get("enabled", True) == expected_body["enabled"], field_name

    live_template_keys = {next(iter(t)) for t in live_index["mappings"]["dynamic_templates"]}
    expected_template_keys = {next(iter(t)) for t in expected_mappings["dynamic_templates"]}
    assert live_template_keys == expected_template_keys

    expected_settings = new_schema.index_settings(
        LiveReconcileDoc, shards=schema_collection.shards, replicas=schema_collection.replicas
    )
    assert int(live_index["settings"]["index"]["number_of_shards"]) == expected_settings["index"]["number_of_shards"]
    assert (
        int(live_index["settings"]["index"]["mapping"]["total_fields"]["limit"])
        == expected_settings["index"]["mapping"]["total_fields"]["limit"]
    )


def test_fields_reflects_live_dynamic_mapping_children(schema_collection):
    """After indexing a document with a dynamic ``tags.*`` key, ``fields()`` reflects it live."""
    schema_collection.save("doc1", {"key": "doc1", "name": "hello", "tags": {"env": "prod"}})
    schema_collection.commit()

    fields = schema_collection.fields()

    assert fields["name"]["type"] == "keyword"
    assert fields["name"]["description"] == "A plain, statically-typed field."
    assert "tags" in fields
    assert fields["tags"]["description"] == "A dynamic-key mapping field."
    assert "tags.env" in fields


def test_check_fields_adds_missing_safe_field_on_a_manually_created_index(es_store):
    """A live index created *without* one schema field gets it added by reconciliation.

    ``ESCollection.__init__`` -> ``_ensure_collection`` -> ``_check_fields`` runs automatically
    at construction time, so the missing field is already reconciled by the time ``getattr``
    returns the collection; this asserts the end state and that the field is genuinely usable
    afterward (present, correctly typed, and not merely tolerated).
    """
    name = _random_name()
    reduced_mappings = new_schema.document_mapping(LiveReconcileDoc)
    reduced_mappings["properties"] = {
        key: value for key, value in reduced_mappings["properties"].items() if key != "name"
    }
    settings = new_schema.index_settings(LiveReconcileDoc, shards=1, replicas=0)

    from howler.common.loader import DATASTORE_INDEX_PREFIX

    index_name = f"{DATASTORE_INDEX_PREFIX}-{name}"
    es_store.client.indices.create(
        index=f"{index_name}_hot",
        mappings=reduced_mappings,
        settings=settings,
        aliases={index_name: {}},
    )
    try:
        es_store.register(name, model_class=None, schema_model=LiveReconcileDoc)
        collection: ESCollection = getattr(es_store, name)

        fields = collection.fields()
        assert "name" in fields
        assert fields["name"]["type"] == "keyword"

        live = es_store.client.indices.get(index=f"{index_name}_hot")
        assert "name" in next(iter(live.values()))["mappings"]["properties"]
    finally:
        es_store.client.indices.delete(index=f"{index_name}_hot", ignore_unavailable=True)


def test_check_fields_refuses_missing_dynamic_template_on_a_manually_created_index(es_store):
    """A live index missing the expected dynamic template for ``tags`` is refused, not "fixed"."""
    from howler.common.exceptions import HowlerValueError
    from howler.common.loader import DATASTORE_INDEX_PREFIX

    name = _random_name()
    mappings = new_schema.document_mapping(LiveReconcileDoc)
    mappings["dynamic_templates"] = [
        template for template in mappings["dynamic_templates"] if next(iter(template)) != "tags.*_tpl"
    ]
    settings = new_schema.index_settings(LiveReconcileDoc, shards=1, replicas=0)

    index_name = f"{DATASTORE_INDEX_PREFIX}-{name}"
    es_store.client.indices.create(
        index=f"{index_name}_hot",
        mappings=mappings,
        settings=settings,
        aliases={index_name: {}},
    )
    try:
        es_store.register(name, model_class=None, schema_model=LiveReconcileDoc)
        # Reconciliation runs during construction itself (``__init__`` -> ``_ensure_collection``
        # -> ``_check_fields``), so the refusal is raised here, not from a later explicit call.
        with pytest.raises(HowlerValueError, match="Refusing to add or change dynamic mapping templates"):
            getattr(es_store, name)
    finally:
        es_store.client.indices.delete(index=f"{index_name}_hot", ignore_unavailable=True)
