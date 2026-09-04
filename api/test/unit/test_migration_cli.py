import importlib
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from howler.external import run_migrations


def test_list_does_not_open_datastore(monkeypatch, capsys):
    migrations = (SimpleNamespace(migration_id="first"), SimpleNamespace(migration_id="second"))
    load_datastore = MagicMock()
    monkeypatch.setattr(run_migrations, "_load_migrations", lambda: (migrations, MagicMock()))
    monkeypatch.setattr(run_migrations, "_load_datastore", load_datastore)

    assert run_migrations.main(["--list"]) == 0

    assert capsys.readouterr().out.splitlines() == ["first", "second"]
    load_datastore.assert_not_called()


def test_unknown_migration_id_is_rejected_before_datastore_creation(monkeypatch, capsys):
    migrations = (SimpleNamespace(migration_id="known"),)
    load_datastore = MagicMock()
    monkeypatch.setattr(run_migrations, "_load_migrations", lambda: (migrations, MagicMock()))
    monkeypatch.setattr(run_migrations, "_load_datastore", load_datastore)

    assert run_migrations.main(["--migration-id", "unknown"]) == 2

    assert "Unknown migration ID(s): unknown" in capsys.readouterr().err
    load_datastore.assert_not_called()


def test_selected_migrations_are_run_and_datastore_is_closed(monkeypatch):
    first = SimpleNamespace(migration_id="first")
    second = SimpleNamespace(migration_id="second")
    datastore = SimpleNamespace(ds=MagicMock())
    runner = MagicMock()
    monkeypatch.setattr(run_migrations, "_load_migrations", lambda: ((first, second), runner))
    monkeypatch.setattr(run_migrations, "_load_datastore", lambda: datastore)

    assert run_migrations.main(["--migration-id", "second", "--migration-id", "first"]) == 0

    runner.assert_called_once_with(datastore, (second, first))
    datastore.ds.close.assert_called_once_with()


def test_datastore_is_closed_and_failure_is_nonzero(monkeypatch, capsys):
    migration = SimpleNamespace(migration_id="first")
    datastore = SimpleNamespace(ds=MagicMock())
    runner = MagicMock(side_effect=RuntimeError("failed"))
    monkeypatch.setattr(run_migrations, "_load_migrations", lambda: ((migration,), runner))
    monkeypatch.setattr(run_migrations, "_load_datastore", lambda: datastore)

    assert run_migrations.main(["--all"]) == 1

    assert "Datastore migration failed: failed" in capsys.readouterr().err
    datastore.ds.close.assert_called_once_with()


def test_timeout_is_set_before_loading_migrations(monkeypatch):
    observed_timeout = None

    def load_migrations():
        nonlocal observed_timeout
        observed_timeout = os.environ.get("HWL_DATASTORE_TRANSPORT_TIMEOUT")
        return (SimpleNamespace(migration_id="first"),), MagicMock()

    monkeypatch.setattr(run_migrations, "_load_migrations", load_migrations)

    assert run_migrations.main(["--list", "--timeout", "42"]) == 0

    assert observed_timeout == "42"


def test_cli_import_does_not_initialize_flask_application(monkeypatch):
    monkeypatch.delitem(sys.modules, "howler.external.run_migrations", raising=False)
    monkeypatch.delitem(sys.modules, "howler.app", raising=False)
    monkeypatch.delitem(sys.modules, "howler.patched", raising=False)

    importlib.import_module("howler.external.run_migrations")

    assert "howler.app" not in sys.modules
    assert "howler.patched" not in sys.modules


def test_selection_rejects_duplicate_registered_ids():
    migrations = (SimpleNamespace(migration_id="duplicate"), SimpleNamespace(migration_id="duplicate"))

    with pytest.raises(ValueError, match="invalid or duplicated"):
        run_migrations._select_migrations(migrations, [], True)


def test_selection_rejects_duplicate_requested_ids():
    migrations = (SimpleNamespace(migration_id="known"),)

    with pytest.raises(ValueError, match="only be selected once"):
        run_migrations._select_migrations(migrations, ["known", "known"], False)


def test_selection_rejects_empty_registry():
    with pytest.raises(ValueError, match="set is empty"):
        run_migrations._select_migrations((), [], True)
