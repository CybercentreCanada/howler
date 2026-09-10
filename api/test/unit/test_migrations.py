from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from howler.datastore.exceptions import DataStoreException, VersionConflictException
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

    store_constructor.assert_called_once_with(config=loader.config, archive_access=True)
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
