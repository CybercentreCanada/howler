from copy import deepcopy
from inspect import unwrap
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from flask import Flask
from howler.api.v1.hit import overwrite_hit
from howler.api.v2 import ingest
from howler.common.exceptions import HowlerValueError
from howler.models import model_extensions, model_registry, schema
from howler.models.hit import Hit
from howler.services import hit_service
from howler.utils.dict_utils import flatten_deep

from evidence.models.evidence import Evidence
from evidence.models.hit import declare_hit_extension


@pytest.fixture
def registered_hit(monkeypatch):
    with model_extensions.isolated():
        declare_hit_extension()
        hit_type = model_extensions.finalize(Hit)
        monkeypatch.setattr(
            hit_service, "datastore", lambda: SimpleNamespace(hit=SimpleNamespace(model_class=hit_type))
        )
        yield hit_type


KEYWORD = {"doc_values": True, "ignore_above": 8191, "index": True, "type": "keyword"}


@pytest.mark.parametrize("ignore_extra_values", [False, True])
def test_convert_hit_keeps_each_evidence_records_lists(registered_hit, ignore_extra_values):
    data = {
        "howler.analytic": "Evidence Lists",
        "evidence": [
            {"tags": ["a"], "file": {"elf": {"exports": ["first"], "sections": [{"name": "one"}, {"name": "two"}]}}},
            {"tags": ["b"], "file": {"elf": {"exports": ["second"], "sections": [{"name": "three"}]}}},
        ],
    }
    original = deepcopy(data)
    hit, warnings = hit_service.convert_hit(data, unique=False, ignore_extra_values=ignore_extra_values)

    assert data == original
    assert warnings == []
    stored = hit.as_primitives()["evidence"]
    assert [{"tags": item["tags"], "file": item["file"]} for item in stored] == original["evidence"]


@pytest.mark.parametrize("route", ["v1", "v2"])
@pytest.mark.parametrize("replace", ["false", "true"])
def test_empty_overwrite_keeps_evidence_and_logs(registered_hit, monkeypatch, route, replace):
    hit = registered_hit.validate_howler(
        {
            "howler.analytic": "Original",
            "howler.hash": "ab",
            "evidence": [{"tags": ["first"]}, {"tags": ["second"]}],
            "howler.log": [{"timestamp": "2025-01-01", "user": "analyst", "explanation": "Created"}],
        }
    )
    stored = hit.as_primitives()
    patch = {"howler.analytic": "Updated", "evidence": {}, "howler.log": {}}
    app = Flask(__name__)
    app.config.update(SECRET_KEY="test")
    with app.test_request_context(
        method="PUT" if route == "v1" else "PATCH", json=patch, query_string={"replace": replace}
    ):
        if route == "v1":
            save_hit = Mock(return_value=({}, "v2"))
            monkeypatch.setattr(hit_service, "save_hit", save_hit)
            unwrap(overwrite_hit)(id=hit.howler.id, user=None, record=hit, server_version="v1")
            saved = save_hit.call_args.args[0]
        else:
            collection = Mock(model_class=registered_hit)
            collection.get.side_effect = [(deepcopy(stored), "v1"), ({}, "v2")]
            monkeypatch.setattr(ingest, "datastore", lambda: {"hit": collection})
            unwrap(ingest.overwrite)(index="hit", id=hit.howler.id, user=None)
            saved = collection.save.call_args.args[1]

    updated = saved.as_primitives()
    assert updated["howler"]["analytic"] == "Updated"
    assert updated["evidence"] == stored["evidence"]
    assert updated["howler"]["log"] == stored["howler"]["log"]


def test_flatten_deep_can_read_mixed_dotted_and_nested_evidence_twice():
    data = {"evidence.tags": ["outer"], "evidence": [{"tags": ["a"]}, {"tags": ["b"]}]}
    original = deepcopy(data)
    for _ in range(2):
        assert flatten_deep(data) == {"evidence.tags": ["outer", "a", "b"]}
        assert data == original


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
