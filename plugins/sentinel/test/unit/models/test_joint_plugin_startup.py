from howler.config import config
from howler.datastore.howler_store import HowlerDatastore
from howler.models import model_extensions, model_registry, schema
from howler.models.hit import Hit
from howler.plugins import PLUGINS, get_plugins


class RegistrationStore:
    """Isolated datastore double that records startup schema registrations."""

    def __init__(self):
        self.registrations = {}

    def register(self, name, model_class, **kwargs):
        self.registrations[name] = (model_class, kwargs)


def test_joint_plugin_manifests_resolve_and_finalize_during_datastore_startup(monkeypatch):
    """Resolve both manifests and finalize their extensions through normal startup, without ES."""
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
    finally:
        model_extensions.clear()
        PLUGINS.clear()
        PLUGINS.update(previous_plugin_cache)
