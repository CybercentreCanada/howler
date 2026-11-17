from types import SimpleNamespace

import pytest
from howler.common.exceptions import HowlerValueError
from howler.models import model_extensions, model_registry, schema
from howler.models.hit import Hit
from howler.services import hit_service

from evidence.models.evidence import Evidence
from evidence.models.hit import declare_hit_extension


@pytest.fixture
def registered_hit(monkeypatch):
    model_extensions.clear()
    declare_hit_extension()
    hit_type = model_extensions.finalize(Hit)
    monkeypatch.setattr(hit_service, "datastore", lambda: SimpleNamespace(hit=SimpleNamespace(model_class=hit_type)))
    yield hit_type
    model_extensions.clear()


KEYWORD = {"doc_values": True, "ignore_above": 8191, "index": True, "type": "keyword"}


def test_evidence_extension_mapping(registered_hit):
    assert "evidence.agent.id" in model_registry.flat_fields(registered_hit)

    mapping = schema.document_mapping(registered_hit)
    properties = mapping["properties"]
    assert properties["evidence.agent.id"] == KEYWORD
    assert properties["evidence.email.attachments.file.hash.md5"] == {
        **KEYWORD,
        "normalizer": "lowercase_normalizer",
    }
    assert properties["evidence.email.attachments.file.hash.ssdeep"] == {
        "analyzer": "text_fuzzy",
        "index": True,
        "type": "text",
    }
    assert properties["evidence.destination.ip"] == {"doc_values": True, "index": True, "type": "ip"}
    assert properties["evidence.email.delivery_timestamp"] == {
        "doc_values": True,
        "format": "date_optional_time||epoch_millis",
        "index": True,
        "type": "date",
    }
    assert properties["evidence.destination.autonomous_systems.number"] == {
        "doc_values": True,
        "index": True,
        "type": "integer",
    }

    evidence_templates = [
        template
        for template in mapping["dynamic_templates"]
        if next(iter(template.values())).get("path_match", "").startswith("evidence.")
    ]
    assert evidence_templates == [
        {f"evidence.{path}_tpl": {"mapping": {"index": True, "type": "keyword"}, "path_match": f"evidence.{path}"}}
        for path in (
            "labels.*",
            "container.labels.*",
            "process.env_vars.*",
            "process.parent.env_vars.*",
            "process.parent.parent.env_vars.*",
        )
    ]


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
