import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from howler.models import model_extensions, model_registry, schema
from howler.models.hit import Hit
from howler.services import hit_service

from sentinel.models.hit import declare_hit_extension
from sentinel.models.sentinel import Sentinel

LEGACY_SENTINEL_CONTRACT = json.loads(Path(__file__).with_name("legacy_sentinel_contract.json").read_text())
LEGACY_SOURCE_COMMIT = "3071fc4ea45d4b2dd44a7ee1646095426097d061"
LEGACY_SOURCE_SHA256 = "5d3dd7753f76ba8095e6f998f5d4f58e6731472baef6fa75804f00c1974a0487"


@pytest.fixture
def registered_hit(monkeypatch):
    model_extensions.clear()
    declare_hit_extension()
    hit_type = model_extensions.finalize(Hit)
    monkeypatch.setattr(hit_service, "datastore", lambda: SimpleNamespace(hit=SimpleNamespace(model_class=hit_type)))
    yield hit_type
    model_extensions.clear()


def test_sentinel_matches_pinned_legacy_contract(registered_hit):
    """Compare Sentinel fields/mappings to the legacy snapshot and assert the startup delta."""
    provenance = LEGACY_SENTINEL_CONTRACT["provenance"]
    assert provenance["source_commit"] == LEGACY_SOURCE_COMMIT
    assert provenance["source_sha256"] == LEGACY_SOURCE_SHA256

    assert sorted(model_registry.flat_fields(Sentinel)) == LEGACY_SENTINEL_CONTRACT["flat_fields"]
    assert Sentinel.model_fields["id"].default is None

    hit_mapping = schema.document_mapping(registered_hit)
    properties = {
        name.removeprefix("sentinel."): mapping
        for name, mapping in hit_mapping["properties"].items()
        if name.startswith("sentinel.")
    }
    assert properties == LEGACY_SENTINEL_CONTRACT["elasticsearch"]["properties"]

    # The standalone legacy Sentinel model needed a catch-all refusal template. As a Hit
    # extension it inherits Hit's dynamic policy instead, so that standalone fallback must not
    # leak into the finalized Hit template set.
    legacy_templates = LEGACY_SENTINEL_CONTRACT["elasticsearch"]["dynamic_templates"]
    refusal_name = LEGACY_SENTINEL_CONTRACT["approved_differences"]["standalone_refusal_template"]
    assert len(legacy_templates) == 1
    assert refusal_name in legacy_templates[0]
    assert hit_mapping["dynamic"] is True
    assert all(refusal_name not in template for template in hit_mapping["dynamic_templates"])
    assert not any(
        str(definition.get("path_match", "")).startswith("sentinel.")
        for template in hit_mapping["dynamic_templates"]
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
