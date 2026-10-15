from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from elastic_transport import ApiResponseMeta, HeadApiResponse, NodeConfig

from howler import odm
from howler.common.loader import DATASTORE_INDEX_PREFIX
from howler.datastore.exceptions import DataStoreException, VersionConflictException
from howler.datastore.howler_store import HowlerDatastore
from howler.datastore.migrations.action_owner import ActionOwnerMigration
from howler.datastore.migrations.base import Migration
from howler.datastore.migrations.case_insensitive_metadata import (
    COLLECTION_NAMES,
    TRANSPORT_TIMEOUT,
    CaseInsensitiveMetadataMigration,
)
from howler.datastore.migrations.runner import MIGRATIONS, run_migrations
from howler.datastore.store import ESStore
from howler.datastore.support.build import build_mapping
from howler.external import run_migrations as migration_cli
from howler.odm.models.action import Action
from howler.odm.models.dossier import Dossier
from howler.odm.models.overview import Overview
from howler.odm.models.template import Template
from howler.odm.models.view import View

MODEL_FIELDS = {
    View: {"query", "sort"},
    Action: {"name", "query"},
    Dossier: {"title", "query"},
    Template: {"analytic", "detection"},
    Overview: {"analytic", "detection"},
}


def _head_response(exists: bool) -> HeadApiResponse:
    return HeadApiResponse(
        ApiResponseMeta(
            status=200 if exists else 404,
            http_version="1.1",
            headers={},
            duration=0,
            node=NodeConfig(scheme="http", host="localhost", port=9200),
        )
    )


def test_metadata_fields_use_case_insensitive_mappings_without_changing_serialization():
    expected_field_paths = {
        "view.query",
        "view.sort",
        "action.name",
        "action.query",
        "dossier.title",
        "dossier.query",
        "template.analytic",
        "template.detection",
        "overview.analytic",
        "overview.detection",
    }
    assert sum(len(fields) for fields in MODEL_FIELDS.values()) == 10

    for model_class, changed_fields in MODEL_FIELDS.items():
        mapping, _ = build_mapping(model_class.fields().values())
        for field_name in changed_fields:
            field = model_class.fields()[field_name]
            assert type(field) is odm.CaseInsensitiveKeyword
            assert field.check(f"MiXeD-{field_name}") == f"MiXeD-{field_name}"
            assert mapping[field_name]["type"] == "keyword"
            assert mapping[field_name]["normalizer"] == "lowercase_normalizer"

        for field_name in {"owner", "admins", "members"} & set(model_class.fields()):
            field = model_class.fields()[field_name]
            assert type(field) is not odm.CaseInsensitiveKeyword
            assert "normalizer" not in mapping[field_name]

    overview_fields = Overview.fields()
    overview_mapping, _ = build_mapping(overview_fields.values())
    assert type(overview_fields["content"]) is odm.Text
    assert overview_mapping["content"]["type"] == "text"
    assert "normalizer" not in overview_mapping["content"]

    actual_field_paths = {
        f"{model_class.__name__.lower()}.{field_name}"
        for model_class, field_names in MODEL_FIELDS.items()
        for field_name in field_names
    }
    assert actual_field_paths == expected_field_paths

    data = [
        (
            View,
            {
                "view_id": str(uuid4()),
                "indexes": ["hit"],
                "title": "View title stays MixedCase",
                "query": "ViewQuery stays MiXeD",
                "sort": "Timestamp DESC MiXeD",
                "type": "personal",
                "owner": "OwnerMiXeD",
                "admins": ["AdminMiXeD"],
                "members": ["MemberMiXeD"],
            },
            {"query": "ViewQuery stays MiXeD", "sort": "Timestamp DESC MiXeD"},
        ),
        (
            Action,
            {
                "action_id": str(uuid4()),
                "owner": "OwnerMiXeD",
                "name": "ActionName MiXeD",
                "query": "ActionQuery MiXeD",
                "triggers": [],
                "operations": [],
            },
            {"name": "ActionName MiXeD", "query": "ActionQuery MiXeD"},
        ),
        (
            Dossier,
            {
                "dossier_id": str(uuid4()),
                "owner": "OwnerMiXeD",
                "title": "DossierTitle MiXeD",
                "query": "DossierQuery MiXeD",
                "type": "personal",
                "leads": [],
                "pivots": [],
            },
            {"title": "DossierTitle MiXeD", "query": "DossierQuery MiXeD"},
        ),
        (
            Template,
            {
                "template_id": str(uuid4()),
                "analytic": "TemplateAnalytic MiXeD",
                "detection": "TemplateDetection MiXeD",
                "type": "personal",
                "owner": "OwnerMiXeD",
            },
            {"analytic": "TemplateAnalytic MiXeD", "detection": "TemplateDetection MiXeD"},
        ),
        (
            Overview,
            {
                "overview_id": str(uuid4()),
                "analytic": "OverviewAnalytic MiXeD",
                "detection": "OverviewDetection MiXeD",
                "content": "# Markdown stays MiXeD",
                "owner": "OwnerMiXeD",
            },
            {
                "analytic": "OverviewAnalytic MiXeD",
                "detection": "OverviewDetection MiXeD",
                "content": "# Markdown stays MiXeD",
            },
        ),
    ]

    for model_class, values, expected in data:
        model = model_class(values)
        serialized = model.as_primitives()
        assert {name: serialized[name] for name in expected} == expected
        assert serialized["owner"] == "OwnerMiXeD"
        for id_field in ("view_id", "action_id", "dossier_id", "template_id", "overview_id"):
            if id_field in values:
                assert serialized[id_field] == values[id_field]


def test_optional_metadata_fields_allow_absence_and_view_dossier_values_keep_case():
    view = View(
        {
            "view_id": str(uuid4()),
            "indexes": ["hit"],
            "title": "Optional sort test",
            "query": "Query MiXeD Case",
            "type": "personal",
            "owner": "OwnerMiXeD",
        }
    )
    dossier = Dossier(
        {
            "dossier_id": str(uuid4()),
            "title": "Dossier MiXeD Case",
            "owner": "OwnerMiXeD",
            "type": "personal",
            "leads": [],
            "pivots": [],
        }
    )
    template = Template({"template_id": str(uuid4()), "analytic": "Analytic MiXeD", "type": "personal"})
    overview = Overview({"overview_id": str(uuid4()), "analytic": "Analytic MiXeD", "content": "Markdown"})

    assert view.sort is None
    assert view.query == "Query MiXeD Case"
    assert dossier.query is None
    assert dossier.title == "Dossier MiXeD Case"
    assert template.detection is None
    assert overview.detection is None


class FakeMigrationRecords:
    def __init__(self):
        self.records: dict[str, dict] = {}
        self.versions: dict[str, int] = {}

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
        if version is not None and version != f"version-{self.versions[key]}":
            raise VersionConflictException(f"{key} has changed")
        if key not in self.records:
            return False
        del self.records[key]
        del self.versions[key]
        return True


class RecordingMigration(Migration):
    def __init__(self, migration_id: str, events: list[str], preflight_error: Exception | None = None):
        self.migration_id = migration_id
        self.events = events
        self.preflight_error = preflight_error

    def preflight(self, datastore) -> None:
        self.events.append(f"preflight:{self.migration_id}")
        if self.preflight_error:
            raise self.preflight_error

    def run(self, datastore) -> int:
        self.events.append(f"run:{self.migration_id}")
        return 0


class TimelineMigrationRecords(FakeMigrationRecords):
    def __init__(self, events: list[str]):
        super().__init__()
        self.events = events

    def save(self, key, data, version=None, refresh=None):
        if data.get("status") == "running":
            self.events.append(f"claim:{key}")
        super().save(key, data, version=version, refresh=refresh)


def _applied_record(migration_id: str) -> dict:
    return {
        "migration_id": migration_id,
        "status": "applied",
        "started_at": "2026-01-01T00:00:00Z",
        "applied_at": "2026-01-01T00:00:01Z",
        "affected_documents": 0,
    }


def _make_datastore(*, document_count=0, reindex_result=True):
    indices = MagicMock()
    indices.get.return_value = {}
    indices.exists.side_effect = lambda index: _head_response(
        not index.endswith("_missing") and not index.endswith("__reindex")
    )
    store = SimpleNamespace(client=SimpleNamespace(indices=indices), validate=True)
    datastore = SimpleNamespace(ds=store)
    collections = {}

    for collection_name in COLLECTION_NAMES:
        collection = SimpleNamespace(
            datastore=store,
            ilm_config=None,
            index_list_full=[
                f"{collection_name}_hot",
                f"{collection_name}-000001",
                f"{collection_name}_missing",
                f"{collection_name}_hot__reindex",
            ],
            reindex=MagicMock(return_value=reindex_result),
            _create_index_template=MagicMock(),
            _index_doc_count=MagicMock(return_value=document_count),
        )
        setattr(datastore, collection_name, collection)
        collections[collection_name] = collection

    return datastore, collections, indices


def test_runner_preflights_every_selected_migration_before_any_claim_or_run():
    events = []
    datastore = SimpleNamespace(ds=SimpleNamespace(client=SimpleNamespace(indices=MagicMock())))
    datastore.migration = TimelineMigrationRecords(events)
    migrations = [RecordingMigration("first", events), RecordingMigration("second", events)]

    run_migrations(datastore, migrations)

    assert events == [
        "preflight:first",
        "preflight:second",
        "claim:first",
        "run:first",
        "claim:second",
        "run:second",
    ]


def test_runner_preflights_applied_migration_in_mixed_batch_before_pending_owner_runs():
    events = []
    records = FakeMigrationRecords()
    records.records["metadata-case-insensitive-search"] = _applied_record("metadata-case-insensitive-search")
    records.versions["metadata-case-insensitive-search"] = 0

    def update_action(*_args, **_kwargs):
        events.append("run:action-owner")
        return {"updated": 0}

    datastore = SimpleNamespace(
        ds=SimpleNamespace(client=SimpleNamespace(indices=MagicMock())),
        migration=records,
        action=SimpleNamespace(name="howler-action", _update_async=MagicMock(side_effect=update_action)),
    )
    metadata_migration = RecordingMigration("metadata-case-insensitive-search", events)

    run_migrations(datastore, [ActionOwnerMigration(), metadata_migration])

    assert events == ["preflight:metadata-case-insensitive-search", "run:action-owner"]
    assert records.records["metadata-case-insensitive-search"] == _applied_record("metadata-case-insensitive-search")


def test_runner_skips_all_preflights_when_every_selected_migration_is_applied():
    events = []
    records = FakeMigrationRecords()
    for migration_id in ("first", "second"):
        records.records[migration_id] = _applied_record(migration_id)
        records.versions[migration_id] = 0
    indices = MagicMock()
    datastore = SimpleNamespace(ds=SimpleNamespace(client=SimpleNamespace(indices=indices)), migration=records)
    migrations = [RecordingMigration("first", events), RecordingMigration("second", events)]

    run_migrations(datastore, migrations)

    assert events == []
    indices.get.assert_not_called()


def test_runner_waits_for_active_metadata_claim_before_preflight():
    migration_id = "metadata-case-insensitive-search"
    now = datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")
    records = FakeMigrationRecords()
    records.records[migration_id] = {
        "migration_id": migration_id,
        "status": "running",
        "started_at": now,
        "claim_id": "active-claim",
    }
    records.versions[migration_id] = 0

    datastore, _, indices = _make_datastore()
    datastore.migration = records
    pending_migration = RecordingMigration("pending-migration", [])
    original_get = records.get_if_exists
    record_reads = 0

    def complete_active_claim(key, as_obj=True, version=False):
        nonlocal record_reads
        if key == migration_id:
            record_reads += 1
            if record_reads == 2:
                records.records[key].update(
                    {
                        "status": "applied",
                        "applied_at": now,
                        "affected_documents": 0,
                    }
                )
        return original_get(key, as_obj=as_obj, version=version)

    records.get_if_exists = complete_active_claim
    preflight_statuses = []

    def find_reindex(index, **_kwargs):
        status = records.records[migration_id]["status"]
        preflight_statuses.append(status)
        if status == "running" and index == f"{DATASTORE_INDEX_PREFIX}-view*":
            return {f"{DATASTORE_INDEX_PREFIX}-view_hot__reindex": {}}
        return {}

    indices.get.side_effect = find_reindex

    run_migrations(datastore, [CaseInsensitiveMetadataMigration(), pending_migration])

    assert record_reads >= 3
    assert preflight_statuses == ["applied"] * len(COLLECTION_NAMES)
    assert pending_migration.events == ["preflight:pending-migration", "run:pending-migration"]


def test_preflight_failure_preserves_stale_claim(monkeypatch):
    monkeypatch.setattr("howler.datastore.migrations.runner._migration_stale_claim_timeout", lambda: 0)
    migration_id = "preflight-failure"
    events = []
    records = FakeMigrationRecords()
    claim = {
        "migration_id": migration_id,
        "status": "running",
        "started_at": "2026-10-14T08:00:00Z",
        "claim_id": "existing-claim",
    }
    records.records[migration_id] = deepcopy(claim)
    records.versions[migration_id] = 0
    datastore = SimpleNamespace(ds=SimpleNamespace(client=SimpleNamespace(indices=MagicMock())), migration=records)
    migration = RecordingMigration(migration_id, events, DataStoreException("preflight blocked"))

    with pytest.raises(DataStoreException, match="preflight blocked"):
        run_migrations(datastore, [migration])

    assert records.records[migration_id] == claim
    assert records.versions[migration_id] == 0
    assert events == [f"preflight:{migration_id}"]


def test_migration_reindexes_fixed_collections_with_configured_timeout_and_counts_physical_indexes(monkeypatch):
    datastore, collections, indices = _make_datastore()
    for collection in collections.values():
        collection._index_doc_count.side_effect = lambda index: 1 if index.endswith("_hot") else 2
    monkeypatch.setattr(
        "howler.datastore.migrations.case_insensitive_metadata.TRANSPORT_TIMEOUT",
        731,
    )

    assert CaseInsensitiveMetadataMigration().run(datastore) == 15

    assert list(collections) == ["view", "action", "dossier", "template", "overview"]
    for collection in collections.values():
        collection.reindex.assert_called_once_with(allow_failures=False, request_timeout=731)
        collection._create_index_template.assert_not_called()
        assert [call.args[0] for call in collection._index_doc_count.call_args_list] == [
            next(index for index in collection.index_list_full if index.endswith("_hot")),
            next(index for index in collection.index_list_full if index.endswith("-000001")),
        ]
    assert indices.exists.call_count == 15


def test_migration_refreshes_only_ilm_template_after_validation_restore_and_before_reindex(monkeypatch):
    datastore, collections, _ = _make_datastore()
    global_ilm_config = object()
    events = []
    collections["view"].ilm_config = object()

    def refresh_template(ilm_config):
        assert datastore.ds.validate is True
        assert ilm_config is global_ilm_config
        events.append(("template", "view"))

    def reindex_view(**_kwargs):
        assert datastore.ds.validate is True
        events.append(("reindex", "view"))
        return True

    def count_view(index):
        events.append(("count", index))
        return 0

    collections["view"]._create_index_template.side_effect = refresh_template
    collections["view"].reindex.side_effect = reindex_view
    collections["view"]._index_doc_count.side_effect = count_view
    monkeypatch.setattr(
        "howler.odm.models.config.config",
        SimpleNamespace(datastore=SimpleNamespace(ilm=global_ilm_config)),
    )

    assert CaseInsensitiveMetadataMigration().run(datastore) == 0

    assert events[:3] == [
        ("template", "view"),
        ("reindex", "view"),
        ("count", "view_hot"),
    ]
    assert [event for event in events if event[0] == "count"] == [
        ("count", "view_hot"),
        ("count", "view-000001"),
    ]
    collections["view"]._create_index_template.assert_called_once_with(global_ilm_config)
    for collection_name, collection in collections.items():
        if collection_name != "view":
            collection._create_index_template.assert_not_called()


def test_migration_unwraps_realistic_head_api_existence_response():
    datastore, _, indices = _make_datastore(document_count=2)

    assert CaseInsensitiveMetadataMigration().run(datastore) == 20
    assert indices.exists.call_count == 15


def test_migration_rejects_invalid_existence_response_body():
    datastore, collections, indices = _make_datastore()
    indices.exists.side_effect = lambda **_: SimpleNamespace(body="true")

    with pytest.raises(DataStoreException, match="invalid existence result"):
        CaseInsensitiveMetadataMigration().run(datastore)

    collections["action"].reindex.assert_not_called()


def test_migration_records_zero_when_existing_physical_indexes_are_empty():
    datastore, _, _ = _make_datastore(document_count=0)

    assert CaseInsensitiveMetadataMigration().run(datastore) == 0


@pytest.mark.parametrize("bad_count", [True, -1, "1", None])
def test_migration_rejects_invalid_index_document_counts(bad_count):
    datastore, collections, _ = _make_datastore()
    collections["view"]._index_doc_count.return_value = bad_count

    with pytest.raises(DataStoreException, match="invalid document count"):
        CaseInsensitiveMetadataMigration().run(datastore)

    collections["action"].reindex.assert_not_called()


@pytest.mark.parametrize("result", [False, None, 1, "true"])
def test_migration_rejects_any_reindex_result_other_than_true(result):
    datastore, collections, _ = _make_datastore(reindex_result=result)

    with pytest.raises(DataStoreException, match="did not confirm a successful reindex"):
        CaseInsensitiveMetadataMigration().run(datastore)

    collections["action"].reindex.assert_not_called()


@pytest.mark.parametrize(
    "leftover_index",
    [
        f"{DATASTORE_INDEX_PREFIX}-view_hot__reindex",
        f"{DATASTORE_INDEX_PREFIX}-view-000001__reindex",
    ],
)
def test_leftover_reindex_preflight_fails_before_lazy_collection_recreation_or_cleanup(leftover_index):
    indices = MagicMock()
    indices.exists.return_value = False
    unrelated_randomized_index = f"{DATASTORE_INDEX_PREFIX}-view_random_suffix_hot__reindex"
    indices.get.side_effect = lambda index, **_: (
        {leftover_index: {}, unrelated_randomized_index: {}} if "-view" in index else {}
    )
    datastore = SimpleNamespace(ds=SimpleNamespace(client=SimpleNamespace(indices=indices)))

    class LazyCollectionsDatastore:
        ds = datastore.ds

        def __getattr__(self, name):
            if name in COLLECTION_NAMES:
                raise AssertionError(f"lazy collection {name} was initialized before preflight")
            raise AttributeError(name)

    with pytest.raises(DataStoreException, match="leftover temporary reindex") as error:
        CaseInsensitiveMetadataMigration().run(LazyCollectionsDatastore())

    assert leftover_index in str(error.value)
    assert unrelated_randomized_index not in str(error.value)
    assert indices.get.call_args_list[0].kwargs["index"] == f"{DATASTORE_INDEX_PREFIX}-view*__reindex"
    indices.exists.assert_not_called()
    indices.delete.assert_not_called()


def test_migration_stops_after_a_midstream_reindex_failure():
    datastore, collections, _ = _make_datastore()
    collections["action"].reindex.side_effect = RuntimeError("reindex interrupted")

    with pytest.raises(RuntimeError, match="reindex interrupted"):
        CaseInsensitiveMetadataMigration().run(datastore)

    collections["view"].reindex.assert_called_once()
    collections["action"].reindex.assert_called_once()
    collections["dossier"].reindex.assert_not_called()
    collections["template"].reindex.assert_not_called()
    collections["overview"].reindex.assert_not_called()


def test_failed_runner_execution_is_unrecorded_retry_succeeds_then_applied_migration_skips(monkeypatch):
    datastore, collections, _ = _make_datastore()
    datastore.migration = FakeMigrationRecords()
    collections["action"].reindex.side_effect = [RuntimeError("temporary failure"), True]
    migration = CaseInsensitiveMetadataMigration()
    monkeypatch.setattr(
        "howler.datastore.migrations.case_insensitive_metadata.TRANSPORT_TIMEOUT",
        137,
    )

    with pytest.raises(RuntimeError, match="temporary failure"):
        run_migrations(datastore, [migration])
    assert datastore.migration.records == {}

    run_migrations(datastore, [migration])
    assert datastore.migration.records[migration.migration_id]["status"] == "applied"
    assert datastore.migration.records[migration.migration_id]["affected_documents"] == 0
    assert collections["view"].reindex.call_count == 2
    for collection in collections.values():
        assert all(call.kwargs["request_timeout"] == 137 for call in collection.reindex.call_args_list)

    calls_after_success = {name: collection.reindex.call_count for name, collection in collections.items()}
    run_migrations(datastore, [migration])
    assert {name: collection.reindex.call_count for name, collection in collections.items()} == calls_after_success


def test_registry_and_cli_list_and_select_the_new_migration(monkeypatch, capsys):
    assert [migration.migration_id for migration in MIGRATIONS] == [
        "action-owner-id-to-owner",
        "metadata-case-insensitive-search",
    ]

    assert migration_cli.main(["--list"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "action-owner-id-to-owner",
        "metadata-case-insensitive-search",
    ]

    datastore = SimpleNamespace(ds=SimpleNamespace(close=MagicMock()))
    runner = MagicMock()
    monkeypatch.setattr(migration_cli, "_load_migrations", lambda: (MIGRATIONS, runner))
    monkeypatch.setattr(migration_cli, "_load_datastore", lambda: datastore)

    assert migration_cli.main(["--migration-id", "metadata-case-insensitive-search"]) == 0
    runner.assert_called_once_with(datastore, (MIGRATIONS[1],))
    datastore.ds.close.assert_called_once_with()


def test_migration_timeout_symbol_matches_datastore_collection_configuration():
    from howler.datastore import collection
    from howler.datastore.migrations import case_insensitive_metadata

    assert case_insensitive_metadata.TRANSPORT_TIMEOUT == collection.TRANSPORT_TIMEOUT


def _make_lazy_store(validate: bool):
    store = ESStore.__new__(ESStore)
    store._models = {
        "view": View,
        "action": Action,
        "dossier": Dossier,
        "template": Template,
        "overview": Overview,
    }
    unrelated_collection = object()
    store._collections = {"unrelated": unrelated_collection}
    store._ilm_configs = {"view": object()}
    store.validate = validate
    indices = MagicMock()
    indices.get.return_value = {}
    indices.exists.return_value = _head_response(True)
    store.client = SimpleNamespace(indices=indices)

    datastore = HowlerDatastore.__new__(HowlerDatastore)
    datastore.ds = store
    return datastore, store, unrelated_collection, indices


@pytest.mark.parametrize("initial_validate", [True, False])
def test_migration_acquires_registered_lazy_collections_without_validation_and_restores_before_reindex(
    monkeypatch, initial_validate
):
    datastore, store, unrelated_collection, indices = _make_lazy_store(initial_validate)
    collections = {}
    expected_models = dict(zip(COLLECTION_NAMES, (View, Action, Dossier, Template, Overview), strict=True))
    ilm_config = store._ilm_configs["view"]

    def make_collection(datastore_arg, name, model_class=None, validate=True, ilm_config=None):
        assert datastore_arg is store
        assert store.validate is False

        def reindex(**_):
            _assert_validation_restored(store, initial_validate)
            return True

        collection = SimpleNamespace(
            datastore=store,
            ilm_config=ilm_config,
            index_list_full=[f"{name}_hot"],
            reindex=MagicMock(side_effect=reindex),
            _create_index_template=MagicMock(),
            _index_doc_count=MagicMock(return_value=1),
        )
        collections[name] = (collection, model_class, validate, ilm_config)
        return collection

    monkeypatch.setattr("howler.datastore.store.ESCollection", make_collection)

    assert CaseInsensitiveMetadataMigration().run(datastore) == len(COLLECTION_NAMES)

    assert store.validate is initial_validate
    assert store._collections == {"unrelated": unrelated_collection}
    assert indices.exists.call_count == len(COLLECTION_NAMES)
    assert set(collections) == set(COLLECTION_NAMES)
    for collection_name, (collection, model_class, collection_validate, collection_ilm_config) in collections.items():
        assert model_class is expected_models[collection_name]
        assert collection_validate is False
        assert collection_ilm_config is (ilm_config if collection_name == "view" else None)
        collection.reindex.assert_called_once_with(allow_failures=False, request_timeout=TRANSPORT_TIMEOUT)


def _assert_validation_restored(store, expected):
    assert store.validate is expected


@pytest.mark.parametrize("initial_validate", [True, False])
@pytest.mark.parametrize("failure_phase", ["acquisition", "template", "reindex"])
def test_migration_restores_validation_after_lazy_collection_failures(monkeypatch, initial_validate, failure_phase):
    datastore, store, unrelated_collection, _ = _make_lazy_store(initial_validate)
    made_collections = {}

    def make_collection(datastore_arg, name, model_class=None, validate=True, ilm_config=None):
        assert datastore_arg is store
        if failure_phase == "acquisition" and name == "view":
            raise RuntimeError("collection acquisition failed")
        collection = SimpleNamespace(
            datastore=store,
            ilm_config=object() if failure_phase == "template" else None,
            index_list_full=[f"{name}_hot"],
            reindex=MagicMock(side_effect=RuntimeError("reindex failed") if failure_phase == "reindex" else None),
            _create_index_template=MagicMock(
                side_effect=RuntimeError("template refresh failed") if failure_phase == "template" else None
            ),
            _index_doc_count=MagicMock(return_value=1),
        )
        made_collections[name] = collection
        return collection

    monkeypatch.setattr("howler.datastore.store.ESCollection", make_collection)
    expected_error = {
        "acquisition": "collection acquisition failed",
        "template": "template refresh failed",
        "reindex": "reindex failed",
    }[failure_phase]

    with pytest.raises(RuntimeError, match=expected_error):
        CaseInsensitiveMetadataMigration().run(datastore)

    assert store.validate is initial_validate
    assert store._collections == {"unrelated": unrelated_collection}
    if failure_phase == "acquisition":
        assert made_collections == {}
    elif failure_phase == "template":
        assert list(made_collections) == ["view"]
        made_collections["view"]._create_index_template.assert_called_once()
        made_collections["view"].reindex.assert_not_called()
    else:
        assert list(made_collections) == ["view"]
        made_collections["view"].reindex.assert_called_once()


def test_failed_template_refresh_is_unrecorded_retry_succeeds_then_applied_migration_skips(monkeypatch):
    datastore, collections, _ = _make_datastore()
    datastore.migration = FakeMigrationRecords()
    collections["view"].ilm_config = object()
    collections["view"]._create_index_template.side_effect = [RuntimeError("template refresh failed"), None]
    global_ilm_config = object()
    monkeypatch.setattr(
        "howler.odm.models.config.config",
        SimpleNamespace(datastore=SimpleNamespace(ilm=global_ilm_config)),
    )
    migration = CaseInsensitiveMetadataMigration()

    with pytest.raises(RuntimeError, match="template refresh failed"):
        run_migrations(datastore, [migration])

    assert datastore.migration.records == {}
    assert datastore.ds.validate is True
    collections["view"]._create_index_template.assert_called_once_with(global_ilm_config)
    collections["view"].reindex.assert_not_called()
    collections["view"]._index_doc_count.assert_not_called()
    for name in COLLECTION_NAMES[1:]:
        collections[name].reindex.assert_not_called()
        collections[name]._index_doc_count.assert_not_called()

    run_migrations(datastore, [migration])

    assert datastore.migration.records[migration.migration_id]["status"] == "applied"
    assert collections["view"]._create_index_template.call_count == 2
    for collection in collections.values():
        collection.reindex.assert_called_once_with(allow_failures=False, request_timeout=TRANSPORT_TIMEOUT)

    operation_counts = {
        name: (collection._create_index_template.call_count, collection.reindex.call_count)
        for name, collection in collections.items()
    }
    run_migrations(datastore, [migration])
    assert {
        name: (collection._create_index_template.call_count, collection.reindex.call_count)
        for name, collection in collections.items()
    } == operation_counts


def test_migration_preflight_still_precedes_real_lazy_collection_initialization(monkeypatch):
    datastore, store, unrelated_collection, indices = _make_lazy_store(True)
    leftover = f"{DATASTORE_INDEX_PREFIX}-view_hot__reindex"
    indices.get.side_effect = lambda index, **_: {leftover: {}} if "-view" in index else {}
    make_collection = MagicMock(side_effect=AssertionError("collection initialized before preflight"))
    monkeypatch.setattr("howler.datastore.store.ESCollection", make_collection)

    with pytest.raises(DataStoreException, match="leftover temporary reindex"):
        CaseInsensitiveMetadataMigration().run(datastore)

    assert indices.get.call_args_list[0].kwargs["index"] == f"{DATASTORE_INDEX_PREFIX}-view*__reindex"
    make_collection.assert_not_called()
    assert store.validate is True
    assert store._collections == {"unrelated": unrelated_collection}
