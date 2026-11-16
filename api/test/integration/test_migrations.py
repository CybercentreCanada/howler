"""Integration coverage for explicit datastore migrations against Elasticsearch."""

import json
import random
import string
from types import SimpleNamespace

import pytest

from howler.datastore.migrations.action_arguments import ActionArgumentsMigration
from howler.datastore.migrations.action_owner import ActionOwnerMigration
from howler.datastore.migrations.runner import run_migrations
from howler.datastore.store import ESStore


def _random_name(prefix: str) -> str:
    return prefix + "_" + "".join(random.choices(string.ascii_lowercase, k=8))


@pytest.fixture()
def migration_datastore(request):
    """Create isolated raw action and migration collections for one migration run."""
    try:
        store = ESStore()
        available = store.ping()
    except Exception:  # noqa: BLE001
        pytest.skip("Could not connect to Elasticsearch")
    if not available:
        store.close()
        pytest.skip("Could not connect to Elasticsearch")

    action_name = _random_name("migration_action")
    migration_name = _random_name("migration_record")
    store.register(action_name)
    store.register(migration_name)
    action = getattr(store, action_name)
    migration = getattr(store, migration_name)

    def cleanup():
        for collection in (action, migration):
            try:
                collection.datastore.client.indices.delete_alias(index="_all", name=collection.name)
            except Exception:  # noqa: BLE001
                pass
            collection.datastore.client.indices.delete(index=collection.index_name, ignore_unavailable=True)
        store.close()

    request.addfinalizer(cleanup)
    return SimpleNamespace(action=action, migration=migration)


def _raw_document(collection, document_id: str) -> dict:
    response = collection.datastore.client.get(index=collection.name, id=document_id)
    return response["_source"]


def test_action_owner_migration_moves_and_cleans_raw_owners(migration_datastore):
    datastore = migration_datastore
    legacy_owner_id = "legacy-owner"
    canonical_owner = "canonical-owner"
    datastore.action.datastore.client.index(
        index=datastore.action.name,
        id="legacy-only",
        document={"owner_id": legacy_owner_id},
    )
    datastore.action.datastore.client.index(
        index=datastore.action.name,
        id="mixed-fields",
        document={"owner": canonical_owner, "owner_id": legacy_owner_id},
        refresh=True,
    )

    migration = ActionOwnerMigration()
    run_migrations(datastore, [migration])

    legacy_document = _raw_document(datastore.action, "legacy-only")
    mixed_document = _raw_document(datastore.action, "mixed-fields")
    record = datastore.migration.get_if_exists(migration.migration_id, as_obj=False)
    assert legacy_document["owner"] == legacy_owner_id
    assert "owner_id" not in legacy_document
    assert mixed_document["owner"] == canonical_owner
    assert "owner_id" not in mixed_document
    assert record["status"] == "applied"
    assert record["affected_documents"] == 2

    run_migrations(datastore, [migration])

    assert datastore.migration.get_if_exists(migration.migration_id, as_obj=False)["affected_documents"] == 2


def test_action_owner_migration_records_zero_matching_documents(migration_datastore):
    datastore = migration_datastore
    datastore.action.datastore.client.index(
        index=datastore.action.name,
        id="canonical-only",
        document={"owner": "canonical-owner"},
        refresh=True,
    )

    migration = ActionOwnerMigration()
    run_migrations(datastore, [migration])

    record = datastore.migration.get_if_exists(migration.migration_id, as_obj=False)
    assert record["status"] == "applied"
    assert record["affected_documents"] == 0


def test_action_arguments_migration_cleans_raw_documents_and_is_idempotent(migration_datastore, caplog):
    datastore = migration_datastore
    documents = {
        "migrated-action": {
            "operations": [
                {
                    "operation_id": "add_label",
                    "data_json": json.dumps(
                        {"category": "generic", "label": "kept", "obsolete": "removed", "query": "spoofed"}
                    ),
                },
                {"operation_id": "transition", "data_json": '{"status":"open","transition":"promote"}'},
            ]
        },
        "untouched-action": {
            "operations": [
                {"operation_id": "disabled_plugin", "data_json": '{"query":"preserved"}'},
                {"operation_id": "add_label", "data_json": "{"},
            ]
        },
    }
    for document_id, source in documents.items():
        datastore.action.datastore.client.index(
            index=datastore.action.name,
            id=document_id,
            document=source,
            refresh="wait_for",
        )

    migration = ActionArgumentsMigration()
    assert migration.run(datastore) == 1
    assert migration.run(datastore) == 0

    migrated = _raw_document(datastore.action, "migrated-action")["operations"]
    assert json.loads(migrated[0]["data_json"]) == {"category": "generic", "label": "kept"}
    assert json.loads(migrated[1]["data_json"]) == {"status": "open", "transition": "promote", "escalation": "alert"}
    assert (
        _raw_document(datastore.action, "untouched-action")["operations"] == documents["untouched-action"]["operations"]
    )
    assert "unknown or disabled" in caplog.text
    assert "data_json must be valid JSON" in caplog.text
