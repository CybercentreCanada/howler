"""Integration coverage for explicit datastore migrations against Elasticsearch."""

import json
import random
import string
from types import SimpleNamespace

import pytest
from pydantic import Field

from howler.actions.models import ActionArguments, ActionDescription, ActionSpecification, ActionStep
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


class IntegrationTypedArguments(ActionArguments):
    value: str = Field(default="default", min_length=1)


class IntegrationTransitionArguments(ActionArguments):
    transition: str
    escalation: str | None = None


def _migration_specification(operation_id: str, arguments: type[ActionArguments]) -> ActionSpecification:
    return ActionSpecification(
        id=operation_id,
        title=operation_id,
        description=ActionDescription(short=operation_id),
        roles=["admin"],
        steps=[ActionStep(args={field_name: [] for field_name in arguments.model_fields})],
        arguments=arguments,
    )


def test_action_arguments_migration_cleans_raw_documents_and_is_idempotent(migration_datastore, monkeypatch, caplog):
    datastore = migration_datastore
    from howler.datastore.migrations import action_arguments as migration_module

    specifications = {
        "typed": _migration_specification("typed", IntegrationTypedArguments),
        "transition": _migration_specification("transition", IntegrationTransitionArguments),
        "legacy_plugin": ActionSpecification.from_legacy(
            {
                "id": "legacy_plugin",
                "title": "Legacy plugin",
                "description": {"short": "Legacy plugin operation"},
                "roles": ["admin"],
                "steps": [{"args": {"plugin_value": []}}],
            }
        ),
    }
    monkeypatch.setattr(
        migration_module.actions,
        "get_specification",
        lambda operation_id: specifications.get(operation_id),
    )

    documents = {
        "typed-action": {
            "operations": [
                {
                    "operation_id": "typed",
                    "data_json": json.dumps(
                        {"value": "kept", "obsolete": "removed", "query": "spoofed", "auth_token": "spoofed"}
                    ),
                },
                {"operation_id": "transition", "data_json": '{"transition":"promote"}'},
                {"operation_id": "transition", "data_json": '{"transition":"demote"}'},
                {"operation_id": "transition", "data_json": '{"transition":"demote","escalation":"alert"}'},
                {"operation_id": "transition", "data_json": '{"transition":"assess"}'},
            ]
        },
        "legacy-action": {
            "operations": [
                {
                    "operation_id": "legacy_plugin",
                    "data_json": json.dumps(
                        {
                            "plugin_value": "kept",
                            "undeclared": "removed",
                            "query": "removed",
                            "auth_token": "removed",
                        }
                    ),
                }
            ]
        },
        "empty-action": {"operations": [{"operation_id": "typed", "data_json": ""}]},
        "unknown-and-malformed": {
            "operations": [
                {"operation_id": "disabled_plugin", "data_json": '{"query":"preserved"}'},
                {"operation_id": "typed", "data_json": "{"},
            ]
        },
        "invalid-declared-value": {"operations": [{"operation_id": "typed", "data_json": '{"value":""}'}]},
    }
    for document_id, source in documents.items():
        datastore.action.datastore.client.index(
            index=datastore.action.name,
            id=document_id,
            document=source,
            refresh="wait_for",
        )

    client = datastore.action.datastore.client
    original_update = client.update
    updates = []

    def track_update(*args, **kwargs):
        updates.append((args, kwargs))
        return original_update(*args, **kwargs)

    monkeypatch.setattr(client, "update", track_update)
    migration = ActionArgumentsMigration()
    assert migration.run(datastore) == 3

    typed = _raw_document(datastore.action, "typed-action")["operations"]
    assert json.loads(typed[0]["data_json"]) == {"value": "kept"}
    assert json.loads(typed[1]["data_json"]) == {"transition": "promote", "escalation": "alert"}
    assert json.loads(typed[2]["data_json"]) == {"transition": "demote", "escalation": "hit"}
    assert json.loads(typed[3]["data_json"]) == {"transition": "demote", "escalation": "alert"}
    assert json.loads(typed[4]["data_json"]) == {"transition": "assess"}
    assert json.loads(_raw_document(datastore.action, "legacy-action")["operations"][0]["data_json"]) == {
        "plugin_value": "kept"
    }
    assert _raw_document(datastore.action, "empty-action")["operations"][0]["data_json"] == "{}"
    assert (
        _raw_document(datastore.action, "unknown-and-malformed")["operations"]
        == documents["unknown-and-malformed"]["operations"]
    )
    assert (
        _raw_document(datastore.action, "invalid-declared-value")["operations"]
        == documents["invalid-declared-value"]["operations"]
    )
    assert "unknown or disabled" in caplog.text
    assert "malformed data_json" in caplog.text
    assert "invalid arguments after migration" in caplog.text
    assert len(updates) == 3

    assert migration.run(datastore) == 0
    assert len(updates) == 3
