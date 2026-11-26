from types import SimpleNamespace

import pytest
from howler.datastore import howler_store
from howler.models import compound, model_extensions, model_registry, optional, schema
from howler.models.azure import Azure
from howler.models.ecs.file import File
from howler.models.hit import Hit
from howler.plugins.config import BasePluginConfig
from howler.services import hit_service

from sentinel.actions import azure_emit_hash
from sentinel.models.hit import declare_hit_extension
from sentinel.models.sentinel import Sentinel
from sentinel.odm.hit import generate


@pytest.fixture
def isolated_models():
    with model_extensions.isolated():
        yield


@pytest.fixture
def registered_hit(monkeypatch, isolated_models):
    declare_hit_extension()
    hit_type = model_extensions.finalize(Hit)
    monkeypatch.setattr(hit_service, "datastore", lambda: SimpleNamespace(hit=SimpleNamespace(model_class=hit_type)))
    return hit_type


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


@pytest.mark.parametrize("finalized", [False, True])
def test_hash_specification_includes_finalized_hit_extensions(monkeypatch, finalized, isolated_models):
    def declare_extensions():
        declare_hit_extension()
        model_extensions.declare(Hit, "extra_file", optional(compound(File)), plugin="test")

    plugin = BasePluginConfig(name="test", modules={"models": {"declare_extensions": {"hit": declare_extensions}}})
    monkeypatch.setattr(howler_store, "get_plugins", lambda: [plugin])
    monkeypatch.setattr(azure_emit_hash, "datastore", lambda: pytest.fail("Specification opened a datastore"))
    if finalized:
        declare_extensions()
        model_extensions.finalize(Hit)

    fields = azure_emit_hash.specification()["steps"][0]["options"]["field"]
    assert "file.hash.sha256" in fields
    assert "extra_file.hash.sha256" in fields


@pytest.mark.parametrize("azure", [None, Azure.model_validate({"tenant_id": "old-tenant-id"})])
def test_generate_populates_finalized_hit(registered_hit, azure):
    hit = registered_hit.model_construct(azure=azure)

    populated, result = generate(hit)

    assert result is hit
    assert populated == ["sentinel"]
    assert hit.sentinel.id == "example-sentinel-id"
    assert hit.azure.tenant_id == "example-tenant-id"
