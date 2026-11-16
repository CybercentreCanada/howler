from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

from howler.external import elasticsearch_initialize_collections as initializer
from howler.external.elasticsearch_initialize_collections import initialize_collections
from howler.external.elasticsearch_rest import setup_howler_plugin_paths


class _LazyStorage:
    def __init__(self) -> None:
        self.accessed: list[str] = []

    def __getattr__(self, name: str) -> Any:
        self.accessed.append(name)
        return object()


def test_initializer_only_touches_each_registered_collection_attribute() -> None:
    storage = _LazyStorage()
    names = ("hit", "event", "case", "user_avatar")

    initialized = initialize_collections(storage, names)

    assert initialized == list(names)
    assert storage.accessed == list(names)


def test_initializer_cli_requires_ack_and_closes_mock_datastore(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    class FakeDatastore(_LazyStorage):
        def __init__(self) -> None:
            super().__init__()
            self.closed = False
            self.ds = self

        def close(self) -> None:
            self.closed = True

    fake = FakeDatastore()
    monkeypatch.setattr(initializer, "load_configured_plugins", lambda: [])
    monkeypatch.setattr(initializer, "_registered_collection_names", lambda: ("hit", "migration"))
    from howler.common import loader

    monkeypatch.setattr(loader, "datastore", lambda: fake)

    with pytest.raises(SystemExit):
        initializer.main([])
    assert initializer.main(["--confirm-reconciliation"]) == 0
    assert fake.accessed == ["hit", "migration"]
    assert fake.closed is True
    assert "Initialized collection hit." in capsys.readouterr().out


def test_initializer_reports_safe_collection_failure_and_closes_store(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    from howler.common import loader
    from howler.common.exceptions import HowlerValueError

    class FailingDatastore(_LazyStorage):
        def __init__(self) -> None:
            super().__init__()
            self.closed = False
            self.ds = self

        def __getattr__(self, name: str) -> Any:
            self.accessed.append(name)
            raise HowlerValueError("Mapping reconciliation refused a schema change.")

        def close(self) -> None:
            self.closed = True

    storage = FailingDatastore()
    monkeypatch.setattr(initializer, "load_configured_plugins", lambda: [])
    monkeypatch.setattr(initializer, "_registered_collection_names", lambda: ("hit",))
    monkeypatch.setattr(loader, "datastore", lambda: storage)

    assert initializer.main(["--confirm-reconciliation"]) == 1
    captured = capsys.readouterr()
    assert "collection hit" in captured.err
    assert "Mapping reconciliation refused a schema change." in captured.err
    assert storage.closed is True


def test_initializer_handles_none_storage_without_attribute_error(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    from howler.common import loader

    monkeypatch.setattr(initializer, "load_configured_plugins", lambda: [])
    monkeypatch.setattr(loader, "datastore", lambda: None)

    assert initializer.main(["--confirm-reconciliation"]) == 1
    assert "datastore factory returned no storage object" in capsys.readouterr().err


def test_shared_plugin_path_setup_mirrors_app_using_real_plugin_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from howler.config_models import config

    plugin_root = Path(__file__).resolve().parents[3] / "plugins"
    monkeypatch.setenv("HWL_PLUGIN_DIRECTORY", str(plugin_root))
    monkeypatch.setattr(config.ui, "debug", False)
    monkeypatch.setattr(sys, "path", ["/sentinel"])

    configured_root = setup_howler_plugin_paths()

    assert configured_root == plugin_root
    assert sys.path == [str(plugin_root), "/sentinel"]


def test_initializer_fails_closed_for_missing_configured_plugin(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    from pathlib import Path

    from howler.common import loader
    from howler.config_models import config
    from howler.plugins import PLUGINS

    plugin_root = Path(__file__).resolve().parents[3] / "plugins"
    monkeypatch.setenv("HWL_PLUGIN_DIRECTORY", str(plugin_root))
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.setattr(config.core, "plugins", {"missing-initializer-plugin"})
    monkeypatch.setattr(loader, "datastore", lambda: pytest.fail("must fail before datastore construction"))
    old_plugin_cache = dict(PLUGINS)
    PLUGINS.clear()
    try:
        assert initializer.main(["--confirm-reconciliation"]) == 1
    finally:
        PLUGINS.clear()
        PLUGINS.update(old_plugin_cache)

    assert "missing-initializer-plugin" in capsys.readouterr().err
