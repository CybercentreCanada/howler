from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

from howler.common import loader
from howler.common.exceptions import HowlerValueError
from howler.config_models import config
from howler.external import elasticsearch_initialize_collections as initializer
from howler.external.elasticsearch_initialize_collections import initialize_collections
from howler.external.elasticsearch_rest import setup_howler_plugin_paths
from howler.plugins import PLUGINS


class _FakeDatastore:
    def __init__(self, fail_with: Exception | None = None) -> None:
        self.accessed: list[str] = []
        self.closed = False
        self.ds = self
        self._fail_with = fail_with

    def __getattr__(self, name: str) -> Any:
        self.accessed.append(name)
        if self._fail_with is not None:
            raise self._fail_with
        return object()

    def close(self) -> None:
        self.closed = True


def test_initialize_collections_and_cli_lifecycle(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    store = _FakeDatastore()
    monkeypatch.setattr(initializer, "load_configured_plugins", lambda: [])
    monkeypatch.setattr(initializer, "_registered_collection_names", lambda: ("hit", "migration"))
    monkeypatch.setattr(loader, "datastore", lambda: store)

    assert initialize_collections(_FakeDatastore(), ("hit", "user_avatar")) == ["hit", "user_avatar"]
    with pytest.raises(SystemExit):
        initializer.main([])
    assert initializer.main(["--confirm-reconciliation"]) == 0
    assert store.accessed == ["hit", "migration"]
    assert store.closed is True
    assert "Initialized collection hit." in capsys.readouterr().out


def test_initializer_error_handling_and_plugin_fail_closed(
    monkeypatch: pytest.MonkeyPatch, capsys, tmp_path: Path
) -> None:
    failing = _FakeDatastore(fail_with=HowlerValueError("Mapping reconciliation refused a schema change."))
    monkeypatch.setattr(initializer, "load_configured_plugins", lambda: [])
    monkeypatch.setattr(initializer, "_registered_collection_names", lambda: ("hit",))
    monkeypatch.setattr(loader, "datastore", lambda: failing)

    assert initializer.main(["--confirm-reconciliation"]) == 1
    assert failing.closed is True
    err = capsys.readouterr().err
    assert "collection hit" in err and "Mapping reconciliation refused" in err

    monkeypatch.setattr(loader, "datastore", lambda: None)
    assert initializer.main(["--confirm-reconciliation"]) == 1
    assert "no storage object" in capsys.readouterr().err

    original_plugins = dict(PLUGINS)
    PLUGINS.clear()
    try:
        monkeypatch.undo()
        plugin_root = Path(__file__).resolve().parents[3] / "plugins"
        monkeypatch.setenv("HWL_PLUGIN_DIRECTORY", str(plugin_root))
        monkeypatch.setattr(config.ui, "debug", False)
        monkeypatch.setattr(sys, "path", ["/sentinel"])
        assert setup_howler_plugin_paths() == plugin_root
        assert sys.path == [str(plugin_root), "/sentinel"]

        monkeypatch.setenv("HWL_PLUGIN_DIRECTORY", str(tmp_path))
        monkeypatch.setattr(config.core, "plugins", {"missing-initializer-plugin"})
        monkeypatch.setattr(loader, "datastore", lambda: pytest.fail("must fail before datastore"))
        assert initializer.main(["--confirm-reconciliation"]) == 1
        assert "missing-initializer-plugin" in capsys.readouterr().err
    finally:
        PLUGINS.clear()
        PLUGINS.update(original_plugins)
