from copy import deepcopy
from inspect import unwrap
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from flask import Flask
from howler.api.v1.hit import overwrite_hit
from howler.api.v2 import ingest
from howler.models import model_extensions, schema
from howler.models.hit import Hit
from howler.services import hit_service

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


@pytest.mark.parametrize("ignore_extra_values", [False, True])
def test_convert_evidence_preserves_nested_lists(registered_hit, ignore_extra_values):
    data = {
        "howler.analytic": "Evidence",
        "evidence": [
            {"tags": ["a"], "file": {"elf": {"exports": ["first"], "sections": [{"name": "one"}, {"name": "two"}]}}},
            {"tags": ["b"], "file": {"elf": {"exports": ["second"]}}},
        ],
    }
    original = deepcopy(data)
    hit, warnings = hit_service.convert_hit(data, unique=False, ignore_extra_values=ignore_extra_values)
    assert data == original and warnings == []
    assert [{"tags": item["tags"], "file": item["file"]} for item in hit.as_primitives()["evidence"]] == original[
        "evidence"
    ]


@pytest.mark.parametrize("route", ["v1", "v2"])
@pytest.mark.parametrize("replace", ["false", "true"])
def test_empty_overwrite_preserves_evidence_and_logs(registered_hit, monkeypatch, route, replace):
    hit = registered_hit.model_validate(
        {
            "howler.analytic": "Original",
            "howler.hash": "ab",
            "evidence": [{"tags": ["first"]}, {"tags": ["second"]}],
            "howler.log": [{"timestamp": "2025-01-01", "user": "analyst", "explanation": "Created"}],
        }
    )
    stored = hit.as_primitives()
    app = Flask(__name__)
    app.secret_key = "test"
    with app.test_request_context(
        method="PUT" if route == "v1" else "PATCH",
        query_string={"replace": replace},
        json={"howler.analytic": "Updated", "evidence": {}, "howler.log": {}},
    ):
        if route == "v1":
            save = Mock(return_value=({}, "v2"))
            monkeypatch.setattr(hit_service, "save_hit", save)
            unwrap(overwrite_hit)(id=hit.howler.id, user=None, record=hit, server_version="v1")
            saved = save.call_args.args[0]
        else:
            collection = Mock(model_class=registered_hit)
            collection.get.side_effect = [(deepcopy(stored), "v1"), ({}, "v2")]
            monkeypatch.setattr(ingest, "datastore", lambda: {"hit": collection})
            unwrap(ingest.overwrite)(index="hit", id=hit.howler.id, user=None)
            saved = collection.save.call_args.args[1]
    updated = saved.as_primitives()
    assert updated["evidence"] == stored["evidence"] and updated["howler"]["log"] == stored["howler"]["log"]
    assert updated["howler"]["analytic"] == "Updated"


def test_evidence_extension_mapping(registered_hit):
    mapping = schema.document_mapping(registered_hit)
    assert mapping["properties"]["evidence.agent.id"]["type"] == "keyword"
    assert mapping["properties"]["evidence.email.attachments.file.hash.md5"]["normalizer"] == "lowercase_normalizer"
    assert [
        next(iter(template))
        for template in mapping["dynamic_templates"]
        if next(iter(template)).startswith("evidence.")
    ] == [
        f"evidence.{path}_tpl"
        for path in (
            "labels.*",
            "container.labels.*",
            "process.env_vars.*",
            "process.parent.env_vars.*",
            "process.parent.parent.env_vars.*",
        )
    ]
