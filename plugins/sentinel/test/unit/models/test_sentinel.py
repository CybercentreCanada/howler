from types import SimpleNamespace

import pytest
from howler.config import config
from howler.datastore.howler_store import HowlerDatastore
from howler.models import model_extensions, model_registry, schema
from howler.models.hit import Hit
from howler.plugins import PLUGINS, get_plugins
from howler.services import hit_service

from sentinel.models.hit import declare_hit_extension
from sentinel.models.sentinel import Sentinel


@pytest.fixture
def registered_hit(monkeypatch):
    model_extensions.clear()
    declare_hit_extension()
    hit_type = model_extensions.finalize(Hit)
    monkeypatch.setattr(hit_service, "datastore", lambda: SimpleNamespace(hit=SimpleNamespace(model_class=hit_type)))
    yield hit_type
    model_extensions.clear()


def test_sentinel_extension_mapping(registered_hit):
    fields = model_registry.flat_fields(Sentinel)
    assert set(fields) == {"id", "tenant_id", "record_type", "incident_id", "alert_id", "evidence_id"}
    assert all(field.default is None for field in Sentinel.model_fields.values())

    mapping = schema.document_mapping(registered_hit)
    properties = mapping["properties"]
    keyword = {"doc_values": True, "ignore_above": 8191, "index": True, "type": "keyword"}
    assert {path: properties[f"sentinel.{path}"] for path in fields} == {path: keyword for path in fields}
    assert mapping["dynamic"] is True
    assert not any(
        str(definition.get("path_match", "")).startswith("sentinel.")
        for template in mapping["dynamic_templates"]
        for definition in template.values()
    )


def test_build_sentinel_alert(registered_hit):
    hit, warnings = hit_service.convert_hit(
        {"howler.analytic": "HBS Analytic", "sentinel.id": "Example Sentinel ID"},
        unique=False,
    )

    assert isinstance(hit, registered_hit)
    assert isinstance(hit.sentinel, Sentinel)
    assert hit.sentinel.id == "Example Sentinel ID"
    assert warnings == []


class RegistrationStore:
    """Record startup schema registrations without connecting to Elasticsearch."""

    def __init__(self):
        self.registrations = {}

    def register(self, name, model_class, **kwargs):
        self.registrations[name] = (model_class, kwargs)


def test_both_plugin_extensions_register_deterministically(monkeypatch):
    previous_plugin_cache = PLUGINS.copy()
    model_extensions.clear()
    PLUGINS.clear()
    monkeypatch.setattr(config.core, "plugins", {"evidence", "sentinel"})

    try:
        plugins = get_plugins()
        assert {plugin.name for plugin in plugins} == {"evidence", "sentinel"}
        assert all(set(plugin.modules.models.declare_extensions) == {"hit"} for plugin in plugins)

        store = RegistrationStore()
        HowlerDatastore(store)

        hit_model, hit_registration = store.registrations["hit"]
        assert model_extensions.is_finalized(Hit)
        assert hit_registration["schema_model"] is hit_model

        hit_fields = model_registry.flat_fields(hit_model)
        assert "evidence.agent.id" in hit_fields
        assert "sentinel.id" in hit_fields

        hit_mapping = schema.document_mapping(hit_model)
        assert "evidence.agent.id" in hit_mapping["properties"]
        assert "sentinel.id" in hit_mapping["properties"]

        extension_order = tuple(name for name in hit_model.model_fields if name in {"evidence", "sentinel"})
        model_extensions.clear()
        for plugin in reversed(plugins):
            plugin.modules.models.declare_extensions["hit"]()
        reverse_order_model = model_extensions.finalize(Hit)
        assert tuple(name for name in reverse_order_model.model_fields if name in {"evidence", "sentinel"}) == (
            extension_order
        )
    finally:
        model_extensions.clear()
        PLUGINS.clear()
        PLUGINS.update(previous_plugin_cache)
