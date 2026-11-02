from __future__ import annotations

from copy import deepcopy
from uuid import uuid4

import elasticsearch
import pytest

from howler.common.exceptions import HowlerRuntimeError
from howler.datastore import collection as collection_module
from howler.datastore.collection import ESCollection
from howler.datastore.exceptions import DataStoreException
from howler.datastore.howler_store import HowlerDatastore
from howler.datastore.migrations import case_insensitive_metadata as migration_module
from howler.datastore.migrations.case_insensitive_metadata import COLLECTION_NAMES, CaseInsensitiveMetadataMigration
from howler.datastore.migrations.runner import run_migrations
from howler.datastore.store import ESStore
from howler.odm.models.action import Action
from howler.odm.models.config import ILMIndexConfig
from howler.odm.models.dossier import Dossier
from howler.odm.models.overview import Overview
from howler.odm.models.template import Template
from howler.odm.models.view import View

MODEL_CLASSES = {
    "view": View,
    "action": Action,
    "dossier": Dossier,
    "template": Template,
    "overview": Overview,
}

SEARCH_FIELDS = {
    "view": {"query": "ViewQueryPhrase", "sort": "ViewSortPhrase"},
    "action": {"name": "ActionNamePhrase", "query": "ActionQueryPhrase"},
    "dossier": {"title": "DossierTitlePhrase", "query": "DossierQueryPhrase"},
    "template": {"analytic": "TemplateAnalyticPhrase", "detection": "TemplateDetectionPhrase"},
    "overview": {
        "analytic": "OverviewAnalyticPhrase",
        "detection": "OverviewDetectionPhrase",
    },
}
VIEW_UI_SEARCH_FIELDS = ("title", "query", "sort", "type", "owner")


def _case_variants(phrase: str) -> tuple[str, str, str]:
    return phrase.lower(), phrase.upper(), phrase


def _metadata_search_query(collection_name: str, phrase: str) -> str:
    if collection_name == "view":
        fields = " OR ".join(f"{field}:*{phrase}*" for field in VIEW_UI_SEARCH_FIELDS)
        return f"({fields})"
    if collection_name == "action":
        return f"name:(*{phrase}*) OR query:(*{phrase}*)"
    return f"*:*{phrase}*"


def _result_ids(results: dict) -> list[str]:
    ids = []
    for item in results["items"]:
        item_id = item["id"]
        ids.extend(item_id if isinstance(item_id, list) else [item_id])
    return ids


def _document_data(collection_name: str) -> dict:
    common = {
        "owner": "OwnerMiXeDCase",
        "admins": ["AdminMiXeDCase"],
        "members": ["MemberMiXeDCase"],
    }
    owner = {"owner": "OwnerMiXeDCase"}
    if collection_name == "view":
        return {
            **common,
            "view_id": str(uuid4()),
            "indexes": ["hit"],
            "title": "Unrelated title",
            **SEARCH_FIELDS[collection_name],
            "type": "personal",
        }
    if collection_name == "action":
        return {
            **common,
            "action_id": str(uuid4()),
            **SEARCH_FIELDS[collection_name],
            "triggers": [],
            "operations": [],
        }
    if collection_name == "dossier":
        return {
            **common,
            "dossier_id": str(uuid4()),
            **SEARCH_FIELDS[collection_name],
            "type": "personal",
            "leads": [],
            "pivots": [],
        }
    if collection_name == "template":
        return {
            **owner,
            "template_id": str(uuid4()),
            **SEARCH_FIELDS[collection_name],
            "type": "personal",
        }
    if collection_name == "overview":
        return {
            **owner,
            "overview_id": str(uuid4()),
            **SEARCH_FIELDS[collection_name],
            "content": "OverviewMarkdownPhrase",
        }
    raise AssertionError(f"Unexpected collection {collection_name!r}")


def _create_legacy_collection(store: ESStore, collection_name: str, document_id: str) -> tuple[ESCollection, dict]:
    model_class = MODEL_CLASSES[collection_name]
    collection = ESCollection(store, collection_name, model_class=model_class)
    model = model_class(_document_data(collection_name))
    source_document = deepcopy(model.as_primitives())

    legacy_mappings = collection._get_index_mappings()
    for field_name in SEARCH_FIELDS[collection_name]:
        legacy_field = legacy_mappings["properties"][field_name]
        assert legacy_field["type"] == "keyword"
        legacy_field.pop("normalizer", None)
    if collection_name == "overview":
        # Before the current ODM changed content to Text, persisted overview content was keyword.
        legacy_mappings["properties"]["content"] = {"type": "keyword"}

    store.client.indices.create(
        index=collection.index_name,
        mappings=legacy_mappings,
        settings=collection._get_index_settings(),
        aliases={collection.name: {}},
    )
    store.client.index(
        index=collection.index_name,
        id=document_id,
        document=source_document,
        refresh="wait_for",
    )

    if collection_name == "overview":
        assert collection.fields()["content"]["type"] == "keyword"

    # The old plain-keyword mappings do not match these lower-case UI-style wildcard queries.
    for phrase in SEARCH_FIELDS[collection_name].values():
        query = _metadata_search_query(collection_name, phrase.lower())
        assert collection.search(query, as_obj=False, rows=100)["total"] == 0

    return collection, source_document


def _ilm_document_data(collection_name: str) -> dict:
    data = _document_data(collection_name)
    if collection_name == "overview":
        data["content"] = "# Migration Markdown MiXeD"
    return data


def _create_legacy_ilm_collection(store: ESStore, config, collection_name: str):
    collection = ESCollection(
        store,
        collection_name,
        model_class=MODEL_CLASSES[collection_name],
        ilm_config=ILMIndexConfig(enabled=True),
    )
    collection._create_ilm_policy(config.datastore.ilm)

    legacy_mappings = deepcopy(collection._get_index_mappings())
    for field_name in SEARCH_FIELDS[collection_name]:
        legacy_mappings["properties"][field_name].pop("normalizer", None)
    if collection_name == "overview":
        # Persisted overview content predates the current ODM Text mapping.
        legacy_mappings["properties"]["content"] = {"type": "keyword"}

    legacy_settings = deepcopy(collection._get_index_settings())
    legacy_settings["index"]["lifecycle"] = {
        "name": f"{collection.name}_policy",
        "rollover_alias": collection.name,
    }
    store.client.indices.put_index_template(
        name=f"{collection.name}_template",
        index_patterns=[f"{collection.name}-*"],
        template={"settings": legacy_settings, "mappings": deepcopy(legacy_mappings)},
    )

    source_documents = {}
    source_ids = {}
    original_index_metadata = {}
    for suffix in ("000001", "000002"):
        index_name = f"{collection.name}-{suffix}"
        document_id = str(uuid4())
        source_document = deepcopy(MODEL_CLASSES[collection_name](_ilm_document_data(collection_name)).as_primitives())
        store.client.indices.create(
            index=index_name,
            mappings=deepcopy(legacy_mappings),
            settings=deepcopy(legacy_settings),
            aliases={collection.name: {"is_write_index": suffix == "000002"}},
        )
        store.client.index(
            index=index_name,
            id=document_id,
            document=source_document,
            refresh="wait_for",
        )
        index_data = store.client.indices.get(index=index_name)[index_name]
        source_documents[index_name] = source_document
        source_ids[index_name] = document_id
        original_index_metadata[index_name] = {
            "lifecycle": deepcopy(index_data["settings"]["index"].get("lifecycle", {})),
            "aliases": deepcopy(index_data.get("aliases", {})),
        }

    return collection, source_documents, source_ids, original_index_metadata


def _seed_legacy_ilm_collections(store: ESStore, config):
    original_ignore_ensure = ESCollection.IGNORE_ENSURE_COLLECTION
    collections = {}
    source_documents = {}
    source_ids = {}
    original_index_metadata = {}
    try:
        ESCollection.IGNORE_ENSURE_COLLECTION = True
        for collection_name in COLLECTION_NAMES:
            (
                collections[collection_name],
                collection_sources,
                collection_ids,
                collection_metadata,
            ) = _create_legacy_ilm_collection(store, config, collection_name)
            source_documents.update(collection_sources)
            source_ids.update(collection_ids)
            original_index_metadata.update(collection_metadata)
    finally:
        # Construction bypasses ensure only while seeding stale resources; the migration runs normally.
        ESCollection.IGNORE_ENSURE_COLLECTION = original_ignore_ensure
    return collections, source_documents, source_ids, original_index_metadata, original_ignore_ensure


def _assert_stale_ilm_templates(store: ESStore, collections: dict) -> None:
    for collection_name, collection in collections.items():
        assert collection.ilm_config is not None
        template = store.client.indices.get_index_template(name=f"{collection.name}_template")["index_templates"][0][
            "index_template"
        ]["template"]
        for field_name in SEARCH_FIELDS[collection_name]:
            assert "normalizer" not in template["mappings"]["properties"][field_name]
        if collection_name == "overview":
            assert template["mappings"]["properties"]["content"]["type"] == "keyword"


def _assert_current_ilm_mappings(store: ESStore, collection_name: str, index_name: str) -> None:
    properties = store.client.indices.get_mapping(index=index_name)[index_name]["mappings"]["properties"]
    for field_name in SEARCH_FIELDS[collection_name]:
        assert properties[field_name]["type"] == "keyword"
        assert properties[field_name]["normalizer"] == "lowercase_normalizer"
    if collection_name == "overview":
        assert properties["content"]["type"] == "text"
        assert "normalizer" not in properties["content"]


def _assert_migrated_ilm_collection(
    store: ESStore,
    collection_name: str,
    collection: ESCollection,
    source_documents: dict,
    source_ids: dict,
    original_index_metadata: dict,
) -> None:
    expected_index_names = {f"{collection.name}-000001", f"{collection.name}-000002"}
    assert set(collection.index_list_full) == expected_index_names
    assert collection.index_name == f"{collection.name}-000002"
    for index_name in expected_index_names:
        index_data = store.client.indices.get(index=index_name)[index_name]
        assert index_data["settings"]["index"].get("lifecycle", {}) == original_index_metadata[index_name]["lifecycle"]
        assert index_data.get("aliases", {}) == original_index_metadata[index_name]["aliases"]
        _assert_current_ilm_mappings(store, collection_name, index_name)
        assert store.client.get(index=index_name, id=source_ids[index_name])["_source"] == source_documents[index_name]

    alias_indices = store.client.indices.get_alias(name=collection.name)
    write_targets = {
        index_name
        for index_name, index_data in alias_indices.items()
        if index_data.get("aliases", {}).get(collection.name, {}).get("is_write_index") is True
    }
    assert write_targets == {f"{collection.name}-000002"}

    template_name = f"{collection.name}_template"
    template = store.client.indices.get_index_template(name=template_name)["index_templates"][0]["index_template"]
    template_mappings = template["template"]["mappings"]["properties"]
    for field_name in SEARCH_FIELDS[collection_name]:
        assert template_mappings[field_name]["normalizer"] == "lowercase_normalizer"
    if collection_name == "overview":
        assert template_mappings["content"]["type"] == "text"


def _rollover_and_verify_ilm_collection(store: ESStore, collection_name: str, collection: ESCollection) -> None:
    rollover_result = store.client.indices.rollover(alias=collection.name, conditions={"max_docs": 1})
    new_index = f"{collection.name}-000003"
    assert rollover_result["rolled_over"] is True
    assert rollover_result["new_index"] == new_index
    _assert_current_ilm_mappings(store, collection_name, new_index)

    collection._refresh_ilm_index_name()
    assert collection.index_name == new_index
    new_document_id = str(uuid4())
    new_document = MODEL_CLASSES[collection_name](_ilm_document_data(collection_name))
    assert collection.save(new_document_id, new_document, refresh="wait_for")
    assert store.client.get(index=new_index, id=new_document_id)["_id"] == new_document_id

    for phrase in SEARCH_FIELDS[collection_name].values():
        for case_variant in _case_variants(phrase):
            results = collection.search(_metadata_search_query(collection_name, case_variant), as_obj=False, rows=100)
            assert results["total"] == 3
            assert new_document_id in _result_ids(results)
    if collection_name == "overview":
        content_results = collection.search("content:MiXeD", as_obj=False, rows=100)
        assert content_results["total"] == 3
        assert new_document_id in _result_ids(content_results)

    alias_indices = store.client.indices.get_alias(name=collection.name)
    write_targets = {
        index_name
        for index_name, index_data in alias_indices.items()
        if index_data.get("aliases", {}).get(collection.name, {}).get("is_write_index") is True
    }
    assert write_targets == {new_index}


def _assert_reindexed_collection(
    store: ESStore,
    collection_name: str,
    collection: ESCollection,
    document_id: str,
    source_document: dict,
) -> None:
    current_mapping = store.client.indices.get_mapping(index=collection.index_name)[collection.index_name]["mappings"][
        "properties"
    ]
    for field_name in SEARCH_FIELDS[collection_name]:
        assert current_mapping[field_name]["type"] == "keyword"
        assert current_mapping[field_name]["normalizer"] == "lowercase_normalizer"
    if collection_name == "overview":
        assert current_mapping["content"]["type"] == "text"
        assert "normalizer" not in current_mapping["content"]
    assert "normalizer" not in current_mapping["owner"]
    assert "normalizer" not in current_mapping["id"]
    for field_name in ("admins", "members"):
        if field_name in current_mapping:
            assert "normalizer" not in current_mapping[field_name]

    # Views and Actions use explicit field-scoped search; the other three screens use *:*phrase*.
    for phrase in SEARCH_FIELDS[collection_name].values():
        for case_variant in _case_variants(phrase):
            query = _metadata_search_query(collection_name, case_variant)
            results = collection.search(query, as_obj=False, rows=100)
            assert results["total"] == 1
            assert _result_ids(results) == [document_id]

    # Ownership fields remain ordinary case-sensitive keywords, unlike the metadata fields above.
    assert collection.search("owner:OwnerMiXeDCase*", as_obj=False, rows=100)["total"] == 1
    assert collection.search("owner:ownermixedcase*", as_obj=False, rows=100)["total"] == 0

    stored = store.client.get(index=collection.index_name, id=document_id)
    assert stored["_source"] == source_document
    assert stored["_id"] == document_id


def _delete_isolated_prefix_indexes(store: ESStore, prefix: str) -> None:
    try:
        indexes = store.client.indices.get(
            index=f"{prefix}-*",
            allow_no_indices=True,
            ignore_unavailable=True,
        )
    except elasticsearch.exceptions.NotFoundError:
        return

    for index_name in indexes:
        store.client.indices.delete(index=index_name, ignore_unavailable=True)


def _delete_isolated_ilm_resources(store: ESStore, prefix: str) -> None:
    _delete_isolated_prefix_indexes(store, prefix)
    for collection_name in COLLECTION_NAMES:
        collection_prefix = f"{prefix}-{collection_name}"
        try:
            store.client.indices.delete_index_template(name=f"{collection_prefix}_template")
        except elasticsearch.exceptions.NotFoundError:
            pass
        try:
            store.client.ilm.delete_lifecycle(name=f"{collection_prefix}_policy")
        except elasticsearch.exceptions.NotFoundError:
            pass


def test_metadata_case_insensitive_migration_preserves_documents_and_enables_wildcard_search(config, monkeypatch):
    seed_store = ESStore(config)
    if not seed_store.ping():
        seed_store.close()
        pytest.skip("Could not connect to Elasticsearch for isolated metadata migration integration test")

    prefix = f"howler-ci-{uuid4().hex[:12]}"
    monkeypatch.setattr(collection_module, "DATASTORE_INDEX_PREFIX", prefix)
    monkeypatch.setattr(migration_module, "DATASTORE_INDEX_PREFIX", prefix)

    original_ignore_ensure = ESCollection.IGNORE_ENSURE_COLLECTION
    datastore_store = None
    source_documents: dict[str, dict] = {}
    document_ids = {collection_name: str(uuid4()) for collection_name in COLLECTION_NAMES}

    try:
        ESCollection.IGNORE_ENSURE_COLLECTION = True
        try:
            for collection_name in COLLECTION_NAMES:
                collection, source_document = _create_legacy_collection(
                    seed_store,
                    collection_name,
                    document_ids[collection_name],
                )
                source_documents[collection_name] = source_document
        finally:
            # Legacy setup alone suppresses ensure; the migration must use normal collection construction.
            ESCollection.IGNORE_ENSURE_COLLECTION = original_ignore_ensure

        datastore_store = ESStore(config)
        assert datastore_store.ping()
        datastore = HowlerDatastore(datastore_store)
        assert datastore_store.validate is True
        assert datastore_store._collections == {}

        # Normal application access still rejects the old keyword mapping before migration.
        with pytest.raises(HowlerRuntimeError, match="Field content didn't have the expected store type"):
            _ = datastore.overview
        assert "overview" not in datastore_store._collections
        assert datastore_store.validate is True

        migration_collection = datastore.migration
        reindexed_collections = []
        original_reindex = ESCollection.reindex

        def track_reindex(collection, *args, **kwargs):
            reindexed_collections.append(collection.name)
            return original_reindex(collection, *args, **kwargs)

        monkeypatch.setattr(ESCollection, "reindex", track_reindex)
        run_migrations(datastore, [CaseInsensitiveMetadataMigration()])

        assert datastore_store.validate is True
        assert set(datastore_store._collections) == {"migration"}
        assert reindexed_collections == [f"{prefix}-{name}" for name in COLLECTION_NAMES]
        migration_record = migration_collection.get_if_exists("metadata-case-insensitive-search", as_obj=False)
        assert migration_record["status"] == "applied"
        assert migration_record["affected_documents"] == len(COLLECTION_NAMES)

        for collection_name in COLLECTION_NAMES:
            collection = getattr(datastore, collection_name)
            assert collection.validate is True
            assert (
                datastore_store.client.indices.exists_index_template(name=f"{collection.name}_template").body is False
            )
            assert collection._ilm_policy_exists() is False
            _assert_reindexed_collection(
                datastore_store,
                collection_name,
                collection,
                document_ids[collection_name],
                source_documents[collection_name],
            )

        # The existing applied-record gate must skip all collection reindexes on subsequent runner calls.
        run_migrations(datastore, [CaseInsensitiveMetadataMigration()])
        assert reindexed_collections == [f"{prefix}-{name}" for name in COLLECTION_NAMES]
    finally:
        ESCollection.IGNORE_ENSURE_COLLECTION = original_ignore_ensure
        _delete_isolated_prefix_indexes(seed_store, prefix)
        seed_store.close()
        if datastore_store is not None:
            datastore_store.close()


def test_metadata_case_insensitive_migration_refreshes_ilm_templates_and_rollover_mappings(config, monkeypatch):
    seed_store = ESStore(config)
    if not seed_store.ping():
        seed_store.close()
        pytest.skip("Could not connect to Elasticsearch for isolated ILM metadata migration integration test")

    prefix = f"howler-ci-ilm-{uuid4().hex[:12]}"
    monkeypatch.setattr(collection_module, "DATASTORE_INDEX_PREFIX", prefix)
    monkeypatch.setattr(migration_module, "DATASTORE_INDEX_PREFIX", prefix)

    original_ignore_ensure = ESCollection.IGNORE_ENSURE_COLLECTION
    try:
        collections, source_documents, source_ids, original_index_metadata, original_ignore_ensure = (
            _seed_legacy_ilm_collections(seed_store, config)
        )
        _assert_stale_ilm_templates(seed_store, collections)

        class IsolatedMetadataDatastore:
            def __init__(self):
                self.ds = seed_store

            def __getattr__(self, name):
                if name in collections:
                    return collections[name]
                raise AttributeError(name)

        datastore = IsolatedMetadataDatastore()
        assert seed_store.validate is True

        affected_documents = CaseInsensitiveMetadataMigration().run(datastore)

        assert affected_documents == len(COLLECTION_NAMES) * 2
        assert seed_store.validate is True

        for collection_name, collection in collections.items():
            _assert_migrated_ilm_collection(
                seed_store,
                collection_name,
                collection,
                source_documents,
                source_ids,
                original_index_metadata,
            )
            _rollover_and_verify_ilm_collection(seed_store, collection_name, collection)
    finally:
        ESCollection.IGNORE_ENSURE_COLLECTION = original_ignore_ensure
        _delete_isolated_ilm_resources(seed_store, prefix)
        seed_store.close()


@pytest.mark.parametrize("temporary_suffix", ["action_hot__reindex", "action-000001__reindex"])
def test_default_migration_batch_preflights_action_orphan_before_lazy_collection_creation(
    config,
    monkeypatch,
    temporary_suffix,
):
    store = ESStore(config)
    if not store.ping():
        store.close()
        pytest.skip("Could not connect to Elasticsearch for isolated migration preflight integration test")

    prefix = f"howler-ci-orphan-{uuid4().hex[:12]}"
    monkeypatch.setattr(collection_module, "DATASTORE_INDEX_PREFIX", prefix)
    monkeypatch.setattr(migration_module, "DATASTORE_INDEX_PREFIX", prefix)
    temporary_index = f"{prefix}-{temporary_suffix}"
    action_hot = f"{prefix}-action_hot"
    action_ilm = f"{prefix}-action-000001"
    action_alias = f"{prefix}-action"
    sentinel_document = {"sentinel": "the-only-copy-MiXeD"}

    try:
        store.client.indices.create(
            index=temporary_index,
            mappings={"properties": {"sentinel": {"type": "keyword"}}},
            settings={"number_of_shards": 1, "number_of_replicas": 0},
        )
        store.client.index(
            index=temporary_index,
            id="only-copy",
            document=sentinel_document,
            refresh="wait_for",
        )
        original_index_data = store.client.indices.get(index=temporary_index)[temporary_index]
        original_settings = original_index_data["settings"]["index"]
        original_aliases = original_index_data.get("aliases", {})
        original_mappings = original_index_data["mappings"]

        # The real datastore keeps collections lazy; constructing it does not touch action.
        datastore = HowlerDatastore(store)
        assert "action" not in store._collections

        with pytest.raises(DataStoreException, match="leftover temporary reindex"):
            run_migrations(datastore)

        # Neither the hot source nor ILM source/alias is created while the orphan is the only copy.
        assert store.client.indices.exists(index=action_hot).body is False
        assert store.client.indices.exists(index=action_ilm).body is False
        assert store.client.indices.exists_alias(name=action_alias).body is False
        assert "action" not in store._collections

        current_index_data = store.client.indices.get(index=temporary_index)[temporary_index]
        assert current_index_data["settings"]["index"] == original_settings
        assert current_index_data.get("aliases", {}) == original_aliases
        assert current_index_data["mappings"] == original_mappings
        assert store.client.get(index=temporary_index, id="only-copy")["_source"] == sentinel_document
        assert store.client.get(index=temporary_index, id="only-copy")["_id"] == "only-copy"

        # Batch preflight failed before either selected migration acquired a claim or ran.
        assert datastore.migration.get_if_exists("action-owner-id-to-owner", as_obj=False) is None
        assert datastore.migration.get_if_exists("metadata-case-insensitive-search", as_obj=False) is None
    finally:
        _delete_isolated_prefix_indexes(store, prefix)
        store.close()
