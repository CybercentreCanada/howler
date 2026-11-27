from typing import Annotated

import pytest
from howler.datastore import howler_store
from howler.models import metadata, model_extensions
from howler.models.azure import Azure
from howler.models.ecs.file import File
from howler.models.hit import Hit
from howler.plugins.config import BasePluginConfig

from sentinel.actions import azure_emit_hash
from sentinel.models.hit import declare_hit_extension
from sentinel.odm.hit import generate


@pytest.mark.parametrize("azure", [None, Azure(tenant_id="old")])
def test_sentinel_extension(azure):
    with model_extensions.isolated():
        declare_hit_extension()
        hit = model_extensions.finalize(Hit).model_construct(azure=azure)
        fields, result = generate(hit)
        assert fields == ["sentinel"] and result is hit
        assert hit.sentinel.id == "example-sentinel-id" and hit.azure.tenant_id == "example-tenant-id"


@pytest.mark.parametrize("finalized", [False, True])
def test_hash_specification_includes_extensions(monkeypatch, finalized):
    def declare():
        declare_hit_extension()
        model_extensions.declare(Hit, "extra_file", Annotated[File | None, metadata(default=None)], plugin="test")

    with model_extensions.isolated():
        plugin = BasePluginConfig(name="test", modules={"models": {"declare_extensions": {"hit": declare}}})
        monkeypatch.setattr(howler_store, "get_plugins", lambda: [plugin])
        monkeypatch.setattr(azure_emit_hash, "datastore", lambda: pytest.fail("Specification opened a datastore"))
        if finalized:
            declare()
            model_extensions.finalize(Hit)
        fields = azure_emit_hash.specification()["steps"][0]["options"]["field"]
        assert {"file.hash.sha256", "extra_file.hash.sha256"} <= set(fields)
