import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from howler.common.exceptions import HowlerValueError
from howler.models import model_extensions, model_registry, schema
from howler.models.hit import Hit
from howler.services import hit_service

from evidence.models.evidence import Evidence
from evidence.models.hit import declare_hit_extension

LEGACY_EVIDENCE_CONTRACT = json.loads(Path(__file__).with_name("legacy_evidence_contract.json").read_text())
LEGACY_SOURCE_COMMIT = "3071fc4ea45d4b2dd44a7ee1646095426097d061"
LEGACY_SOURCE_SHA256 = "1ef4bc0bf73d3e94dff1634a3ad9e5d3cc54e402bba8886eb6592bdb3b0fe3f6"


@pytest.fixture
def registered_hit(monkeypatch):
    model_extensions.clear()
    declare_hit_extension()
    hit_type = model_extensions.finalize(Hit)
    monkeypatch.setattr(hit_service, "datastore", lambda: SimpleNamespace(hit=SimpleNamespace(model_class=hit_type)))
    yield hit_type
    model_extensions.clear()


def test_evidence_matches_pinned_legacy_contract(registered_hit):
    """Compare the typed extension to the model/mapping snapshot generated at the pinned base."""
    provenance = LEGACY_EVIDENCE_CONTRACT["provenance"]
    assert provenance["source_commit"] == LEGACY_SOURCE_COMMIT
    assert provenance["source_sha256"] == LEGACY_SOURCE_SHA256

    assert sorted(model_registry.flat_fields(Evidence)) == LEGACY_EVIDENCE_CONTRACT["flat_fields"]

    legacy_compound_paths = set(LEGACY_EVIDENCE_CONTRACT["flat_fields_with_compounds"])
    typed_compound_paths = set(model_registry.flat_fields(Evidence, show_compound=True))
    approved_compound_paths = set(LEGACY_EVIDENCE_CONTRACT["approved_differences"]["typed_only_compound_paths"])
    assert typed_compound_paths - legacy_compound_paths == approved_compound_paths
    assert legacy_compound_paths - typed_compound_paths == set()

    hit_mapping = schema.document_mapping(registered_hit)
    properties = {
        name.removeprefix("evidence."): mapping
        for name, mapping in hit_mapping["properties"].items()
        if name.startswith("evidence.")
    }
    assert properties == LEGACY_EVIDENCE_CONTRACT["elasticsearch"]["properties"]

    templates = []
    for template in hit_mapping["dynamic_templates"]:
        name, definition = next(iter(template.items()))
        path_key = "path_match" if "path_match" in definition else "match"
        path = definition.get(path_key, "")
        if isinstance(path, str) and path.startswith("evidence."):
            normalized_definition = dict(definition)
            normalized_definition[path_key] = path.removeprefix("evidence.")
            templates.append({name.removeprefix("evidence."): normalized_definition})

    assert templates == LEGACY_EVIDENCE_CONTRACT["elasticsearch"]["dynamic_templates"]


def test_build_evidence_alert(registered_hit):
    hit, warnings = hit_service.convert_hit(
        {
            "howler.analytic": "Evidence Example Analytic",
            "evidence.agent.id": ["potato"],
        },
        unique=False,
    )

    assert isinstance(hit, registered_hit)
    assert isinstance(hit.evidence[0], Evidence)
    assert hit.evidence[0].agent.id == "potato"
    assert warnings == []

    hit, warnings = hit_service.convert_hit(
        {
            "howler.analytic": "Evidence Example Analytic Part Two",
            "evidence": [{"agent.id": "potato"}, {"agent.id": "tomato"}],
        },
        unique=False,
    )

    assert [evidence.agent.id for evidence in hit.evidence] == ["potato", "tomato"]
    assert warnings == []

    with pytest.raises(HowlerValueError) as err:
        hit_service.convert_hit(
            {
                "howler.analytic": "Evidence Example Analytic Part Two",
                "evidence": [{"agent.id": "potato"}, {"agent.nope": "potato"}],
            },
            unique=False,
        )

    assert "nope" in str(err.value)
