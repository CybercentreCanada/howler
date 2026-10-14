from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import elasticsearch
import pytest

from howler.datastore import collection as collection_module
from howler.datastore.collection import ESCollection
from howler.datastore.exceptions import DataStoreException
from howler.datastore.howler_store import HowlerDatastore
from howler.datastore.migrations import case_insensitive_metadata as migration_module
from howler.datastore.migrations.case_insensitive_metadata import COLLECTION_NAMES, CaseInsensitiveMetadataMigration
from howler.datastore.migrations.runner import run_migrations
from howler.datastore.store import ESStore
from howler.odm.models.action import Action
from howler.odm.models.dossier import Dossier
from howler.odm.models.migration import MigrationRecord
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
        "content": "OverviewMarkdownPhrase",
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
        }
    raise AssertionError(f"Unexpected collection {collection_name!r}")


def _create_legacy_collection(store: ESStore, collection_name: str, document_id: str) -> tuple[ESCollection, dict]:
    model_class = MODEL_CLASSES[collection_name]
    collection = ESCollection(store, f"{collection_name}_{uuid4().hex[:8]}", model_class=model_class)
    model = model_class(_document_data(collection_name))
    source_document = deepcopy(model.as_primitives())

    legacy_mappings = collection._get_index_mappings()
    for field_name in SEARCH_FIELDS[collection_name]:
        legacy_field = legacy_mappings["properties"][field_name]
        assert legacy_field["type"] == "keyword"
        legacy_field.pop("normalizer", None)

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

    # The old plain-keyword mappings do not match these lower-case UI-style wildcard queries.
    for phrase in SEARCH_FIELDS[collection_name].values():
        query = _metadata_search_query(collection_name, phrase.lower())
        assert collection.search(query, as_obj=False, rows=100)["total"] == 0

    return collection, source_document


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


def _delete_isolated_indexes(store: ESStore, collection: ESCollection) -> None:
    try:
        indexes = store.client.indices.get(
            index=f"{collection.name}*",
            allow_no_indices=True,
            ignore_unavailable=True,
        )
    except elasticsearch.exceptions.NotFoundError:
        return

    for index_name in indexes:
        store.client.indices.delete(index=index_name, ignore_unavailable=True)


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


def test_metadata_case_insensitive_migration_preserves_documents_and_enables_wildcard_search(config, monkeypatch):
    store = ESStore(config)
    if not store.ping():
        store.close()
        pytest.skip("Could not connect to Elasticsearch for isolated metadata migration integration test")

    prefix = f"howler-ci-{uuid4().hex[:12]}"
    monkeypatch.setattr(collection_module, "DATASTORE_INDEX_PREFIX", prefix)
    monkeypatch.setattr(migration_module, "DATASTORE_INDEX_PREFIX", prefix)

    original_ignore_ensure = ESCollection.IGNORE_ENSURE_COLLECTION
    ESCollection.IGNORE_ENSURE_COLLECTION = True
    collections: dict[str, ESCollection] = {}
    migration_collection = None
    source_documents: dict[str, dict] = {}
    document_ids = {collection_name: str(uuid4()) for collection_name in COLLECTION_NAMES}

    try:
        for collection_name in COLLECTION_NAMES:
            collection, source_document = _create_legacy_collection(
                store,
                collection_name,
                document_ids[collection_name],
            )
            collections[collection_name] = collection
            source_documents[collection_name] = source_document

        ESCollection.IGNORE_ENSURE_COLLECTION = original_ignore_ensure
        migration_collection = ESCollection(
            store,
            f"migration_records_{uuid4().hex[:8]}",
            model_class=MigrationRecord,
        )
        datastore = SimpleNamespace(ds=store, migration=migration_collection, **collections)
        reindex_spies = {}
        for collection_name, collection in collections.items():
            collection.reindex = MagicMock(wraps=collection.reindex)
            reindex_spies[collection_name] = collection.reindex

        run_migrations(datastore, [CaseInsensitiveMetadataMigration()])

        migration_record = migration_collection.get_if_exists("metadata-case-insensitive-search", as_obj=False)
        assert migration_record["status"] == "applied"
        assert migration_record["affected_documents"] == len(COLLECTION_NAMES)

        for collection_name, collection in collections.items():
            _assert_reindexed_collection(
                store,
                collection_name,
                collection,
                document_ids[collection_name],
                source_documents[collection_name],
            )

        # The existing applied-record gate must skip all collection reindexes on subsequent runner calls.
        rerun_counts = {collection_name: reindex.call_count for collection_name, reindex in reindex_spies.items()}
        run_migrations(datastore, [CaseInsensitiveMetadataMigration()])
        assert {
            collection_name: reindex.call_count for collection_name, reindex in reindex_spies.items()
        } == rerun_counts
    finally:
        ESCollection.IGNORE_ENSURE_COLLECTION = original_ignore_ensure
        for collection in [*collections.values(), *([migration_collection] if migration_collection else [])]:
            _delete_isolated_indexes(store, collection)
        store.close()


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
