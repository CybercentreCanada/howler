from concurrent.futures import ThreadPoolExecutor
from threading import Event as ThreadEvent
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from howler.actions import change_field
from howler.datastore import howler_store
from howler.models import ModelExtensionRegistry, model_extensions
from howler.models.event import Event
from howler.models.fields import Keyword
from howler.models.hit import Hit
from howler.plugins.config import BasePluginConfig


@pytest.fixture
def isolated_models():
    with model_extensions.isolated():
        yield


def test_change_field_accepts_finalized_hit_extension(monkeypatch, isolated_models):
    field = "plugin_extension"
    model_extensions.declare(Hit, field, Keyword, plugin="test-plugin")
    hit_model = model_extensions.finalize(Hit)

    hit_collection = SimpleNamespace(model_class=hit_model, update_by_query=MagicMock())
    datastore = MagicMock(return_value=SimpleNamespace(hit=hit_collection))
    monkeypatch.setattr(change_field, "datastore", datastore)

    options = change_field.specification()["steps"][0]["options"]["field"]
    assert field in options
    datastore.assert_not_called()

    result = change_field.execute("*:*", field, "updated")

    assert result[0]["outcome"] == "success"
    hit_collection.update_by_query.assert_called_once()
    update = hit_collection.update_by_query.call_args.args[1][0]
    assert update.key == field
    assert update.value == "updated"


def test_cold_action_model_uses_configured_hooks_without_touching_pending_declarations(monkeypatch, isolated_models):
    def declare_hit():
        model_extensions.declare(Hit, "action_field", Keyword, plugin="action-plugin")

    plugin = BasePluginConfig(name="action-plugin", modules={"models": {"declare_extensions": {"hit": declare_hit}}})
    monkeypatch.setattr(howler_store, "get_plugins", lambda: [plugin])
    declare_hit()  # Startup has already declared this hook's field, but not finalized Hit.
    model_extensions.declare(Hit, "not_configured", Keyword, plugin="other")
    model_extensions.declare(Event, "other_field", Keyword, plugin="other")
    pending = {target: model_extensions.pending(target) for target in (Hit, Event)}

    for _ in range(2):
        fields = howler_store.get_action_hit_model().model_fields
        assert "action_field" in fields
        assert "not_configured" not in fields
    assert {target: model_extensions.pending(target) for target in pending} == pending
    assert not model_extensions.is_finalized(Hit)
    assert not model_extensions.is_finalized(Event)


def test_cold_discovery_preserves_another_threads_startup_model(monkeypatch):
    registry = ModelExtensionRegistry()
    monkeypatch.setattr(howler_store, "model_extensions", registry)
    monkeypatch.setattr(howler_store.config.core.clue, "enabled", False)
    declared, resume = ThreadEvent(), ThreadEvent()

    def declare_hit():
        registry.declare(Hit, "discovery_field", Keyword, plugin="action-plugin")
        declared.set()
        assert resume.wait(timeout=10)

    plugin = BasePluginConfig(name="action-plugin", modules={"models": {"declare_extensions": {"hit": declare_hit}}})
    monkeypatch.setattr(howler_store, "get_plugins", lambda: [plugin])
    with ThreadPoolExecutor(max_workers=1) as worker:
        discovery = worker.submit(howler_store.get_action_hit_model)
        try:
            assert declared.wait(timeout=10)
            assert not registry.pending(Hit)
            registry.declare(Hit, "startup_field", Keyword, plugin="startup")
            installed = registry.finalize(Hit)
        finally:
            resume.set()
        cold = discovery.result(timeout=10)

    assert "discovery_field" in cold.model_fields and "startup_field" not in cold.model_fields
    assert "startup_field" in installed.model_fields and "discovery_field" not in installed.model_fields
    assert howler_store.get_action_hit_model() is installed
