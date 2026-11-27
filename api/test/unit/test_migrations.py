import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from elasticsearch.exceptions import NotFoundError
from pydantic import Field

from howler.actions.models import ActionArguments, ActionDescription, ActionSpecification, ActionStep
from howler.datastore.exceptions import DataStoreException, VersionConflictException
from howler.datastore.migrations import action_arguments as action_arguments_migration
from howler.datastore.migrations.action_arguments import ActionArgumentsMigration, _migrate_operations
from howler.datastore.migrations.action_owner import ActionOwnerMigration
from howler.datastore.migrations.base import Migration
from howler.datastore.migrations.runner import _mark_applied, _release_claim, run_migrations


class FakeMigrationCollection:
    def __init__(self, records=None):
        self.records = records or {}
        self.versions = {key: 0 for key in self.records}

    def get_if_exists(self, key, as_obj=True, version=False):
        record = self.records.get(key)
        if version:
            if record is None:
                return None, "create"
            return deepcopy(record), f"version-{self.versions[key]}"

        return deepcopy(record)

    def save(self, key, data, version=None, refresh=None):
        if version == "create":
            if key in self.records:
                raise VersionConflictException(f"{key} already exists")
        elif version != f"version-{self.versions[key]}":
            raise VersionConflictException(f"{key} has changed")

        self.records[key] = deepcopy(data)
        self.versions[key] = self.versions.get(key, -1) + 1

    def delete(self, key, refresh=None, version=None):
        if key not in self.records:
            return False
        if version is not None and version != f"version-{self.versions[key]}":
            raise VersionConflictException(f"{key} has changed")
        del self.records[key]
        del self.versions[key]
        return True


class StubMigration(Migration):
    migration_id = "stub-migration"

    def __init__(self, result=0, error=None):
        self.result = result
        self.error = error
        self.calls = 0

    def run(self, datastore) -> int:
        self.calls += 1
        if self.error:
            raise self.error
        return self.result


def make_datastore(records=None):
    return SimpleNamespace(migration=FakeMigrationCollection(records))


def test_loader_constructs_datastore_without_running_migrations(monkeypatch):
    from howler.common import loader
    from howler.config_models import config

    datastore = MagicMock()
    store = MagicMock()
    datastore_constructor = MagicMock(return_value=datastore)
    store_constructor = MagicMock(return_value=store)
    migrations = MagicMock()
    monkeypatch.setattr(loader, "_datastore", None)
    monkeypatch.setattr("howler.datastore.howler_store.HowlerDatastore", datastore_constructor)
    monkeypatch.setattr("howler.datastore.store.ESStore", store_constructor)
    monkeypatch.setattr("howler.datastore.migrations.run_migrations", migrations)

    assert loader.datastore() is datastore

    store_constructor.assert_called_once_with(config=config, archive_access=True)
    datastore_constructor.assert_called_once_with(store)
    migrations.assert_not_called()


def test_run_migrations_records_zero_document_migration():
    datastore = make_datastore()
    migration = StubMigration(result=0)

    run_migrations(datastore, [migration])

    record = datastore.migration.records[migration.migration_id]
    assert record["status"] == "applied"
    assert record["affected_documents"] == 0
    assert record["started_at"]
    assert record["applied_at"]
    assert record["claim_id"]


def test_run_migrations_skips_applied_migration():
    datastore = make_datastore(
        {
            "stub-migration": {
                "migration_id": "stub-migration",
                "status": "applied",
                "started_at": "2026-01-01T00:00:00.000Z",
                "applied_at": "2026-01-01T00:00:01.000Z",
                "affected_documents": 3,
            }
        }
    )
    migration = StubMigration(result=7)

    run_migrations(datastore, [migration])

    assert migration.calls == 0
    assert datastore.migration.records["stub-migration"]["affected_documents"] == 3


def test_run_migrations_removes_failed_claim():
    datastore = make_datastore()
    migration = StubMigration(error=RuntimeError("migration failed"))

    with pytest.raises(RuntimeError, match="migration failed"):
        run_migrations(datastore, [migration])

    assert migration.calls == 1
    assert migration.migration_id not in datastore.migration.records


def test_run_migrations_rejects_duplicate_ids():
    datastore = make_datastore()
    first = StubMigration()
    second = StubMigration()

    with pytest.raises(DataStoreException, match="must be unique"):
        run_migrations(datastore, [first, second])

    assert datastore.migration.records == {}


def test_run_migrations_waits_for_claimed_migration(monkeypatch):
    now = datetime.now(tz=timezone.utc)
    datastore = make_datastore(
        {
            "stub-migration": {
                "migration_id": "stub-migration",
                "status": "running",
                "started_at": now.isoformat().replace("+00:00", "Z"),
                "claim_id": "other-claim",
            }
        }
    )
    migration = StubMigration(result=7)
    reads = 0
    original_get = datastore.migration.get_if_exists

    def get_if_exists(key, as_obj=True, version=False):
        nonlocal reads
        reads += 1
        if reads == 2:
            datastore.migration.records[key].update(
                {
                    "status": "applied",
                    "applied_at": now.isoformat().replace("+00:00", "Z"),
                    "affected_documents": 4,
                }
            )
        return original_get(key, as_obj=as_obj, version=version)

    datastore.migration.get_if_exists = get_if_exists
    monkeypatch.setattr("howler.datastore.migrations.runner._migration_wait_timeout", lambda: 1)
    monkeypatch.setattr("howler.datastore.migrations.runner._migration_poll_interval", lambda: 0)
    monkeypatch.setattr("howler.datastore.migrations.runner.time.sleep", lambda _: None)

    run_migrations(datastore, [migration])

    assert migration.calls == 0
    assert datastore.migration.records["stub-migration"]["affected_documents"] == 4


def test_action_owner_migration_cleans_legacy_owner_fields():
    collection = SimpleNamespace(
        name="howler-action",
        _update_async=MagicMock(return_value={"updated": 4}),
    )
    datastore = SimpleNamespace(action=collection)

    affected_documents = ActionOwnerMigration().run(datastore)

    assert affected_documents == 4
    collection._update_async.assert_called_once()
    args, kwargs = collection._update_async.call_args
    assert args == ("howler-action",)
    assert kwargs["query"] == {
        "bool": {
            "filter": [{"exists": {"field": "owner_id"}}],
        }
    }
    assert "ctx._source.owner = ctx._source.owner_id" in kwargs["script"]["source"]
    assert "ctx._source.remove('owner_id')" in kwargs["script"]["source"]
    assert "if (!ctx._source.containsKey('owner') || ctx._source.owner == null)" in kwargs["script"]["source"]
    assert kwargs["refresh"] is True


def test_action_owner_migration_records_noop_count():
    collection = SimpleNamespace(name="howler-action", _update_async=MagicMock(return_value={"updated": 0}))
    datastore = SimpleNamespace(action=collection)

    assert ActionOwnerMigration().run(datastore) == 0


def test_failed_action_owner_update_does_not_record_applied_migration():
    datastore = make_datastore()
    datastore.action = SimpleNamespace(
        name="howler-action",
        _update_async=MagicMock(side_effect=DataStoreException("partial update")),
    )

    with pytest.raises(DataStoreException, match="partial update"):
        run_migrations(datastore, [ActionOwnerMigration()])

    assert datastore.migration.records == {}


@pytest.mark.parametrize("result", [True, -1, "1", None])
def test_run_migrations_rejects_invalid_affected_document_count(result):
    datastore = make_datastore()
    migration = StubMigration(result=result)

    with pytest.raises(DataStoreException, match="invalid affected-document count"):
        run_migrations(datastore, [migration])

    assert migration.migration_id not in datastore.migration.records


def test_run_migrations_replaces_stale_claim(monkeypatch):
    stale_started_at = datetime.now(tz=timezone.utc) - timedelta(hours=2)
    datastore = make_datastore(
        {
            "stub-migration": {
                "migration_id": "stub-migration",
                "status": "running",
                "started_at": stale_started_at.isoformat().replace("+00:00", "Z"),
                "claim_id": "stale-claim",
            }
        }
    )
    migration = StubMigration(result=2)
    monkeypatch.setattr("howler.datastore.migrations.runner._migration_stale_claim_timeout", lambda: 1)

    run_migrations(datastore, [migration])

    record = datastore.migration.records[migration.migration_id]
    assert migration.calls == 1
    assert record["status"] == "applied"
    assert record["claim_id"] != "stale-claim"
    assert record["affected_documents"] == 2


def test_run_migrations_recovers_stale_claim_replacement_race(monkeypatch):
    stale_started_at = datetime.now(tz=timezone.utc) - timedelta(hours=2)
    datastore = make_datastore(
        {
            "stub-migration": {
                "migration_id": "stub-migration",
                "status": "running",
                "started_at": stale_started_at.isoformat().replace("+00:00", "Z"),
                "claim_id": "stale-claim",
            }
        }
    )
    migration = StubMigration(result=1)
    original_save = datastore.migration.save
    replacement_attempts = 0

    def save(key, data, version=None, refresh=None):
        nonlocal replacement_attempts
        if version != "create" and data.get("status") == "running":
            replacement_attempts += 1
            if replacement_attempts == 1:
                datastore.migration.versions[key] += 1
                raise VersionConflictException("claim replaced concurrently")
        return original_save(key, data, version=version, refresh=refresh)

    datastore.migration.save = save
    monkeypatch.setattr("howler.datastore.migrations.runner._migration_stale_claim_timeout", lambda: 1)

    run_migrations(datastore, [migration])

    assert replacement_attempts == 2
    assert migration.calls == 1
    assert datastore.migration.records[migration.migration_id]["status"] == "applied"


def test_old_claim_owner_cannot_complete_or_delete_replacement_claim():
    datastore = make_datastore(
        {
            "stub-migration": {
                "migration_id": "stub-migration",
                "status": "running",
                "started_at": datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z"),
                "claim_id": "replacement-claim",
            }
        }
    )

    with pytest.raises(DataStoreException, match="no longer owned"):
        _mark_applied(datastore.migration, "stub-migration", "old-claim", 1)
    with pytest.raises(DataStoreException, match="no longer owned"):
        _release_claim(datastore.migration, "stub-migration", "old-claim")

    assert datastore.migration.records["stub-migration"]["claim_id"] == "replacement-claim"


@pytest.mark.parametrize(
    "record",
    [
        {"migration_id": "other-id", "status": "running", "started_at": "2026-01-01T00:00:00Z"},
        {"migration_id": "stub-migration", "status": "unknown", "started_at": "2026-01-01T00:00:00Z"},
        {"migration_id": "stub-migration", "status": "running", "started_at": "not-a-date"},
    ],
)
def test_run_migrations_rejects_invalid_records(record):
    datastore = make_datastore({"stub-migration": record})

    with pytest.raises(DataStoreException):
        run_migrations(datastore, [StubMigration()])


def test_run_migrations_rejects_empty_selection():
    with pytest.raises(DataStoreException, match="At least one"):
        run_migrations(make_datastore(), [])


class MigrationArguments(ActionArguments):
    value: str = Field(min_length=1)


class MigrationTransitionArguments(ActionArguments):
    transition: str
    escalation: str | None = None
    status: str | None = None


def _migration_specification(operation_id, arguments):
    return ActionSpecification(
        id=operation_id,
        title=operation_id,
        description=ActionDescription(short=operation_id),
        roles=["admin"],
        steps=[ActionStep(args={field_name: [] for field_name in arguments.model_fields})],
        arguments=arguments,
    )


def _install_migration_specifications(monkeypatch):
    specifications = {
        "typed": _migration_specification("typed", MigrationArguments),
        "empty_typed": ActionSpecification(
            id="empty_typed",
            title="empty_typed",
            description=ActionDescription(short="empty_typed"),
            roles=["admin"],
        ),
        "transition": _migration_specification("transition", MigrationTransitionArguments),
        "legacy": ActionSpecification.from_legacy(
            {
                "id": "legacy",
                "title": "legacy",
                "description": {"short": "legacy"},
                "roles": ["admin"],
                "steps": [{"args": {"plugin_value": []}}],
            }
        ),
    }
    monkeypatch.setattr(
        action_arguments_migration.actions,
        "get_specification",
        lambda operation_id: specifications.get(operation_id),
    )
    return specifications


@pytest.mark.parametrize(
    ("operation_id", "input_data", "expected_data"),
    [
        ("typed", {"value": "kept", "obsolete": 1, "query": "spoofed", "auth_token": "spoofed"}, {"value": "kept"}),
        ("empty_typed", {"obsolete": 1, "query": "spoofed"}, {}),
        (
            "legacy",
            {"plugin_value": "kept", "undeclared": 1, "query": "x", "auth_token": "x", "operation_id": "x"},
            {"plugin_value": "kept"},
        ),
    ],
)
def test_action_arguments_migration_strips_undeclared_and_reserved_keys(
    monkeypatch, operation_id, input_data, expected_data
):
    _install_migration_specifications(monkeypatch)
    operations = [{"operation_id": operation_id, "data_json": json.dumps(input_data)}]

    migrated, changed = _migrate_operations(operations, "action-id")

    assert changed
    assert json.loads(migrated[0]["data_json"]) == expected_data


@pytest.mark.parametrize(
    ("transition", "escalation", "expected", "should_change"),
    [
        ("promote", None, "alert", True),
        ("promote", "", "alert", True),
        ("demote", None, "hit", True),
        ("demote", "alert", "alert", False),
        ("assess", None, None, False),
    ],
)
def test_action_arguments_migration_backfills_transition_escalations(
    monkeypatch, transition, escalation, expected, should_change
):
    _install_migration_specifications(monkeypatch)
    data = {"transition": transition}
    if escalation is not None:
        data["escalation"] = escalation
    operations = [{"operation_id": "transition", "data_json": json.dumps(data)}]

    migrated, changed = _migrate_operations(operations, "action-id")

    assert changed is should_change
    if not should_change:
        assert migrated == operations
    else:
        assert json.loads(migrated[0]["data_json"]) == {"transition": transition, "escalation": expected}


def test_action_arguments_migration_normalizes_empty_and_preserves_invalid_operations(monkeypatch, caplog):
    _install_migration_specifications(monkeypatch)
    migrated_empty, changed_empty = _migrate_operations([{"operation_id": "typed", "data_json": ""}], "action-id")
    assert changed_empty
    assert migrated_empty[0]["data_json"] == "{}"

    operations = [
        {"operation_id": "disabled_plugin", "data_json": '{"obsolete": 1}'},
        {"operation_id": "typed", "data_json": "{"},
        {"operation_id": "typed", "data_json": "[]"},
        {"operation_id": "typed", "data_json": json.dumps({"value": ""})},
        {"operation_id": "transition", "data_json": '{"transition":["promote"]}'},
    ]
    migrated, changed = _migrate_operations(operations, "action-id")

    assert not changed
    assert migrated == operations
    assert "unknown or disabled" in caplog.text
    assert "data_json must be valid JSON" in caplog.text
    assert "data_json must be a JSON object" in caplog.text
    assert "invalid arguments after migration" in caplog.text


def _make_action_arguments_datastore(source, *, update_side_effect=None):
    client = SimpleNamespace()
    client.get = MagicMock(return_value={"_source": deepcopy(source), "_seq_no": 1, "_primary_term": 1})
    client.update = MagicMock(side_effect=update_side_effect)
    client.indices = SimpleNamespace(refresh=MagicMock())
    collection = SimpleNamespace(
        name="howler-actions",
        MAX_VERSION_CONFLICT_ATTEMPTS=3,
        datastore=SimpleNamespace(client=client),
        scan_with_retry=MagicMock(
            return_value=iter([{"_id": "action-id", "_index": "howler-actions_hot", "_source": deepcopy(source)}])
        ),
    )

    def with_retries(func, *args, **kwargs):
        kwargs.pop("raise_conflicts", None)
        return func(*args, **kwargs)

    collection.with_retries = MagicMock(side_effect=with_retries)
    return SimpleNamespace(action=collection), collection, client


def test_action_arguments_migration_retries_conflicts_and_is_idempotent(monkeypatch):
    _install_migration_specifications(monkeypatch)
    source = {"operations": [{"operation_id": "typed", "data_json": '{"value":"kept","old":1}'}]}
    datastore, collection, client = _make_action_arguments_datastore(source)
    update_attempts = 0

    def update_document(*_args, **kwargs):
        nonlocal update_attempts
        update_attempts += 1
        if update_attempts == 1:
            raise VersionConflictException("write conflict")
        source["operations"] = kwargs["doc"]["operations"]
        return {"result": "updated"}

    client.update.side_effect = update_document
    collection.scan_with_retry.side_effect = lambda **_: iter(
        [{"_id": "action-id", "_index": "howler-actions_hot", "_source": deepcopy(source)}]
    )

    assert ActionArgumentsMigration().run(datastore) == 1
    assert update_attempts == 2
    client.indices.refresh.assert_called_once_with(index="howler-actions")
    assert json.loads(source["operations"][0]["data_json"]) == {"value": "kept"}

    client.indices.refresh.reset_mock()
    assert ActionArgumentsMigration().run(datastore) == 0
    assert client.update.call_count == 2
    client.indices.refresh.assert_not_called()


def test_action_arguments_migration_conflict_exhaustion_and_deleted_docs(monkeypatch):
    _install_migration_specifications(monkeypatch)
    source = {"operations": [{"operation_id": "typed", "data_json": '{"value":"kept","old":1}'}]}
    datastore, collection, client = _make_action_arguments_datastore(
        source, update_side_effect=VersionConflictException("write conflict")
    )

    with pytest.raises(VersionConflictException, match="write conflict"):
        ActionArgumentsMigration().run(datastore)
    assert client.update.call_count == collection.MAX_VERSION_CONFLICT_ATTEMPTS

    datastore, _, client = _make_action_arguments_datastore(
        source, update_side_effect=NotFoundError("document deleted", None, {})
    )
    assert ActionArgumentsMigration().run(datastore) == 0
    client.indices.refresh.assert_not_called()


def test_action_arguments_migration_restores_lazy_collection_validation():
    client = SimpleNamespace(indices=SimpleNamespace(refresh=MagicMock()))
    collection = SimpleNamespace(
        name="howler-actions",
        MAX_VERSION_CONFLICT_ATTEMPTS=3,
        datastore=SimpleNamespace(client=client),
        scan_with_retry=MagicMock(return_value=iter([])),
    )
    store = SimpleNamespace(validate=True)

    class LazyDatastore:
        ds = store

        @property
        def action(self):
            assert self.ds.validate is False
            return collection

    assert ActionArgumentsMigration().run(LazyDatastore()) == 0
    assert store.validate is True
    collection.scan_with_retry.assert_called_once_with(query={"match_all": {}}, index="howler-actions")
